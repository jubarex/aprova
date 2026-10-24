"""Executa passos de roteiro (modo apresentação): reproduz exatamente as entradas gravadas."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..persistence.flow_models import ContactReferral
from ..persistence.models import Actor, ValidationCase
from ..scenarios import SCENARIOS
from . import attachments, decisions, messaging, people
from .common import AppError
from .rounds import active_round


def scenario_of(s: Session, case: ValidationCase) -> str | None:
    for sid, sc in SCENARIOS.items():
        if sc["process_id"] == case.process_id:
            return sid
    return None


def run_step(s: Session, att_dir: Path, case: ValidationCase, step_id: str, implanter: Actor) -> dict:
    sid = scenario_of(s, case)
    if sid is None:
        raise AppError("NOT_FOUND", "este processo não tem roteiro", 404)
    step = next((x for x in SCENARIOS[sid]["steps"] if x["id"] == step_id), None)
    if step is None:
        raise AppError("NOT_FOUND", "passo inexistente", 404)
    t = step["type"]
    key = f"script:{case.id}:{step['id']}"
    if t == "message":
        actor_id = step["actor"]
        if actor_id == "@referral":
            rf = s.scalar(select(ContactReferral).where(ContactReferral.case_id == case.id,
                                                        ContactReferral.status == "authorized")
                          .order_by(ContactReferral.created_at.desc()))
            if rf is None or not rf.new_actor_id:
                raise AppError("INVALID_TRANSITION", "a pessoa indicada ainda não foi autorizada", 409)
            actor_id = rf.new_actor_id
        actor = s.get(Actor, actor_id)
        rnd = active_round(s, case.id)
        if step["channel"] == "pylon":
            out = messaging.pylon_webhook(s, case, actor, external_key=key, body=step["text"])
            return {"step": step_id, **out}
        att = step.get("attachment")
        m, created = messaging.ingest(s, case, actor, channel=step["channel"], body=step["text"], external_key=key,
                                      reply_to_round_id=rnd.id if rnd else None, has_attachment=bool(att))
        if att and created:
            attachments.store(s, att_dir, case, m, att["filename"], att["content"].encode("utf-8"),
                              att.get("sidecar"))
        return {"step": step_id, "message_id": m.id, "created": created, "substantive": m.substantive}
    if t == "referral":
        actor = s.get(Actor, step["actor"])
        rf = people.request_referral(s, case, actor, name=step["name"], sector=step.get("sector", ""),
                                     alias=step.get("alias", ""), topic=step.get("topic", "geral"))
        return {"step": step_id, "referral_id": rf.id}
    if t == "authorize_referral":
        rf = s.scalar(select(ContactReferral).where(ContactReferral.case_id == case.id,
                                                    ContactReferral.status == "pending")
                      .order_by(ContactReferral.created_at.desc()))
        if rf is None:
            raise AppError("NOT_FOUND", "não há indicação pendente", 404)
        people.authorize_referral(s, rf, implanter)
        return {"step": step_id, "referral_id": rf.id, "actor_id": rf.new_actor_id}
    if t == "decision":
        from ..persistence.models import Intervention
        iv = s.scalar(select(Intervention).where(Intervention.case_id == case.id, Intervention.status == "open")
                      .order_by(Intervention.created_at))
        hd = decisions.record(s, case, implanter.id, kind=step["kind"], text=step["text"],
                              intervention_id=iv.id if iv else None)
        return {"step": step_id, "decision_id": hd.id}
    raise AppError("VALIDATION_ERROR", "tipo de passo desconhecido", 422)
