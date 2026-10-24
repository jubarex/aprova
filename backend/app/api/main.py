"""API FastAPI: sessão demo, comandos, projeções e Portal (v2 §13, adendo v2.1 §11).

Cada rota abre a própria transação curta (commit antes de responder). Mutações exigem
Idempotency-Key; o erro segue {code,message,details,request_id,retryable}.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from .. import clock
from ..agent import fixtures
from ..application import cases, changes, portal, views
from ..application.common import (
    AppError, audit, get_actor, has_role, open_interventions, pause_case, require_role, resume_case,
)
from ..application.seed import seed
from ..config import Settings, load_settings
from ..domain.changeset import CATALOG
from ..persistence.db import init_schema, make_engine, make_session_factory, tx
from ..persistence.models import (
    Actor, Base, ChangeSet, DemoSession, FormVersion, IdempotencyRecord, Intervention, Municipality,
    ProcessDefinition, Ticket, ValidationCase,
)
from ..worker import runner

LOCAL_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:4173"]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionIn(Body):
    actor_id: str


class TicketIn(Body):
    process_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    initial_reply: str = Field(min_length=1, max_length=20000)
    start_case: bool = True


class DecisionIn(Body):
    decision: str = Field(pattern="^(approve|reject)$")
    expected_case_version: int
    rationale: str = ""


class CommandIn(Body):
    expected_case_version: int
    rationale: str = ""


class TestCaseIn(Body):
    name: str
    kind: str = Field(pattern="^(positivo|negativo|limite|identidade)$")
    inputs: dict
    expected_codes: list[str] = []
    requirement: str = ""


class TestsIn(Body):
    cases: list[TestCaseIn]


class ResolveIn(Body):
    resolution: str = Field(min_length=3)


class ResetIn(Body):
    confirm: str


class ClockIn(Body):
    hours: float = Field(gt=0, le=24 * 30)


def create_app(settings: Settings | None = None, start_worker: bool = True) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings)
    init_schema(engine)
    factory = make_session_factory(engine)
    stop = threading.Event()
    paused = threading.Event()  # worker suspenso durante reset
    fixtures.register_all()
    with tx(factory) as s:
        seed(s)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        t = None
        if start_worker:
            def work():
                while not stop.is_set():
                    if paused.is_set():
                        stop.wait(0.2)
                        continue
                    runner.loop(factory, lambda: stop.is_set() or paused.is_set())
            t = threading.Thread(target=work, name="worker", daemon=True)
            t.start()
        yield
        stop.set()
        if t:
            t.join(timeout=3)

    app = FastAPI(title="Aprova Command", version="0.1.0", lifespan=lifespan)
    app.state.factory, app.state.settings, app.state.engine = factory, settings, engine
    app.add_middleware(CORSMiddleware, allow_origins=LOCAL_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        resp = await call_next(request)
        resp.headers["X-Request-Id"] = request.state.request_id
        return resp

    def err(request: Request, status: int, code: str, message: str, details=None, retryable=False):
        return JSONResponse(status_code=status, content={
            "code": code, "message": message, "details": details or {},
            "request_id": getattr(request.state, "request_id", ""), "retryable": retryable})

    @app.exception_handler(AppError)
    async def _app_error(request: Request, e: AppError):
        return err(request, e.status, e.code, e.message, e.details, e.retryable)

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, e: RequestValidationError):
        return err(request, 422, "VALIDATION_ERROR", "requisição inválida",
                   {"errors": [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()]})

    # ---------------------------------------------------------- helpers

    def db():
        return tx(factory)

    def whoami(s, token: str | None) -> Actor:
        if not token:
            raise AppError("UNAUTHENTICATED", "sessão demo ausente", 401)
        sess = s.get(DemoSession, token)
        if sess is None:
            raise AppError("UNAUTHENTICATED", "sessão demo inválida", 401)
        return get_actor(s, sess.actor_id)

    def need_implanter(s, actor: Actor) -> Actor:
        if not has_role(s, actor, "implanter"):
            raise AppError("FORBIDDEN", "ação restrita ao implantador", 403)
        return actor

    def idem(s, actor: Actor, operation: str, resource: str, key: str | None, payload: dict, fn):
        """Mesma chave+payload devolve o resultado original; payload diferente => 409 (v2 §13.1, T16)."""
        if not key:
            raise AppError("IDEMPOTENCY_KEY_REQUIRED", "envie o cabeçalho Idempotency-Key", 400)
        h = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        rec = s.scalar(select(IdempotencyRecord).where(
            IdempotencyRecord.actor_id == actor.id, IdempotencyRecord.operation == operation,
            IdempotencyRecord.resource == resource, IdempotencyRecord.key == key))
        if rec:
            if rec.payload_hash != h:
                raise AppError("IDEMPOTENCY_CONFLICT", "a chave já foi usada com outro conteúdo", 409)
            return rec.response
        out = fn()
        s.add(IdempotencyRecord(actor_id=actor.id, operation=operation, resource=resource, key=key,
                                payload_hash=h, response=out))
        return out

    TOKEN = Header(default=None, alias="X-Demo-Token")
    IDEM = Header(default=None, alias="Idempotency-Key")

    def case_or_404(s, actor: Actor, case_id: str) -> ValidationCase:
        c = s.get(ValidationCase, case_id)
        if c is None or (actor.municipality_id and c.municipality_id != actor.municipality_id):
            raise AppError("NOT_FOUND", "caso inexistente", 404)
        return c

    def cs_or_404(s, actor: Actor, cs_id: str) -> ChangeSet:
        cs = s.get(ChangeSet, cs_id)
        if cs is None or (actor.municipality_id and cs.municipality_id != actor.municipality_id):
            raise AppError("NOT_FOUND", "candidata inexistente", 404)
        return cs

    # ---------------------------------------------------------- saúde / demo

    @app.get("/api/health")
    def health():
        with db() as s:
            s.execute(text("select 1"))
        hb = runner.heartbeat()
        return {"status": "ok", "worker": {"running": start_worker and not stop.is_set(),
                                           "heartbeat": hb["at"], "last_error": hb["last_error"]}}

    @app.get("/api/demo/runtime")
    def runtime():
        return {"app_env": settings.app_env, "banner": "Ambiente de demonstração — dados sintéticos",
                "ai_mode": "IA: replay offline" if settings.ai_adapter == "offline_replay" else "IA: inferência ao vivo",
                "extraction_simulated": True, "business_now": clock.business_now().isoformat(),
                "catalog": CATALOG}

    @app.get("/api/demo/personas")
    def personas():
        with db() as s:
            rows = s.scalars(select(Actor).order_by(Actor.kind, Actor.name))
            return [{"id": a.id, "name": a.name, "kind": a.kind, "municipality_id": a.municipality_id} for a in rows]

    @app.post("/api/demo/session")
    def new_session(body: SessionIn):
        with db() as s:
            actor = get_actor(s, body.actor_id)
            token = secrets.token_urlsafe(24)
            s.add(DemoSession(token=token, actor_id=actor.id))
            return {"token": token, "actor": {"id": actor.id, "name": actor.name, "kind": actor.kind,
                                              "municipality_id": actor.municipality_id}}

    @app.get("/api/demo/me")
    def me(token: str | None = TOKEN):
        with db() as s:
            a = whoami(s, token)
            return {"id": a.id, "name": a.name, "kind": a.kind, "municipality_id": a.municipality_id,
                    "is_implanter": has_role(s, a, "implanter")}

    def demo_only():
        if not settings.is_demo:
            raise AppError("NOT_FOUND", "controle de simulação indisponível fora do modo demo", 404)

    @app.post("/api/demo/seed")
    def do_seed(token: str | None = TOKEN):
        demo_only()
        with db() as s:
            need_implanter(s, whoami(s, token))
            seed(s)
        return {"ok": True}

    @app.post("/api/demo/reset")
    def do_reset(body: ResetIn, token: str | None = TOKEN):
        demo_only()
        if body.confirm != "RESETAR":
            raise AppError("CONFIRMATION_REQUIRED", 'envie confirm="RESETAR"', 400)
        with db() as s:
            need_implanter(s, whoami(s, token))
        paused.set()
        try:
            Base.metadata.drop_all(engine)
            init_schema(engine)
            clock.set_offset(clock.timedelta(0))
            with tx(factory) as s:
                seed(s)
        finally:
            paused.clear()
        return {"ok": True}

    @app.post("/api/demo/clock/advance")
    def advance(body: ClockIn, token: str | None = TOKEN):
        demo_only()
        with db() as s:
            need_implanter(s, whoami(s, token))
        return {"business_now": clock.advance(body.hours).isoformat()}

    @app.get("/api/demo/scenarios")
    def scenarios():
        return [{"id": "G", "title": "Cenário G — ciclo completo",
                 "description": "Ticket com dois pedidos claros → candidata e testes → duas aprovações → aplicação, "
                                "verificação e fechamento.", "mode": "offline"}]

    @app.post("/api/demo/scenarios/{scenario_id}/start")
    def start_scenario(scenario_id: str, token: str | None = TOKEN):
        demo_only()
        if scenario_id != "G":
            raise AppError("NOT_FOUND", "cenário inexistente", 404)
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            p = s.get(ProcessDefinition, "proc_vr_iss012")
            active = s.scalar(select(ValidationCase).where(ValidationCase.process_id == p.id,
                                                           ValidationCase.active == True))  # noqa: E712
            if active:
                return {"case_id": active.id, "reused": True}
            t = cases.create_ticket(s, process_id=p.id, title="Ajustes no formulário de alvará",
                                    description="Pedido do secretário de Fazenda",
                                    initial_reply=fixtures.SCENARIO_G_REPLY, actor=actor.id)
            c = cases.start_case(s, t.id, actor.id)
            return {"case_id": c.id, "reused": False}

    # ---------------------------------------------------------- organização

    @app.get("/api/clients")
    def clients(token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            out = []
            for m in s.scalars(select(Municipality).order_by(Municipality.name)):
                procs = list(s.scalars(select(ProcessDefinition).where(ProcessDefinition.municipality_id == m.id)))
                active = len(list(s.scalars(select(ValidationCase).where(
                    ValidationCase.municipality_id == m.id, ValidationCase.active == True))))  # noqa: E712
                done = len(list(s.scalars(select(ValidationCase).where(
                    ValidationCase.municipality_id == m.id, ValidationCase.state == "COMPLETED"))))
                out.append({**views.municipality_dto(m), "processes": len(procs), "not_started": len(
                    [p for p in procs if not p.started]), "active_cases": active, "completed": done,
                    "target_date": views._utc(m.target_date).isoformat() if m.target_date else None})
            return out

    @app.get("/api/processes")
    def processes(client: str | None = None, token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            q = select(ProcessDefinition).order_by(ProcessDefinition.due_date)
            if client:
                q = q.where(ProcessDefinition.municipality_id == client)
            out = []
            for p in s.scalars(q):
                m = s.get(Municipality, p.municipality_id)
                out.append({"id": p.id, "code": p.code, "name": p.name, "municipality": views.municipality_dto(m),
                            "started": p.started, "wave": p.wave, "deadline": views.deadline_dto(p.due_date),
                            "current_version_id": p.current_version_id})
            return out

    @app.get("/api/forms/{version_id}")
    def form(version_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = whoami(s, token)
            v = s.get(FormVersion, version_id)
            p = s.get(ProcessDefinition, v.process_id) if v else None
            if not v or (actor.municipality_id and p.municipality_id != actor.municipality_id):
                raise AppError("NOT_FOUND", "versão inexistente", 404)
            return {"id": v.id, "version": v.version, "sha256": v.sha256, "schema": json.loads(v.content)}

    # ---------------------------------------------------------- Hoje

    @app.get("/api/today")
    def today(client: str | None = None, token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            return views.today(s, client)

    # ---------------------------------------------------------- tickets e casos

    @app.post("/api/tickets")
    def new_ticket(body: TicketIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))

            def run():
                t = cases.create_ticket(s, process_id=body.process_id, title=body.title,
                                        description=body.description, initial_reply=body.initial_reply,
                                        actor=actor.id)
                out = {"ticket_id": t.id, "case_id": None}
                if body.start_case:
                    out["case_id"] = cases.start_case(s, t.id, actor.id).id
                return out
            return idem(s, actor, "ticket.create", body.process_id, key, body.model_dump(), run)

    @app.get("/api/cases")
    def list_cases(client: str | None = None, token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            q = select(ValidationCase).order_by(ValidationCase.created_at.desc())
            if client:
                q = q.where(ValidationCase.municipality_id == client)
            return [views.case_card(s, c) for c in s.scalars(q)]

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            return views.case_detail(s, case_or_404(s, actor, case_id))

    @app.get("/api/cases/{case_id}/timeline")
    def get_timeline(case_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            case_or_404(s, actor, case_id)
            return views.timeline(s, case_id)

    @app.get("/api/cases/{case_id}/explanation")
    def get_explanation(case_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            return views.explanation(s, case_or_404(s, actor, case_id))

    @app.post("/api/cases/{case_id}/pause")
    def pause(case_id: str, body: CommandIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            c = case_or_404(s, actor, case_id)

            def run():
                pause_case(s, c, actor=actor.id, expected_version=body.expected_case_version, why=body.rationale)
                return {"state": c.state, "version": c.version}
            return idem(s, actor, "case.pause", case_id, key, body.model_dump(), run)

    @app.post("/api/cases/{case_id}/resume")
    def resume(case_id: str, body: CommandIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            c = case_or_404(s, actor, case_id)

            def run():
                resume_case(s, c, actor=actor.id, expected_version=body.expected_case_version, why=body.rationale)
                return {"state": c.state, "version": c.version}
            return idem(s, actor, "case.resume", case_id, key, body.model_dump(), run)

    # ---------------------------------------------------------- candidata, testes, aprovações

    def cs_detail(s, cs: ChangeSet) -> dict:
        case = s.get(ValidationCase, cs.case_id)
        run = changes.latest_run(s, cs.id, "pre_approval")
        post = changes.latest_run(s, cs.id, "post_readback")
        cases_ = changes.suite_cases(s, cs.id)
        return {
            "id": cs.id, "case_id": cs.case_id, "status": cs.status, "base_version_id": cs.base_version_id,
            "candidate_hash": cs.candidate_hash, "short_hash": cs.candidate_hash[:8],
            "rationale": cs.rationale, "operations": cs.operations, "case_version": case.version,
            "case_state": case.state, "applied_version_id": cs.applied_version_id,
            "diff": changes.build_diff(s, cs),
            "tests": [{"id": c.id, "name": c.name, "kind": c.kind, "inputs": c.inputs,
                       "expected_codes": c.expected_codes, "requirement": c.requirement,
                       "reviewed": c.reviewed_by is not None} for c in cases_],
            "suite_hash": changes.suite_hash(cases_),
            "coverage_gaps": changes.coverage_gaps(s, cs),
            "last_run": ({"id": run.id, "passed": run.passed, "results": run.results,
                          "stale": run.candidate_hash != cs.candidate_hash
                          or run.suite_hash != changes.suite_hash(cases_)} if run else None),
            "readback_run": ({"id": post.id, "passed": post.passed} if post else None),
            "open_interventions": len(open_interventions(s, case.id)),
        }

    @app.get("/api/cases/{case_id}/change-sets")
    def case_change_sets(case_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            case_or_404(s, actor, case_id)
            rows = s.scalars(select(ChangeSet).where(ChangeSet.case_id == case_id).order_by(ChangeSet.created_at))
            return [cs_detail(s, cs) for cs in rows]

    @app.get("/api/change-sets/{cs_id}/diff")
    def cs_diff(cs_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            return cs_detail(s, cs_or_404(s, actor, cs_id))

    @app.post("/api/change-sets/{cs_id}/tests/run")
    def tests_run(cs_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            cs = cs_or_404(s, actor, cs_id)
            changes.run_tests(s, cs, phase="pre_approval", executor=actor.id)
            s.flush()
            return cs_detail(s, cs)

    @app.post("/api/change-sets/{cs_id}/tests/review")
    def tests_review(cs_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            cs = cs_or_404(s, actor, cs_id)
            changes.review_tests(s, cs, actor)
            s.flush()
            return cs_detail(s, cs)

    @app.put("/api/change-sets/{cs_id}/tests")
    def tests_edit(cs_id: str, body: TestsIn, token: str | None = TOKEN):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            cs = cs_or_404(s, actor, cs_id)
            changes.edit_tests(s, cs, actor, [c.model_dump() for c in body.cases])
            s.flush()
            return cs_detail(s, cs)

    @app.post("/api/change-sets/{cs_id}/request-approval")
    def request_approval(cs_id: str, body: CommandIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            cs = cs_or_404(s, actor, cs_id)

            def run():
                changes.submit_for_approval(s, cs, actor, body.expected_case_version)
                s.flush()
                return {"state": s.get(ValidationCase, cs.case_id).state}
            return idem(s, actor, "cs.request_approval", cs_id, key, body.model_dump(), run)

    @app.post("/api/change-sets/{cs_id}/implanter-approval")
    def implanter_approval(cs_id: str, body: DecisionIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = whoami(s, token)
            cs = cs_or_404(s, actor, cs_id)

            def run():
                changes.decide_implanter(s, cs, actor, decision=body.decision,
                                         expected_version=body.expected_case_version, rationale=body.rationale)
                s.flush()
                return {"state": s.get(ValidationCase, cs.case_id).state}
            return idem(s, actor, "cs.implanter_approval", cs_id, key, body.model_dump(), run)

    @app.post("/api/change-sets/{cs_id}/municipal-approval")
    def municipal_approval(cs_id: str, body: DecisionIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = whoami(s, token)
            cs = cs_or_404(s, actor, cs_id)

            def run():
                changes.decide_municipal(s, cs, actor, decision=body.decision,
                                         expected_version=body.expected_case_version, rationale=body.rationale,
                                         channel="command")
                s.flush()
                return {"state": s.get(ValidationCase, cs.case_id).state}
            return idem(s, actor, "cs.municipal_approval", cs_id, key, body.model_dump(), run)

    @app.post("/api/change-sets/{cs_id}/revoke")
    def revoke(cs_id: str, body: CommandIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = whoami(s, token)
            cs = cs_or_404(s, actor, cs_id)

            def run():
                changes.revoke(s, cs, actor, expected_version=body.expected_case_version,
                               rationale=body.rationale or "sem motivo informado")
                s.flush()
                return {"state": s.get(ValidationCase, cs.case_id).state}
            return idem(s, actor, "cs.revoke", cs_id, key, body.model_dump(), run)

    # ---------------------------------------------------------- intervenções

    @app.get("/api/interventions")
    def interventions(status: str = "open", client: str | None = None, token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            q = select(Intervention).where(Intervention.status == status).order_by(
                Intervention.urgency, Intervention.created_at)
            if client:
                q = q.where(Intervention.municipality_id == client)
            out = []
            for i in s.scalars(q):
                c = s.get(ValidationCase, i.case_id)
                out.append({"id": i.id, "code": i.reason_code, "reason": i.reason, "needed": i.needed_decision,
                            "urgency": i.urgency, "case": views.case_card(s, c),
                            "since": views._utc(i.created_at).isoformat()})
            return out

    @app.post("/api/interventions/{iv_id}/resolve")
    def resolve(iv_id: str, body: ResolveIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_implanter(s, whoami(s, token))
            iv = s.get(Intervention, iv_id)
            if iv is None:
                raise AppError("NOT_FOUND", "intervenção inexistente", 404)

            def run():
                if iv.status != "open":
                    raise AppError("ALREADY_RESOLVED", "intervenção já resolvida", 409)
                iv.status, iv.resolution, iv.resolved_by = "resolved", body.resolution, actor.id
                iv.resolved_at = clock.business_now()
                case = s.get(ValidationCase, iv.case_id)
                audit(s, actor=actor.id, action="intervention_resolved", case=case, why=body.resolution)
                # resolver não aprova nem encerra outras intervenções; a retomada é um comando à parte
                return {"id": iv.id, "status": iv.status}
            return idem(s, actor, "iv.resolve", iv_id, key, body.model_dump(), run)

    # ---------------------------------------------------------- Portal da prefeitura

    def need_contact(s, token) -> Actor:
        a = whoami(s, token)
        if a.kind != "contato":
            raise AppError("FORBIDDEN", "o Portal é para contatos da prefeitura", 403)
        return a

    @app.get("/api/portal/me")
    def portal_me(token: str | None = TOKEN):
        with db() as s:
            return portal.home(s, need_contact(s, token))

    @app.get("/api/portal/approvals/{cs_id}")
    def portal_approval(cs_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = need_contact(s, token)
            cs = s.get(ChangeSet, cs_id)
            if cs is None:
                raise AppError("NOT_FOUND", "recurso inexistente", 404)
            return portal.approval_view(s, cs, actor)

    @app.post("/api/portal/approvals/{cs_id}")
    def portal_decide(cs_id: str, body: DecisionIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = need_contact(s, token)
            cs = s.get(ChangeSet, cs_id)
            if cs is None or cs.municipality_id != actor.municipality_id:
                raise AppError("NOT_FOUND", "recurso inexistente", 404)

            def run():
                changes.decide_municipal(s, cs, actor, decision=body.decision,
                                         expected_version=body.expected_case_version, rationale=body.rationale,
                                         channel="portal")
                s.flush()
                return {"state": s.get(ValidationCase, cs.case_id).state}
            return idem(s, actor, "portal.approval", cs_id, key, body.model_dump(), run)

    return app


app = None


def get_app() -> FastAPI:  # uvicorn --factory app.api.main:get_app
    return create_app()
