"""Decisões humanas: viram evidência e retomam o fluxo (v2 §9.3, §6)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import business_now
from ..persistence.flow_models import Gap, HumanDecision
from ..persistence.models import ChangeRequest, Intervention, ValidationCase
from .common import AppError, audit, move_case, open_interventions, resume_case
from . import messaging

KINDS = ("resolve_conflict", "provide_answer", "fix_interpretation", "dispose_request")


def record(s: Session, case: ValidationCase, actor_id: str, *, kind: str, text: str, payload: dict | None = None,
           intervention_id: str | None = None, expected_version: int | None = None) -> HumanDecision:
    if kind not in KINDS:
        raise AppError("VALIDATION_ERROR", "tipo de decisão inválido", 422)
    if len(text.strip()) < 3:
        raise AppError("RATIONALE_REQUIRED", "informe a decisão e a justificativa", 422)
    payload = payload or {}
    if expected_version is not None and case.version != expected_version:
        raise AppError("VERSION_CONFLICT", "o caso mudou; recarregue e decida novamente", 409)
    if kind == "dispose_request":
        cr = s.get(ChangeRequest, payload.get("request_id", ""))
        disp = payload.get("disposition")
        if not cr or cr.case_id != case.id or disp not in ("rejected", "withdrawn", "accepted"):
            raise AppError("VALIDATION_ERROR", "pedido ou disposição inválidos", 422)
        cr.disposition = disp  # rejeitar/retirar exige decisão humana justificada; nunca infla a taxa de sucesso
    if kind == "resolve_conflict":
        disputed = list(s.scalars(select(Gap).where(Gap.case_id == case.id, Gap.status == "disputed")))
        if not disputed:
            raise AppError("INVALID_TRANSITION", "não há lacuna disputada neste caso", 409)
        for g in disputed:
            g.status = "open"  # reaberta: a decisão humana entra como fonte na próxima reconciliação
    hd = HumanDecision(case_id=case.id, actor_id=actor_id, kind=kind, text=text.strip(), payload=payload,
                       created_at=business_now())
    s.add(hd)
    s.flush()
    audit(s, actor=actor_id, action="human_decision", case=case, detail={"decision_id": hd.id, "kind": kind},
          why=text.strip()[:300])
    if intervention_id:
        iv = s.get(Intervention, intervention_id)
        if not iv or iv.case_id != case.id:
            raise AppError("NOT_FOUND", "intervenção fora do escopo", 404)
        if iv.status == "open":
            iv.status, iv.resolution, iv.resolved_by, iv.resolved_at = "resolved", text.strip(), actor_id, business_now()
            audit(s, actor=actor_id, action="intervention_resolved", case=case, why=text.strip()[:300])
    # com a intervenção resolvida e evidência pendente, retoma consolidando (nunca escolhe destino arbitrário)
    if case.state == "BLOCKED_HUMAN" and not open_interventions(s, case.id):
        resume_case(s, case, actor=actor_id, expected_version=None, why="Decisão humana registrada")
    elif case.state in ("CHANGES_READY", "WAITING_MUNICIPAL_APPROVAL", "WAITING_IMPLANTER_APPROVAL"):
        messaging.kick(s, case)
    return hd
