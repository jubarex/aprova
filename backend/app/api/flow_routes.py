"""Rotas das fatias 2-3: conversas, rodadas, indicações, decisões, anexos, Caixa de entrada e Portal de pendências."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from types import SimpleNamespace

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .. import clock
from ..application import (
    attachments, decisions, flow_views, messaging, people, portal, rounds, scenario_runner, views,
)
from ..application.common import AppError, get_actor, has_role, resume_case
from ..persistence.flow_models import Attachment, ContactReferral, Message, RoundItem, ValidationRound
from ..persistence.models import Actor, DemoSession, Intervention, Ticket, ValidationCase
from ..persistence.flow_models import PortalAccess
from ..scenarios import SCENARIOS, public_view


class B(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReferralIn(B):
    name: str = Field(min_length=2)
    sector: str = ""
    alias: str = ""
    topic: str = "geral"
    gap_ids: list[str] = []
    expected_case_version: int | None = None


class AuthorizeIn(B):
    decision: str = Field(default="authorize", pattern="^(authorize|reject)$")


class OwnerIn(B):
    name: str = ""
    topic: str = "geral"
    existing_actor_id: str | None = None


class DecisionIn(B):
    kind: str
    text: str
    payload: dict = {}
    intervention_id: str | None = None
    expected_case_version: int | None = None


class ReviewIn(B):
    relevant: bool = True
    text: str = ""


class LinkIn(B):
    round_id: str


class FaultIn(B):
    channel: str
    mode: str | None = None


class MergeIn(B):
    drop_id: str
    confirm: bool = False


class ChannelIn(B):
    channel: str
    case_id: str | None = None


class WebhookIn(B):
    case_id: str
    actor_id: str
    external_key: str
    body: str


class ReopenIn(B):
    text: str = Field(min_length=3)


class AnswerIn(B):
    kind: str = Field(default="answer", pattern="^(answer|not_applicable)$")
    text: str = ""
    expected_case_version: int | None = None


class PortalReferIn(B):
    name: str = Field(min_length=2)
    sector: str = ""
    alias: str = ""


class OnboardingIn(B):
    preferred_channel: str = "portal"
    claims: list[dict] = []


class LinkReqIn(B):
    actor_id: str


class TokenIn(B):
    token: str


def register(app: FastAPI, c: SimpleNamespace) -> None:
    TOKEN, IDEM = c.TOKEN, c.IDEM
    db, whoami, need_implanter, idem, case_or_404 = c.db, c.whoami, c.need_implanter, c.idem, c.case_or_404

    # ---------------------------------------------------------- leituras do implantador

    @app.get("/api/cases/{case_id}/gaps")
    def gaps(case_id: str, token: str | None = TOKEN):
        with db() as s:
            a = need_implanter(s, whoami(s, token))
            case_or_404(s, a, case_id)
            return flow_views.gaps_view(s, case_id)

    @app.get("/api/cases/{case_id}/rounds")
    def rounds_(case_id: str, token: str | None = TOKEN):
        with db() as s:
            a = need_implanter(s, whoami(s, token))
            case_or_404(s, a, case_id)
            return flow_views.rounds_view(s, case_id)

    @app.get("/api/cases/{case_id}/conversations")
    def convo(case_id: str, token: str | None = TOKEN):
        with db() as s:
            a = need_implanter(s, whoami(s, token))
            case_or_404(s, a, case_id)
            return {"messages": flow_views.conversation_view(s, case_id),
                    "referrals": flow_views.referrals_view(s, case_id),
                    "decisions": flow_views.decisions_view(s, case_id)}

    @app.get("/api/inbox")
    def inbox(client: str | None = None, triage: bool = False, token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            return flow_views.inbox(s, client, triage)

    @app.get("/api/demo/scenarios")
    def scenarios_():
        return public_view()

    # ---------------------------------------------------------- simulador de canais

    @app.post("/api/cases/{case_id}/messages")
    async def post_message(case_id: str, request: Request, token: str | None = TOKEN):
        """Simulador (Pylon/WhatsApp/Portal): multipart com texto e anexos; mesma jornada dos demais canais."""
        form = await request.form()
        files = [f for f in form.getlist("files") if hasattr(f, "filename")]
        blobs = [(f.filename, await f.read()) for f in files]
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            case = case_or_404(s, imp, case_id)
            actor = get_actor(s, str(form.get("actor_id", "")))
            channel = str(form.get("channel", ""))
            body = str(form.get("text", ""))
            key = str(form.get("external_key") or "") or None
            reply = str(form.get("reply_to_round_id") or "") or None
            if len(blobs) > attachments.MAX_PER_MESSAGE:
                raise AppError("UPLOAD_REJECTED", "no máximo 5 arquivos por mensagem", 422)
            for name, data in blobs:
                attachments.validate(name, data)  # valida tudo antes de gravar qualquer coisa
            if channel == "pylon" and key:
                out = messaging.pylon_webhook(s, case, actor, external_key=key, body=body)
                return out
            m, created = messaging.ingest(s, case, actor, channel=channel, body=body, external_key=key,
                                          reply_to_round_id=reply, has_attachment=bool(blobs))
            sidecar = str(form.get("sidecar_text") or "") or None
            if created:
                for name, data in blobs:
                    attachments.store(s, c.settings.attachment_dir, case, m, name, data, sidecar)
            return {"message_id": m.id, "created": created, "substantive": m.substantive,
                    "triage": m.triage_status, "flagged": m.flagged}

    @app.post("/api/integrations/pylon/webhook")
    def pylon_webhook(body: WebhookIn, token: str | None = TOKEN):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            case = case_or_404(s, imp, body.case_id)
            return messaging.pylon_webhook(s, case, get_actor(s, body.actor_id), external_key=body.external_key,
                                           body=body.body)

    @app.post("/api/cases/{case_id}/script/{step_id}")
    def script(case_id: str, step_id: str, token: str | None = TOKEN):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            case = case_or_404(s, imp, case_id)
            return scenario_runner.run_step(s, c.settings.attachment_dir, case, step_id, imp)

    @app.post("/api/demo/faults")
    def set_fault(body: FaultIn, token: str | None = TOKEN):
        c.demo_only()
        with db() as s:
            need_implanter(s, whoami(s, token))
            rounds.set_fault(s, body.channel, body.mode)
            return rounds.faults(s)

    @app.get("/api/demo/faults")
    def get_faults(token: str | None = TOKEN):
        with db() as s:
            need_implanter(s, whoami(s, token))
            return rounds.faults(s)

    # ---------------------------------------------------------- rodadas, triagem, anexos

    @app.post("/api/rounds/{round_id}/release")
    def release(round_id: str, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            rnd = s.get(ValidationRound, round_id)
            if rnd is None:
                raise AppError("NOT_FOUND", "rodada inexistente", 404)
            case = case_or_404(s, imp, rnd.case_id)

            def run():
                rounds.release_round(s, case, rnd, imp.id)
                return {"state": case.state}
            return idem(s, imp, "round.release", round_id, key, {}, run)

    @app.post("/api/messages/{message_id}/link")
    def link(message_id: str, body: LinkIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            m = s.get(Message, message_id)
            if m is None:
                raise AppError("NOT_FOUND", "mensagem inexistente", 404)
            case = case_or_404(s, imp, m.case_id)

            def run():
                messaging.link_message(s, case, m, body.round_id, imp.id)
                return {"state": case.state}
            return idem(s, imp, "message.link", message_id, key, body.model_dump(), run)

    @app.get("/api/attachments/{att_id}")
    def get_attachment(att_id: str, token: str | None = TOKEN):
        with db() as s:
            actor = whoami(s, token)
            att = s.get(Attachment, att_id)
            if att is None or (actor.municipality_id and att.municipality_id != actor.municipality_id):
                raise AppError("NOT_FOUND", "anexo inexistente", 404)
            data = (c.settings.attachment_dir / att.internal_name).read_bytes()
            ctype = "text/plain; charset=utf-8" if att.content_type in ("text/markdown", "application/json") else att.content_type
            return Response(content=data, media_type=ctype, headers={
                "Content-Disposition": f'attachment; filename="{att.id}"', "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox"})

    @app.post("/api/attachments/{att_id}/review")
    def review_att(att_id: str, body: ReviewIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            att = s.get(Attachment, att_id)
            if att is None:
                raise AppError("NOT_FOUND", "anexo inexistente", 404)
            case = case_or_404(s, imp, att.case_id)

            def run():
                hd = attachments.review(s, case, att, imp.id, body.relevant, body.text)
                if body.relevant:
                    messaging.kick(s, case)
                elif case.state == "BLOCKED_HUMAN":
                    pass
                return {"decision_id": hd.id}
            return idem(s, imp, "attachment.review", att_id, key, body.model_dump(), run)

    # ---------------------------------------------------------- métricas, cronograma, avaliação

    @app.get("/api/command/metrics")
    def metrics(client: str | None = None, token: str | None = TOKEN):
        from ..application import metrics as m
        with db() as s:
            need_implanter(s, whoami(s, token))
            return m.compute(s, client)

    @app.get("/api/schedule")
    def schedule(client: str | None = None, token: str | None = TOKEN):
        from ..persistence.models import Municipality, ProcessDefinition
        with db() as s:
            need_implanter(s, whoami(s, token))
            out = []
            for m in s.scalars(select(Municipality).order_by(Municipality.name)):
                if client and m.id != client:
                    continue
                procs = list(s.scalars(select(ProcessDefinition).where(ProcessDefinition.municipality_id == m.id)
                                       .order_by(ProcessDefinition.wave, ProcessDefinition.due_date)))
                rows = []
                for p in procs:
                    case = s.scalar(select(ValidationCase).where(ValidationCase.process_id == p.id)
                                    .order_by(ValidationCase.created_at.desc()))
                    card = views.case_card(s, case) if case else None
                    rows.append({"id": p.id, "code": p.code, "name": p.name, "wave": p.wave,
                                 "due_at": views._utc(p.due_date).isoformat() if p.due_date else None,
                                 "deadline": views.deadline_dto(p.due_date, done=bool(case and case.state == "COMPLETED")),
                                 "case_id": case.id if case else None,
                                 "axis": card["axis"] if card else "idle",
                                 "state_label": card["state_label"] if card else "Não iniciado"})
                out.append({**views.municipality_dto(m),
                            "start": views._utc(m.start_date).isoformat() if m.start_date else None,
                            "target": views._utc(m.target_date).isoformat() if m.target_date else None,
                            "now": clock.business_now().isoformat(), "processes": rows})
            return out

    @app.get("/api/evaluations/latest")
    def latest_eval(token: str | None = TOKEN):
        import json as _json
        from ..evaluation.generalization import ARTIFACTS
        with db() as s:
            need_implanter(s, whoami(s, token))
        out = {"offline": None, "generalization": None}
        files = (sorted(ARTIFACTS.glob("evaluation-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                 if ARTIFACTS.exists() else [])
        for f in files:
            try:
                d = _json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            g = d.get("gate")
            if g in out and out[g] is None:
                out[g] = {k: v for k, v in d.items() if k != "executions"}
        return out

    # ---------------------------------------------------------- pessoas

    @app.post("/api/cases/{case_id}/referrals")
    def referral(case_id: str, body: ReferralIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            actor = whoami(s, token)
            case = case_or_404(s, actor, case_id)

            def run():
                if actor.kind == "contato":
                    who = actor
                else:
                    need_implanter(s, actor)
                    who = None
                if who is None:
                    raise AppError("FORBIDDEN", "a indicação parte de um contato da prefeitura", 403)
                rf = people.request_referral(s, case, who, name=body.name, sector=body.sector, alias=body.alias,
                                             topic=body.topic, gap_ids=body.gap_ids)
                return {"referral_id": rf.id, "status": rf.status}
            return idem(s, actor, "referral.create", case_id, key, body.model_dump(), run)

    @app.post("/api/referrals/{rf_id}/authorize")
    def authorize(rf_id: str, body: AuthorizeIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            rf = s.get(ContactReferral, rf_id)
            if rf is None:
                raise AppError("NOT_FOUND", "indicação inexistente", 404)
            case_or_404(s, imp, rf.case_id)

            def run():
                people.authorize_referral(s, rf, imp, decision=body.decision)
                return {"status": rf.status, "actor_id": rf.new_actor_id}
            return idem(s, imp, "referral.authorize", rf_id, key, body.model_dump(), run)

    @app.post("/api/cases/{case_id}/authorize-owner")
    def authorize_owner(case_id: str, body: OwnerIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            case = case_or_404(s, imp, case_id)

            def run():
                a = people.authorize_owner(s, case, imp, name=body.name, topic=body.topic,
                                           existing_actor_id=body.existing_actor_id)
                return {"actor_id": a.id}
            return idem(s, imp, "case.authorize_owner", case_id, key, body.model_dump(), run)

    @app.post("/api/contacts/{actor_id}/merge")
    def merge(actor_id: str, body: MergeIn, token: str | None = TOKEN):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            keep, drop = get_actor(s, actor_id), get_actor(s, body.drop_id)
            people.merge_contacts(s, keep, drop, imp, body.confirm)
            return {"kept": keep.id, "aliases": keep.aliases}

    @app.post("/api/contacts/{actor_id}/preferred-channel")
    def preferred(actor_id: str, body: ChannelIn, token: str | None = TOKEN):
        with db() as s:
            who = whoami(s, token)
            target = get_actor(s, actor_id)
            if who.id != target.id and not has_role(s, who, "implanter"):
                raise AppError("FORBIDDEN", "somente o próprio contato ou o implantador", 403)
            people.set_preferred_channel(s, body.case_id, target, body.channel)
            return {"channel": body.channel}

    # ---------------------------------------------------------- decisões, reabertura, intervenção

    @app.post("/api/cases/{case_id}/decisions")
    def decide(case_id: str, body: DecisionIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            case = case_or_404(s, imp, case_id)

            def run():
                hd = decisions.record(s, case, imp.id, kind=body.kind, text=body.text, payload=body.payload,
                                      intervention_id=body.intervention_id, expected_version=body.expected_case_version)
                return {"decision_id": hd.id, "state": case.state}
            return idem(s, imp, "case.decision", case_id, key, body.model_dump(), run)

    @app.post("/api/tickets/{ticket_id}/reopen")
    def reopen(ticket_id: str, body: ReopenIn, token: str | None = TOKEN, key: str | None = IDEM):
        from ..application import cases as cases_svc
        from ..persistence.models import TicketComment
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            t = s.get(Ticket, ticket_id)
            if t is None:
                raise AppError("NOT_FOUND", "ticket inexistente", 404)

            def run():
                last = s.scalar(select(ValidationCase).where(ValidationCase.ticket_id == t.id)
                                .order_by(ValidationCase.cycle_number.desc()))
                if last is None or last.state != "COMPLETED":
                    raise AppError("INVALID_TRANSITION", "só um ciclo concluído pode ser reaberto", 409)
                s.add(TicketComment(ticket_id=t.id, visibility="public", author=imp.name, body=body.text))
                t.initial_reply, t.status = body.text, "open"
                new = cases_svc.start_case(s, t.id, imp.id)
                return {"case_id": new.id, "cycle": new.cycle_number, "previous": last.id}
            return idem(s, imp, "ticket.reopen", ticket_id, key, body.model_dump(), run)

    # ---------------------------------------------------------- Portal: pendências, link mágico, histórico

    @app.post("/api/demo/portal-links")
    def portal_link(body: LinkReqIn, token: str | None = TOKEN):
        c.demo_only()
        with db() as s:
            need_implanter(s, whoami(s, token))
            a = get_actor(s, body.actor_id)
            if a.kind != "contato":
                raise AppError("VALIDATION_ERROR", "o link é para contatos da prefeitura", 422)
            raw = secrets.token_urlsafe(24)
            s.add(PortalAccess(actor_id=a.id, municipality_id=a.municipality_id,
                               token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                               expires_at=clock.business_now() + timedelta(days=14)))
            return {"url": f"/portal/entrar?t={raw}", "expires_in_days": 14}

    @app.post("/api/portal/session")
    def portal_session(body: TokenIn):
        with db() as s:
            pa = s.scalar(select(PortalAccess).where(PortalAccess.token_hash == hashlib.sha256(body.token.encode()).hexdigest()))
            now = clock.business_now()
            exp = pa.expires_at.replace(tzinfo=now.tzinfo) if pa and pa.expires_at.tzinfo is None else (pa.expires_at if pa else None)
            if pa is None or pa.revoked_at is not None or exp < now:
                raise AppError("INVALID_LINK", "este link expirou ou não é válido", 401)
            pa.last_used_at = now
            sess = secrets.token_urlsafe(24)
            s.add(DemoSession(token=sess, actor_id=pa.actor_id))
            return {"token": sess}

    @app.get("/api/portal/pending")
    def pending(token: str | None = TOKEN):
        with db() as s:
            return flow_views.portal_items(s, c.need_contact(s, token))

    @app.get("/api/portal/items/{item_id}")
    def item(item_id: str, token: str | None = TOKEN):
        with db() as s:
            a = c.need_contact(s, token)
            for it in flow_views.portal_items(s, a):
                if it["id"] == item_id:
                    return it
            raise AppError("NOT_FOUND", "pendência inexistente", 404)

    @app.post("/api/portal/items/{item_id}/answer")
    async def answer(item_id: str, request: Request, token: str | None = TOKEN,
                     idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        form = await request.form()
        blobs = [(f.filename, await f.read()) for f in form.getlist("files") if hasattr(f, "filename")]
        text = str(form.get("text", ""))
        kind = str(form.get("kind", "answer"))
        with db() as s:
            a = c.need_contact(s, token)
            it = s.get(RoundItem, item_id)
            rnd = s.get(ValidationRound, it.round_id) if it else None
            if not it or rnd.recipient_id != a.id or rnd.municipality_id != a.municipality_id:
                raise AppError("NOT_FOUND", "pendência inexistente", 404)
            case = s.get(ValidationCase, rnd.case_id)
            for name, data in blobs:
                attachments.validate(name, data)
            if kind == "not_applicable":
                text = text.strip() or "Esta pergunta não se aplica a este processo."
            if not text.strip() and not blobs:
                raise AppError("RATIONALE_REQUIRED", "escreva a resposta ou anexe um documento", 422)

            def run():
                key = f"portal:{item_id}:{hashlib.sha256((text + str(len(blobs))).encode()).hexdigest()[:16]}"
                m, created = messaging.ingest(s, case, a, channel="portal", body=text, external_key=key,
                                              round_item_id=item_id, has_attachment=bool(blobs))
                if created:
                    for name, data in blobs:
                        attachments.store(s, c.settings.attachment_dir, case, m, name, data, None)
                return {"message_id": m.id, "received": True}
            return idem(s, a, "portal.answer", item_id, idempotency_key, {"t": text, "k": kind, "n": len(blobs)}, run)

    @app.post("/api/portal/items/{item_id}/refer")
    def refer(item_id: str, body: PortalReferIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            a = c.need_contact(s, token)
            it = s.get(RoundItem, item_id)
            rnd = s.get(ValidationRound, it.round_id) if it else None
            if not it or rnd.recipient_id != a.id:
                raise AppError("NOT_FOUND", "pendência inexistente", 404)
            case = s.get(ValidationCase, rnd.case_id)
            from ..persistence.flow_models import Gap
            gap = s.get(Gap, it.gap_id)

            def run():
                rf = people.request_referral(s, case, a, name=body.name, sector=body.sector, alias=body.alias,
                                             topic=gap.topic, gap_ids=[gap.id])
                return {"referral_id": rf.id, "status": rf.status}
            return idem(s, a, "portal.refer", item_id, key, body.model_dump(), run)

    @app.get("/api/portal/history")
    def history(token: str | None = TOKEN):
        with db() as s:
            a = c.need_contact(s, token)
            rows = s.scalars(select(Message).where(Message.actor_id == a.id, Message.direction == "in",
                                                   Message.municipality_id == a.municipality_id)
                             .order_by(Message.seq.desc()))
            return [{"id": m.id, "channel": m.channel, "body": m.body, "at": views._utc(m.received_at).isoformat()}
                    for m in rows]

    @app.get("/api/portal/onboarding")
    def onboarding_get(token: str | None = TOKEN):
        with db() as s:
            return portal.onboarding_view(s, c.need_contact(s, token))

    @app.post("/api/portal/onboarding")
    def onboarding(body: OnboardingIn, token: str | None = TOKEN, key: str | None = IDEM):
        with db() as s:
            a = c.need_contact(s, token)
            return idem(s, a, "portal.onboarding", a.id, key, body.model_dump(),
                        lambda: portal.save_onboarding(s, a, body.preferred_channel, body.claims))

    @app.post("/api/claims/{claim_id}/handle")
    def handle_claim(claim_id: str, token: str | None = TOKEN):
        from ..persistence.flow_models import ResponsibilityClaim
        with db() as s:
            imp = need_implanter(s, whoami(s, token))
            cl = s.get(ResponsibilityClaim, claim_id)
            if cl is None:
                raise AppError("NOT_FOUND", "declaração inexistente", 404)
            cl.handled = True
            return {"handled": True}
