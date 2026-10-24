"""Fontes, entrada do agente e aplicação validada da saída (v2 §5.3, §10.3, §11).

O agente propõe; aqui o backend confere citações, catálogo e lacunas e só então persiste.
Tudo acontece na transação do chamador: proposta inválida não deixa efeito parcial.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agent import instructions, replay
from ..agent.contracts import AgentEnvelope
from ..domain.changeset import ChangeSetError, apply_operations, operation_sources_ok
from ..domain.forms import FormSchema, canonical_bytes, schema_hash
from ..clock import business_now
from ..persistence.flow_models import Attachment, DerivedArtifact, Gap, HumanDecision, Message, RoundItem
from ..persistence.models import (
    Approval, ChangeRequest, ChangeSet, Evidence, FormTestCase, FormVersion, Ticket, ValidationCase, new_id,
)
from .common import AppError, audit
from .cases import load_schema

AGENT_INSTRUCTIONS = ["00_VISAO_E_ESCOPO", "01_ARQUITETURA_E_CONTRATOS", "02_AGENTE_GENERICO",
                      "03_RODADAS_E_CANAIS", "04_FORMULARIOS_E_APROVACOES", "08_RED_TEAM"]
MAX_EVIDENCE_CHARS = 200_000

# Adaptador ativo; o app o ajusta na inicialização (offline_replay | openai_compatible).
STATE = {"adapter": "offline_replay"}


@dataclass
class Source:
    ref: str
    type: str  # message | derived | human_decision
    id: str
    text: str
    hash: str


def _h(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def collect_sources(s: Session, case: ValidationCase) -> list[Source]:
    """Fontes substantivas em ordem de recepção; texto original imutável."""
    rows: list[tuple] = []
    for m in s.scalars(select(Message).where(Message.case_id == case.id, Message.direction == "in",
                                             Message.substantive == True, Message.flagged == False,  # noqa: E712
                                             Message.mirror_of_message_id.is_(None))):
        if m.round_id is None and m.triage_status == "pending":
            continue  # sem correlação inequívoca: fica em triagem, não vira evidência
        rows.append((m.received_at, m.seq, "message", m.id, m.body))
    for d in s.scalars(select(DerivedArtifact).where(DerivedArtifact.case_id == case.id,
                                                     DerivedArtifact.status == "ok")):
        att = s.get(Attachment, d.attachment_id)
        parent = s.get(Message, att.message_id)
        if parent.flagged or (parent.round_id is None and parent.triage_status == "pending"):
            continue
        rows.append((parent.received_at, parent.seq + 0.5, "derived", d.id, d.text))
    for hd in s.scalars(select(HumanDecision).where(HumanDecision.case_id == case.id)):
        rows.append((hd.created_at, 0, "human_decision", hd.id, hd.text))
    rows.sort(key=lambda r: (r[0].replace(tzinfo=None), r[1], r[3]))
    out = [Source(f"S{i + 1}", t, sid, text, _h(text)) for i, (_, _, t, sid, text) in enumerate(rows)]
    if sum(len(x.text) for x in out) > MAX_EVIDENCE_CHARS:
        raise AppError("EVIDENCE_TOO_LARGE", "evidências excedem o limite por análise; selecione ou segmente", 422)
    return out


def open_gaps(s: Session, case_id: str) -> list[Gap]:
    return list(s.scalars(select(Gap).where(Gap.case_id == case_id, Gap.status.in_(["open", "disputed"]))
                          .order_by(Gap.created_at, Gap.ref)))


def build_input(s: Session, case: ValidationCase, stage: str) -> tuple[replay.AnalysisInput, list[Source]]:
    ticket = s.get(Ticket, case.ticket_id)
    base = s.get(FormVersion, case.base_version_id)
    sources = collect_sources(s, case)
    gaps = sorted(open_gaps(s, case.id), key=lambda g: int(g.ref[1:]))
    inp = replay.AnalysisInput(
        ticket_reply=ticket.initial_reply, base_hash=base.sha256, stage=stage,
        sources=tuple(x.text for x in sources), open_gaps=tuple(f"{g.ref}:{g.question}" for g in gaps))
    return inp, sources


def run_agent(s: Session, case: ValidationCase, stage: str) -> tuple[AgentEnvelope, dict, list[Source]]:
    """Chama o adaptador ativo. ReplayMiss/AppError sobem para o chamador abrir intervenção."""
    inp, sources = build_input(s, case, stage)
    loaded = instructions.load_many(AGENT_INSTRUCTIONS)
    if STATE["adapter"] == "offline_replay":
        env, meta = replay.analyze(inp, case.id, case.version)
    else:
        from ..agent import live  # import tardio: só quando configurado
        env, meta = live.analyze(inp, case.id, case.version, sources, [g for g in open_gaps(s, case.id)])
    meta["instructions"] = [{"id": i.id, "sha256": i.sha256} for i in loaded]
    return env, meta, sources


def _resolve_text(s: Session, case: ValidationCase, ref: str, sources: list[Source]) -> tuple[str, str, str, str]:
    """(source_type, source_id, text, hash) de uma referência TICKET ou Sn."""
    if ref == "TICKET":
        t = s.get(Ticket, case.ticket_id)
        return "ticket_initial_reply", t.id, t.initial_reply, _h(t.initial_reply)
    by = {x.ref: x for x in sources}
    x = by.get(ref)
    if x is None:
        raise AppError("BAD_REFERENCE", f"fonte inexistente: {ref}", 422)
    return x.type, x.id, x.text, x.hash


def next_gap_number(s: Session, case_id: str) -> int:
    return (s.scalar(select(func.count()).select_from(Gap).where(Gap.case_id == case_id)) or 0) + 1


def apply_output(s: Session, case: ValidationCase, env: AgentEnvelope, meta: dict, sources: list[Source]) -> dict:
    """Valida e persiste. Devolve {outcome, ...}; levanta AppError/ChangeSetError sem efeito parcial."""
    if env.expected_case_version != case.version:
        raise AppError("STALE_PROPOSAL", "proposta obsoleta: o caso mudou durante a análise", 409)
    # 1) citações exatas (pontos de código Unicode, [start,end))
    evidences: list[Evidence] = []
    for c in env.evidence:
        stype, sid, text, shash = _resolve_text(s, case, c.source_ref, sources)
        if not (0 <= c.start < c.end <= len(text)) or text[c.start:c.end] != c.quote:
            raise AppError("CITATION_MISMATCH", f"citação não coincide com a fonte {c.source_ref}: {c.quote[:40]!r}", 422)
        evidences.append(Evidence(id=new_id("ev_"), case_id=case.id, municipality_id=case.municipality_id,
                                  source_type=stype, source_id=sid, source_hash=shash,
                                  start=c.start, end=c.end, quote=c.quote))

    def ev_ids(idx: list[int], what: str) -> list[str]:
        out = []
        for i in idx:
            if not 0 <= i < len(evidences):
                raise AppError("BAD_REFERENCE", f"{what}: índice de evidência inválido ({i})", 422)
            out.append(evidences[i].id)
        return out

    # 2) valida tudo antes de adicionar à sessão
    new_requests = [(r, ev_ids(r.evidence_indexes, "pedido")) for r in env.requests]
    for g in env.gaps:
        if not 0 <= g.request_index < len(env.requests):
            raise AppError("BAD_REFERENCE", f"lacuna aponta para pedido inexistente ({g.request_index})", 422)
    gap_by_ref = {g.ref: g for g in s.scalars(select(Gap).where(Gap.case_id == case.id))}
    for u in env.gap_updates:
        if u.gap_ref not in gap_by_ref:
            raise AppError("BAD_REFERENCE", f"lacuna inexistente: {u.gap_ref}", 422)
        if u.status == "answered" and not u.evidence_indexes:
            raise AppError("BAD_REFERENCE", f"{u.gap_ref}: resposta sem evidência", 422)
        ev_ids(u.evidence_indexes, u.gap_ref)

    candidate = ops = None
    ops_ev: list[list[str]] = []
    if env.change_set:
        ops = []
        for p in env.change_set.operations:
            ids = ev_ids(p.evidence_indexes, "operação")
            ops.append(p.operation.model_copy(update={"evidence_ids": ids}))
        missing = operation_sources_ok(ops)
        if missing:
            raise ChangeSetError("; ".join(missing))
        base = s.get(FormVersion, case.base_version_id)
        candidate = apply_operations(load_schema(base), ops)

    # 3) persiste
    s.add_all(evidences)
    crs: list[ChangeRequest] = []
    for r, ids in new_requests:
        cr = ChangeRequest(id=new_id("cr_"), case_id=case.id, summary=r.summary,
                           source_quote=evidences[r.evidence_indexes[0]].quote, clarity=r.clarity,
                           feasibility=r.feasibility, risk=r.risk, next_action=r.next_action)
        crs.append(cr)
    s.add_all(crs)
    s.flush()
    n = next_gap_number(s, case.id)
    new_gaps: list[Gap] = []
    for g in env.gaps:
        ref_ids = new_requests[g.request_index][1]
        gap = Gap(id=new_id("gap_"), case_id=case.id, request_id=crs[g.request_index].id, ref=f"G{n}",
                  question=g.question, answer_kind=g.answer_kind, options=g.options, topic=g.topic,
                  blocking=g.blocking, answer_evidence_ids=[], note="; ".join(ref_ids[:0]))
        n += 1
        new_gaps.append(gap)
    s.add_all(new_gaps)
    s.flush()
    answered_now = 0
    for u in env.gap_updates:
        gap = gap_by_ref[u.gap_ref]
        gap.status = u.status
        gap.note = u.note
        if u.status == "answered":
            gap.answer_evidence_ids = ev_ids(u.evidence_indexes, u.gap_ref)
            answered_now += 1
            for it in s.scalars(select(RoundItem).where(RoundItem.gap_id == gap.id, RoundItem.status == "open")):
                it.status = "answered"
        elif u.status == "obsolete":
            for it in s.scalars(select(RoundItem).where(RoundItem.gap_id == gap.id, RoundItem.status == "open")):
                it.status = "answered"
    s.flush()
    audit(s, actor="agente", action="dossier_created" if env.stage == "initial" else "reconciled", case=case,
          detail={**meta, "requests": len(crs), "new_gaps": len(new_gaps), "answered": answered_now},
          why=f"{len(crs)} pedido(s) novo(s), {len(new_gaps)} lacuna(s) nova(s), {answered_now} resposta(s) validada(s)")

    blocking_open = [g for g in open_gaps(s, case.id) if g.blocking]
    result = {"new_gaps": len(new_gaps), "answered": answered_now, "blocking_open": len(blocking_open),
              "change_set_id": None, "intervention": None}
    if env.intervention:
        result["intervention"] = env.intervention.model_dump()
    disputed = [g for g in blocking_open if g.status == "disputed"]
    result["disputed"] = len(disputed)

    if env.change_set and candidate is not None and not blocking_open and not disputed and not env.intervention:
        unsafe = [r for r, _ in new_requests if r.clarity != "clear" or r.feasibility != "supported"
                  or r.next_action != "propose_change"]
        if not unsafe:
            result["change_set_id"] = _store_change_set(s, case, env, ops, candidate, evidences)
            for cr in s.scalars(select(ChangeRequest).where(ChangeRequest.case_id == case.id,
                                                            ChangeRequest.disposition == "pending",
                                                            ChangeRequest.next_action == "propose_change")):
                cr.disposition = "accepted"
    if env.no_safe_action:
        result["no_safe_action"] = env.no_safe_action
    return result


def _store_change_set(s: Session, case: ValidationCase, env: AgentEnvelope, ops, candidate: FormSchema,
                      evidences: list[Evidence]) -> str:
    """Nova revisão supera a anterior e invalida aprovações (I09)."""
    from .changes import invalidate_approvals  # evita ciclo de import
    prev = list(s.scalars(select(ChangeSet).where(ChangeSet.case_id == case.id).order_by(ChangeSet.revision)))
    rev = (prev[-1].revision + 1) if prev else 1
    for p in prev:
        if p.status not in ("superseded", "rejected", "applied", "verified"):
            invalidate_approvals(s, p, case, reason="Nova revisão da candidata", actor="agente")
            p.status = "superseded"
    cs = ChangeSet(id=new_id("chs_"), case_id=case.id, municipality_id=case.municipality_id,
                   process_id=case.process_id, revision=rev, base_version_id=case.base_version_id,
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
    audit(s, actor="agente", action="change_set_proposed", case=case,
          detail={"change_set_id": cs.id, "revision": rev, "candidate_hash": cs.candidate_hash},
          why="Candidata criada a partir dos pedidos aceitos e das respostas validadas")
    case.next_action = "Revisar os testes e pedir aprovação"
    return cs.id
