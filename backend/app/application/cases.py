"""Ticket -> caso -> dossiê -> ChangeSet candidata (v2 §7, §9, §11)."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agent import instructions, replay
from ..agent.contracts import AgentEnvelope
from ..clock import business_now
from ..domain.changeset import ChangeSetError, apply_operations, operation_sources_ok
from ..domain.forms import FormSchema, canonical_bytes, schema_hash, validate_schema
from ..persistence.models import (
    ChangeRequest, ChangeSet, Evidence, FormTestCase, FormVersion, ProcessDefinition, Ticket,
    ValidationCase, new_id,
)
from .common import AppError, audit, enqueue, move_case, open_intervention

AGENT_INSTRUCTIONS = ["00_VISAO_E_ESCOPO", "01_ARQUITETURA_E_CONTRATOS", "02_AGENTE_GENERICO",
                      "04_FORMULARIOS_E_APROVACOES"]


def load_schema(version: FormVersion) -> FormSchema:
    return FormSchema.model_validate_json(version.content)


def store_version(s: Session, process: ProcessDefinition, schema: FormSchema,
                  base_version_id: str | None) -> FormVersion:
    nxt = (s.scalar(select(func.max(FormVersion.version)).where(FormVersion.process_id == process.id)) or 0) + 1
    content = canonical_bytes(schema)
    v = FormVersion(id=new_id("fv_"), process_id=process.id, version=nxt, base_version_id=base_version_id,
                    content=content.decode("utf-8"), sha256=schema_hash(schema), created_at=business_now())
    s.add(v)
    s.flush()
    return v


def create_ticket(s: Session, *, process_id: str, title: str, description: str, initial_reply: str,
                  actor: str) -> Ticket:
    process = s.get(ProcessDefinition, process_id)
    if process is None:
        raise AppError("NOT_FOUND", "processo inexistente", 404)
    t = Ticket(id=new_id("tk_"), municipality_id=process.municipality_id, process_id=process.id,
               title=title, description=description, initial_reply=initial_reply, created_at=business_now())
    s.add(t)
    audit(s, actor=actor, action="ticket_created", municipality_id=process.municipality_id,
          detail={"ticket_id": t.id})
    return t


def start_case(s: Session, ticket_id: str, actor: str) -> ValidationCase:
    """DRAFT -> INTAKE -> UNDERSTANDING_FORM; fixa a base e agenda a leitura do schema."""
    ticket = s.get(Ticket, ticket_id)
    if ticket is None:
        raise AppError("NOT_FOUND", "ticket inexistente", 404)
    process = s.get(ProcessDefinition, ticket.process_id)
    if not process.current_version_id:
        raise AppError("NO_BASE_FORM", "processo sem formulário vigente", 409)
    active = s.scalar(select(ValidationCase).where(ValidationCase.ticket_id == ticket.id,
                                                   ValidationCase.active == True))  # noqa: E712
    if active:
        raise AppError("CASE_ALREADY_ACTIVE", "já existe um ciclo ativo para este ticket", 409,
                       {"case_id": active.id})
    cycle = (s.scalar(select(func.max(ValidationCase.cycle_number)).where(
        ValidationCase.ticket_id == ticket.id)) or 0) + 1
    prev = s.scalar(select(ValidationCase.id).where(ValidationCase.ticket_id == ticket.id,
                                                    ValidationCase.cycle_number == cycle - 1))
    case = ValidationCase(id=new_id("cs_"), municipality_id=ticket.municipality_id, ticket_id=ticket.id,
                          process_id=process.id, cycle_number=cycle, previous_case_id=prev, state="DRAFT",
                          base_version_id=process.current_version_id, next_action="Ler o formulário",
                          state_since=business_now())
    s.add(case)
    try:
        s.flush()
    except IntegrityError as e:
        raise AppError("CASE_ALREADY_ACTIVE", "já existe um ciclo ativo para este ticket", 409) from e
    process.started = True
    audit(s, actor=actor, action="case_created", case=case, why="Caso criado a partir do ticket")
    move_case(s, case, "start", actor=actor, why="Ticket válido; versão-base fixada")
    move_case(s, case, "ticket_persisted", actor=actor, why="Ticket e referência persistidos")
    enqueue(s, "understand_form", case.id, dedupe_key=f"understand:{case.id}")
    return case


# ---------------------------------------------------------------- worker


def handle_understand_form(s: Session, case: ValidationCase) -> None:
    base = s.get(FormVersion, case.base_version_id)
    errors = validate_schema(load_schema(base))
    if errors:
        open_intervention(s, case, code="SCHEMA_INVALIDO", reason="O formulário-base não passou na validação: "
                          + "; ".join(errors[:3]), needed="Corrigir o formulário-base")
        move_case(s, case, "integrity_error", actor="sistema", why="Schema-base inválido")
        return
    move_case(s, case, "schema_validated", actor="sistema", why="Schema-base validado")
    enqueue(s, "analyze_initial_reply", case.id, dedupe_key=f"analyze:{case.id}")


def _verify_citation(text: str, start: int, end: int, quote: str) -> bool:
    return 0 <= start < end <= len(text) and text[start:end] == quote


def handle_analyze(s: Session, case: ValidationCase) -> None:
    ticket = s.get(Ticket, case.ticket_id)
    base = s.get(FormVersion, case.base_version_id)
    loaded = instructions.load_many(AGENT_INSTRUCTIONS)
    inp = replay.AnalysisInput(ticket_reply=ticket.initial_reply, base_hash=base.sha256)
    try:
        env, meta = replay.analyze(inp, case.id, case.version)
    except replay.ReplayMiss as e:
        open_intervention(s, case, code="REPLAY_MISS", urgency=2,
                          reason="Não há gravação de replay para esta entrada; nenhuma análise foi inventada.",
                          needed="Registrar a análise manualmente ou executar com inferência ao vivo")
        audit(s, actor="agente", action="replay_miss", case=case, detail={"input_hash": inp.key()})
        move_case(s, case, "dossier_blocked", actor="sistema", why=str(e))
        return
    meta["instructions"] = [{"id": i.id, "sha256": i.sha256} for i in loaded]
    try:
        persist_proposal(s, case, ticket, base, env, meta)
    except (ChangeSetError, AppError, ValueError) as e:
        open_intervention(s, case, code="PROPOSTA_INVALIDA", reason=f"A proposta do agente foi rejeitada: {e}",
                          needed="Revisar o pedido e criar a candidata manualmente")
        audit(s, actor="agente", action="proposal_rejected", case=case, detail={"error": str(e), **meta})
        move_case(s, case, "dossier_blocked", actor="sistema", why="Proposta inválida")


def persist_proposal(s: Session, case: ValidationCase, ticket: Ticket, base: FormVersion,
                     env: AgentEnvelope, meta: dict) -> None:
    if env.expected_case_version != case.version:
        raise AppError("STALE_PROPOSAL", "proposta obsoleta", 409)
    src_hash = hashlib.sha256(ticket.initial_reply.encode("utf-8")).hexdigest()
    # 1) citações exatas; qualquer falha invalida a proposta inteira (sem efeito parcial)
    for r in env.change_requests.requests:
        c = r.citation
        if not _verify_citation(ticket.initial_reply, c.start, c.end, c.quote):
            raise AppError("CITATION_MISMATCH", f"citação não coincide com o texto: {c.quote[:40]!r}", 422)
    requests = env.change_requests.requests
    evidences: list[Evidence] = []
    crs: list[ChangeRequest] = []
    for r in requests:
        ev = Evidence(id=new_id("ev_"), case_id=case.id, municipality_id=case.municipality_id,
                      source_type="ticket_initial_reply", source_id=ticket.id, source_hash=src_hash,
                      start=r.citation.start, end=r.citation.end, quote=r.citation.quote)
        evidences.append(ev)
        crs.append(ChangeRequest(case_id=case.id, summary=r.summary, source_quote=r.citation.quote,
                                 clarity=r.clarity, feasibility=r.feasibility, risk=r.risk,
                                 next_action=r.next_action))
    candidate = None
    ops = []
    if env.change_set:
        for p in env.change_set.operations:
            for i in p.citation_indexes:
                if not 0 <= i < len(requests):
                    raise AppError("BAD_REFERENCE", f"índice de pedido inválido: {i}", 422)
        # traduz fonte (índice do pedido) -> evidence_id real
        for p in env.change_set.operations:
            op = p.operation.model_copy(update={"evidence_ids": [evidences[i].id for i in p.citation_indexes]})
            ops.append(op)
        missing = operation_sources_ok(ops)
        if missing:
            raise ChangeSetError("; ".join(missing))
        candidate = apply_operations(load_schema(base), ops)
    # 2) persiste tudo (mesma transação do chamador)
    s.add_all(evidences + crs)
    s.flush()
    audit(s, actor="agente", action="dossier_created", case=case, detail=meta,
          why=f"{len(requests)} pedido(s) identificado(s) com citação verificada")
    unsafe = [r for r in requests if r.clarity != "clear" or r.feasibility != "supported"
              or r.next_action != "propose_change"]
    if candidate is None or unsafe:
        open_intervention(s, case, code="SEM_ACAO_SEGURA", urgency=2,
                          reason="Há pedidos ambíguos ou fora do catálogo; o agente não propõe alteração sem decisão.",
                          needed="Esclarecer com a prefeitura ou decidir manualmente")
        move_case(s, case, "dossier_blocked", actor="sistema", why="Sem ação segura")
        return
    cs = ChangeSet(id=new_id("chs_"), case_id=case.id, municipality_id=case.municipality_id,
                   process_id=case.process_id, revision=1, base_version_id=base.id,
                   operations=[o.model_dump(mode="json") for o in ops],
                   candidate_content=canonical_bytes(candidate).decode("utf-8"),
                   candidate_hash=schema_hash(candidate), status="draft",
                   rationale=env.change_set.rationale, created_by="agente", created_at=business_now())
    s.add(cs)
    s.flush()
    for t in env.change_set.tests:
        s.add(FormTestCase(change_set_id=cs.id, name=t.name, kind=t.kind, inputs=t.inputs,
                           expected_codes=sorted(t.expected_codes), requirement=t.requirement,
                           evidence_ids=[e.id for e in evidences]))
    for cr in crs:
        cr.disposition = "accepted"
    audit(s, actor="agente", action="change_set_proposed", case=case, detail={"change_set_id": cs.id,
          "candidate_hash": cs.candidate_hash}, why="Candidata criada a partir dos pedidos aceitos")
    case.next_action = "Revisar os testes e pedir aprovação"
    move_case(s, case, "dossier_changes_ready", actor="sistema", why="Candidata e testes prontos para revisão")
