"""Erros, auditoria, transições com revisão otimista e permissões (v2 §3, §9, §13.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..clock import business_now
from ..domain.states import CaseState, InvalidTransition, can_resume_to, transition
from ..persistence.models import (
    Actor, AuditEvent, Intervention, ProcessDefinition, RoleAssignment, ValidationCase, WorkItem, new_id,
)


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 409, details: dict | None = None,
                 retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details, self.retryable = details or {}, retryable


def audit(s: Session, *, actor: str, action: str, case: ValidationCase | None = None,
          from_state: str | None = None, to_state: str | None = None,
          detail: dict | None = None, why: str = "", municipality_id: str | None = None) -> AuditEvent:
    seq = (s.scalar(select(func.max(AuditEvent.seq))) or 0) + 1
    ev = AuditEvent(
        seq=seq, case_id=case.id if case else None,
        municipality_id=case.municipality_id if case else municipality_id,
        actor=actor, action=action, from_state=from_state, to_state=to_state,
        case_version=case.version if case else None, detail=detail or {}, why=why,
        created_at=business_now(),
    )
    s.add(ev)
    return ev


def _bump(s: Session, case: ValidationCase, new_state: CaseState, expected_version: int | None) -> None:
    """Atualização condicional por revisão: dois comandos com a mesma revisão => um commit (T01)."""
    s.flush()  # grava alterações pendentes do caso antes da atualização condicional
    expected = expected_version if expected_version is not None else case.version
    res = s.execute(
        update(ValidationCase)
        .where(ValidationCase.id == case.id, ValidationCase.version == expected)
        .values(state=new_state.value, version=expected + 1, state_since=business_now())
    )
    if res.rowcount != 1:
        raise AppError("VERSION_CONFLICT", "o caso mudou; recarregue e decida novamente", 409,
                       {"case_id": case.id}, retryable=False)
    s.refresh(case)


def move_case(s: Session, case: ValidationCase, event: str, *, actor: str, why: str = "",
              expected_version: int | None = None, detail: dict | None = None) -> CaseState:
    old = CaseState(case.state)
    try:
        dest = transition(old, event)
    except InvalidTransition as e:
        raise AppError("INVALID_TRANSITION", str(e), 409, {"state": old.value, "event": event}) from e
    _bump(s, case, dest, expected_version)
    audit(s, actor=actor, action=event, case=case, from_state=old.value, to_state=dest.value,
          detail=detail, why=why)
    return dest


def pause_case(s: Session, case: ValidationCase, *, actor: str, expected_version: int | None = None,
               why: str = "") -> None:
    old = CaseState(case.state)
    resume = old.value
    move_case(s, case, "pause", actor=actor, why=why, expected_version=expected_version)
    case.resume_state = resume


def safe_resume_target(s: Session, case: ValidationCase) -> CaseState | None:
    """Estado seguro calculado após revalidar pendências; o cliente nunca escolhe o destino (v2 §9.2)."""
    from ..persistence.flow_models import Gap
    from . import messaging
    if messaging.pending_evidence(s, case.id):
        return CaseState.PROCESSING_REPLY
    if s.scalar(select(Gap).where(Gap.case_id == case.id, Gap.status == "open", Gap.blocking == True)):  # noqa: E712
        return CaseState.BUILDING_ROUND
    from ..persistence.models import ChangeSet
    cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == case.id).order_by(ChangeSet.created_at.desc()))
    if cs is not None and cs.status in ("draft", "ready", "rejected"):
        return CaseState.CHANGES_READY
    return None


def resume_case(s: Session, case: ValidationCase, *, actor: str, expected_version: int | None,
                why: str = "") -> CaseState:
    old = CaseState(case.state)
    if old not in (CaseState.PAUSED, CaseState.BLOCKED_HUMAN, CaseState.FAILED_RETRYABLE):
        raise AppError("INVALID_TRANSITION", "o caso não está pausado nem aguardando decisão", 409)
    if open_interventions(s, case.id):
        raise AppError("INTERVENTION_OPEN", "resolva as intervenções abertas antes de retomar", 409)
    stored = CaseState(case.resume_state) if case.resume_state else None
    if old == CaseState.PAUSED and stored:
        target = stored
    else:
        target = safe_resume_target(s, case)
    if target is None:
        raise AppError("NOTHING_TO_RESUME", "não há um estado seguro para retomar; crie uma candidata ou nova rodada", 409)
    from . import messaging, rounds
    from datetime import timedelta
    paused_for = business_now() - (case.state_since.replace(tzinfo=business_now().tzinfo)
                                   if case.state_since.tzinfo is None else case.state_since)
    _bump(s, case, target, expected_version)
    audit(s, actor=actor, action="resume", case=case, from_state=old.value, to_state=target.value, why=why)
    case.resume_state = None
    if old == CaseState.PAUSED:
        rounds.shift_deadlines(s, case.id, paused_for if paused_for > timedelta(0) else timedelta(0))
    if target == CaseState.PROCESSING_REPLY:
        messaging.schedule_consolidation(s, case, timedelta(seconds=messaging.QUIET_SECONDS))
    elif target == CaseState.BUILDING_ROUND:
        enqueue(s, "plan_round", case.id, dedupe_key=f"plan:{case.id}:{case.version}")
    elif messaging.pending_evidence(s, case.id) and target in (CaseState.WAITING_ANY_CHANNEL, CaseState.WAITING_PRIMARY_CHANNEL):
        messaging.kick(s, case)
    return target


def open_interventions(s: Session, case_id: str) -> list[Intervention]:
    return list(s.scalars(select(Intervention).where(Intervention.case_id == case_id,
                                                     Intervention.status == "open")))


def open_intervention(s: Session, case: ValidationCase, *, code: str, reason: str, needed: str = "",
                      urgency: int = 2) -> Intervention:
    iv = Intervention(case_id=case.id, municipality_id=case.municipality_id, reason_code=code,
                      reason=reason, needed_decision=needed, urgency=urgency, created_at=business_now())
    s.add(iv)
    case.blocked_reason = reason
    audit(s, actor="sistema", action="intervention_opened", case=case, detail={"code": code}, why=reason)
    return iv


def enqueue(s: Session, kind: str, case_id: str | None, payload: dict | None = None,
            dedupe_key: str | None = None, available_at: datetime | None = None) -> WorkItem | None:
    if dedupe_key and s.scalar(select(WorkItem).where(WorkItem.dedupe_key == dedupe_key)):
        return None
    w = WorkItem(case_id=case_id, kind=kind, payload=payload or {}, dedupe_key=dedupe_key,
                 available_at=available_at or business_now())
    s.add(w)
    return w


# ------------------------------------------------------------ permissões


def get_actor(s: Session, actor_id: str) -> Actor:
    a = s.get(Actor, actor_id)
    if a is None:
        raise AppError("UNAUTHENTICATED", "persona inválida", 401)
    return a


def has_role(s: Session, actor: Actor, role: str, process: ProcessDefinition | None = None) -> bool:
    """Papel vem do servidor, nunca do cliente (I07, I18). Papel de outro município não vale."""
    q = select(RoleAssignment).where(
        RoleAssignment.actor_id == actor.id, RoleAssignment.role == role, RoleAssignment.revoked_at.is_(None)
    )
    for ra in s.scalars(q):
        if process is None:
            return True
        if ra.process_id is None and ra.municipality_id is None:
            return True  # papel global (implantador / aprovador Aprova)
        if ra.process_id == process.id:
            return True
        if ra.process_id is None and ra.municipality_id == process.municipality_id:
            return True
    return False


def require_role(s: Session, actor: Actor, role: str, process: ProcessDefinition | None = None) -> None:
    if not has_role(s, actor, role, process):
        raise AppError("FORBIDDEN", "papel insuficiente para esta ação", 403)


def short_id() -> str:
    return new_id()
