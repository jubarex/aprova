"""Handlers do worker para o fluxo de rodadas: análise, planejamento, envio e consolidação."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent import replay
from ..domain.changeset import ChangeSetError
from ..domain.states import CaseState
from ..clock import business_now
from ..persistence.flow_models import DerivedArtifact, Gap, HumanDecision, Message, RoundItem
from ..persistence.models import ChangeSet, Ticket, ValidationCase
from . import analysis, messaging, rounds
from .common import AppError, audit, enqueue, move_case, open_intervention


def _fail_analysis(s: Session, case: ValidationCase, code: str, reason: str, event: str, needed: str) -> None:
    open_intervention(s, case, code=code, urgency=2, reason=reason, needed=needed)
    move_case(s, case, event, actor="sistema", why=reason)


def handle_analyze(s: Session, case: ValidationCase) -> None:
    """Resposta inicial -> dossiê (pedidos, lacunas) -> próxima etapa."""
    try:
        env, meta, sources = analysis.run_agent(s, case, "initial")
    except replay.ReplayMiss as e:
        audit(s, actor="agente", action="replay_miss", case=case)
        _fail_analysis(s, case, "REPLAY_MISS", "Não há gravação de replay para esta entrada; nenhuma análise foi inventada.",
                       "dossier_blocked", "Registrar a análise manualmente ou executar com inferência ao vivo")
        return
    except AppError as e:
        _fail_analysis(s, case, e.code, e.message, "dossier_blocked", "Revisar a entrada")
        return
    try:
        res = analysis.apply_output(s, case, env, meta, sources)
    except (ChangeSetError, AppError, ValueError) as e:
        audit(s, actor="agente", action="proposal_rejected", case=case, detail={"error": str(e), **meta})
        _fail_analysis(s, case, "PROPOSTA_INVALIDA", f"A proposta do agente foi rejeitada: {e}",
                       "dossier_blocked", "Revisar o pedido e criar a candidata manualmente")
        return
    _route_after_analysis(s, case, res, "dossier")


def _route_after_analysis(s: Session, case: ValidationCase, res: dict, prefix: str) -> None:
    cur = rounds.active_round(s, case.id)
    if cur and not rounds.open_items(s, cur.id):
        cur.status = "completed"
    iv = res.get("intervention")
    if iv:
        open_intervention(s, case, code=iv["code"], reason=iv["reason"], needed=iv.get("needed_decision", ""),
                          urgency=iv.get("urgency", 2))
        _go(s, case, prefix, "blocked", "Intervenção solicitada pelo agente")
    elif res.get("disputed"):
        open_intervention(s, case, code="LACUNA_DISPUTADA", urgency=1,
                          reason="Respostas contraditórias: o sistema não escolhe uma fonte arbitrariamente.",
                          needed="Decidir qual regra vale ou pedir esclarecimento específico")
        _go(s, case, prefix, "blocked", "Conflito entre fontes")
    elif res["blocking_open"]:
        _go(s, case, prefix, "new_round", "Lacunas abertas: nova rodada com o que falta")
    elif res.get("change_set_id"):
        _go(s, case, prefix, "changes_ready", "Candidata e testes prontos para revisão")
    else:
        why = res.get("no_safe_action") or "Sem ação segura: há pedidos ambíguos ou fora do catálogo"
        open_intervention(s, case, code="SEM_ACAO_SEGURA", urgency=2, reason=why,
                          needed="Esclarecer com a prefeitura ou decidir manualmente")
        _go(s, case, prefix, "blocked", why)


_EVENT = {
    ("dossier", "blocked"): "dossier_blocked", ("dossier", "new_round"): "dossier_needs_round",
    ("dossier", "changes_ready"): "dossier_changes_ready",
    ("reconcile", "blocked"): "reconciled_conflict", ("reconcile", "new_round"): "reconciled_new_round",
    ("reconcile", "changes_ready"): "reconciled_changes_ready",
}


def _go(s: Session, case: ValidationCase, prefix: str, kind: str, why: str) -> None:
    if prefix == "reconcile" and kind == "new_round":
        cur = rounds.active_round(s, case.id)
        if cur and rounds.open_items(s, cur.id):
            move_case(s, case, "reconciled_incomplete", actor="sistema", why="Faltam itens da rodada atual")
            case.next_action = "Aguardar o restante da resposta"
            return
    move_case(s, case, _EVENT[(prefix, kind)], actor="sistema", why=why)
    if kind == "new_round":
        enqueue(s, "plan_round", case.id, dedupe_key=f"plan:{case.id}:{case.version}")
    if kind == "changes_ready":
        case.next_action = "Revisar os testes e pedir aprovação"


# ------------------------------------------------------------ planejamento


def handle_plan_round(s: Session, case: ValidationCase) -> None:
    if case.state not in ("BUILDING_ROUND",):
        return
    rnd = rounds.plan_round(s, case)
    if rnd is None:
        gaps = s.scalars(select(Gap).where(Gap.case_id == case.id, Gap.status == "open", Gap.blocking == True))  # noqa: E712
        if not list(gaps):
            open_intervention(s, case, code="NADA_A_PERGUNTAR", urgency=2,
                              reason="Não restam lacunas para perguntar, mas o caso não avançou.",
                              needed="Revisar o caso e retomar")
            move_case(s, case, "nothing_to_ask", actor="sistema", why="Sem lacunas abertas")
            return
        move_case(s, case, "no_recipient", actor="sistema",
                  why="Nenhum responsável autorizado cobre este assunto")
        case.next_action = "Descobrir o responsável com o contato central"
        return
    move_case(s, case, "round_planned", actor="sistema", why=rnd.grouping_note)
    case.next_action = "Revisar a primeira mensagem" if (
        rounds.SETTINGS["first_message_review"] and rounds.is_first_contact(s, rnd.recipient_id)) else "Enviando a rodada"
    if rounds.SETTINGS["first_message_review"] and rounds.is_first_contact(s, rnd.recipient_id):
        audit(s, actor="sistema", action="first_message_review_required", case=case,
              detail={"round_id": rnd.id}, why="Primeira mensagem a este destinatário: revisão humana antes do envio")
        return
    rounds.release_round(s, case, rnd, "sistema")


def handle_send_round(s: Session, case: ValidationCase, round_id: str) -> None:
    from ..persistence.flow_models import ValidationRound
    rnd = s.get(ValidationRound, round_id)
    if case.state != "SENDING_ROUND" or rnd is None or rnd.status != "sending":
        return  # obsoleto: cancelado antes do efeito
    rounds.start_send(s, case, rnd)
    out = rounds.process_send(s, case, rnd)
    if out == "retry":
        n = max((o.attempts for o in _pending(s, case, rnd)), default=1)
        enqueue(s, "send_round", case.id, {"round_id": rnd.id},
                dedupe_key=f"send:{rnd.id}:{rnd.revision}:{n}",
                available_at=business_now() + timedelta(seconds=rounds.RETRY_BACKOFF[min(n - 1, 1)]))


def _pending(s, case, rnd):
    from ..persistence.models import OutboxMessage
    return [o for o in s.scalars(select(OutboxMessage).where(OutboxMessage.case_id == case.id,
                                                             OutboxMessage.kind == "send"))
            if o.payload.get("round_id") == rnd.id and o.status == "pending"]


# ------------------------------------------------------------ consolidação


def mark_consolidated(s: Session, case_id: str, upto_seq: int) -> None:
    for m in s.scalars(select(Message).where(Message.case_id == case_id, Message.consolidated == False,  # noqa: E712
                                             Message.direction == "in", Message.seq <= upto_seq)):
        m.consolidated = True
    for d in s.scalars(select(DerivedArtifact).where(DerivedArtifact.case_id == case_id,
                                                     DerivedArtifact.consolidated == False)):  # noqa: E712
        d.consolidated = True
    for h in s.scalars(select(HumanDecision).where(HumanDecision.case_id == case_id,
                                                   HumanDecision.consolidated == False)):  # noqa: E712
        h.consolidated = True


def handle_consolidate(s: Session, case: ValidationCase) -> None:
    if case.state != "PROCESSING_REPLY":
        return
    prev = case.resume_state
    last_seq = max([m.seq for m in s.scalars(select(Message).where(Message.case_id == case.id))] or [0])
    move_case(s, case, "evidence_validated", actor="sistema", why="Evidências persistidas e validadas")
    try:
        env, meta, sources = analysis.run_agent(s, case, "reconcile")
    except replay.ReplayMiss:
        audit(s, actor="agente", action="replay_miss", case=case)
        open_intervention(s, case, code="REPLAY_MISS", urgency=2,
                          reason="Não há gravação de replay para estas respostas; nenhuma análise foi inventada.",
                          needed="Decidir manualmente com base nas respostas recebidas")
        move_case(s, case, "reconciled_conflict", actor="sistema", why="Replay sem correspondência")
        mark_consolidated(s, case.id, last_seq)
        return
    except AppError as e:
        open_intervention(s, case, code=e.code, reason=e.message, urgency=2)
        move_case(s, case, "reconciled_conflict", actor="sistema", why=e.message)
        return
    try:
        res = analysis.apply_output(s, case, env, meta, sources)
    except (ChangeSetError, AppError, ValueError) as e:
        audit(s, actor="agente", action="proposal_rejected", case=case, detail={"error": str(e), **meta})
        open_intervention(s, case, code="PROPOSTA_INVALIDA", urgency=2, reason=f"A proposta do agente foi rejeitada: {e}",
                          needed="Revisar as respostas e decidir")
        move_case(s, case, "reconciled_conflict", actor="sistema", why="Proposta inválida")
        mark_consolidated(s, case.id, last_seq)
        return
    mark_consolidated(s, case.id, last_seq)
    material = bool(res["answered"] or res["new_gaps"] or res.get("change_set_id") or res.get("intervention")
                    or res.get("disputed"))
    if prev and not material and prev in ("READY_FOR_APPROVAL", "WAITING_MUNICIPAL_APPROVAL",
                                           "WAITING_IMPLANTER_APPROVAL", "CHANGES_READY"):
        # evidência sem efeito sobre a candidata: restaura o estado anterior, aprovações intactas
        _restore(s, case, prev)
        return
    if prev and not res.get("change_set_id") and prev in ("WAITING_MUNICIPAL_APPROVAL", "WAITING_IMPLANTER_APPROVAL",
                                                         "READY_FOR_APPROVAL"):
        from .changes import invalidate_approvals
        cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == case.id).order_by(ChangeSet.created_at.desc()))
        if cs and cs.status not in ("applied", "verified", "superseded"):
            invalidate_approvals(s, cs, case, reason="Evidência nova alterou o entendimento do caso", actor="sistema")
    case.resume_state = None
    _route_after_analysis(s, case, res, "reconcile")
    if res.get("change_set_id"):
        case.next_action = "Revisar os testes e pedir aprovação"
    # chegou mais evidência durante a análise: nova rodada de consolidação
    if messaging.pending_evidence(s, case.id) and case.state in ("CHANGES_READY", "WAITING_PRIMARY_CHANNEL",
                                                                 "WAITING_ANY_CHANNEL"):
        messaging.kick(s, case)


def _restore(s: Session, case: ValidationCase, prev: str) -> None:
    from sqlalchemy import update
    s.flush()
    res = s.execute(update(ValidationCase).where(ValidationCase.id == case.id, ValidationCase.version == case.version)
                    .values(state=prev, version=case.version + 1, state_since=business_now()))
    if res.rowcount != 1:
        raise AppError("VERSION_CONFLICT", "o caso mudou durante a consolidação", 409)
    s.refresh(case)
    case.resume_state = None
    audit(s, actor="sistema", action="state_restored", case=case, to_state=prev,
          why="A nova evidência não altera a candidata; o estado anterior e as aprovações foram mantidos")
