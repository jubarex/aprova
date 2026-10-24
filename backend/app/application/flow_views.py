"""Projeções do fluxo de rodadas: lacunas, rodadas, conversa, indicações, Caixa de entrada e Portal."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import business_now
from ..persistence.flow_models import (
    Attachment, ContactReferral, DerivedArtifact, Gap, HumanDecision, Message, RoundItem, ValidationRound,
)
from ..persistence.models import Actor, Municipality, ProcessDefinition, Ticket, ValidationCase
from ..scenarios import SCENARIOS
from .rounds import compose_message, open_items
from .views import _utc, deadline_dto, municipality_dto


def gaps_view(s: Session, case_id: str) -> list[dict]:
    rows = s.scalars(select(Gap).where(Gap.case_id == case_id).order_by(Gap.created_at))
    return sorted(({"id": g.id, "ref": g.ref, "question": g.question, "answer_kind": g.answer_kind,
                    "options": g.options, "topic": g.topic, "status": g.status, "blocking": g.blocking,
                    "note": g.note, "answer_evidence_ids": g.answer_evidence_ids} for g in rows),
                  key=lambda g: int(g["ref"][1:]))


def rounds_view(s: Session, case_id: str) -> list[dict]:
    out = []
    for r in s.scalars(select(ValidationRound).where(ValidationRound.case_id == case_id).order_by(ValidationRound.seq)):
        who = s.get(Actor, r.recipient_id)
        case = s.get(ValidationCase, case_id)
        items = list(s.scalars(select(RoundItem).where(RoundItem.round_id == r.id).order_by(RoundItem.position)))
        out.append({
            "id": r.id, "seq": r.seq, "status": r.status, "revision": r.revision, "objective": r.objective,
            "summary": r.summary, "grouping_note": r.grouping_note,
            "recipient": {"id": who.id, "name": who.name}, "channels": r.channels,
            "sent_at": _utc(r.sent_at).isoformat() if r.sent_at else None, "reminders_sent": r.reminders_sent,
            "items": [{"id": i.id, "position": i.position, "question": i.question, "status": i.status,
                       "answer_kind": i.answer_kind, "options": i.options,
                       "due_at": _utc(i.due_at).isoformat() if i.due_at else None} for i in items],
            "preview": compose_message(s, case, r, [i for i in items if i.status == "open"]) if r.status in ("ready", "sending") else None,
            "awaiting_review": r.status == "ready" and case.state == "ROUND_READY",
        })
    return out


def conversation_view(s: Session, case_id: str, include_internal: bool = True) -> list[dict]:
    out = []
    for m in s.scalars(select(Message).where(Message.case_id == case_id).order_by(Message.seq)):
        who = s.get(Actor, m.actor_id) if m.actor_id else None
        atts = [{"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size,
                 "status": a.status} for a in s.scalars(select(Attachment).where(Attachment.message_id == m.id))]
        derived = []
        for a in s.scalars(select(Attachment).where(Attachment.message_id == m.id)):
            for d in s.scalars(select(DerivedArtifact).where(DerivedArtifact.attachment_id == a.id)):
                derived.append({"id": d.id, "adapter": d.adapter, "simulated": d.simulated, "status": d.status,
                                "text": d.text[:500]})
        out.append({
            "id": m.id, "seq": m.seq, "channel": m.channel, "direction": m.direction, "body": m.body,
            "actor": {"id": who.id, "name": who.name} if who else None, "round_id": m.round_id,
            "substantive": m.substantive, "flagged": m.flagged, "triage": m.triage_status,
            "mirror": m.mirror_of_message_id is not None, "consolidated": m.consolidated,
            "at": _utc(m.received_at).isoformat(), "attachments": atts, "derived": derived,
        })
    return out


def referrals_view(s: Session, case_id: str) -> list[dict]:
    out = []
    for r in s.scalars(select(ContactReferral).where(ContactReferral.case_id == case_id).order_by(ContactReferral.created_at)):
        frm = s.get(Actor, r.from_actor_id)
        out.append({"id": r.id, "name": r.name, "sector": r.sector, "alias": r.alias, "topic": r.topic,
                    "status": r.status, "from": {"id": frm.id, "name": frm.name} if frm else None,
                    "gaps": r.gap_ids, "new_actor_id": r.new_actor_id})
    return out


def decisions_view(s: Session, case_id: str) -> list[dict]:
    return [{"id": d.id, "kind": d.kind, "text": d.text, "actor_id": d.actor_id, "at": _utc(d.created_at).isoformat()}
            for d in s.scalars(select(HumanDecision).where(HumanDecision.case_id == case_id).order_by(HumanDecision.created_at))]


def inbox(s: Session, client: str | None, only_triage: bool) -> list[dict]:
    q = select(Message).where(Message.direction == "in", Message.mirror_of_message_id.is_(None))
    if client:
        q = q.where(Message.municipality_id == client)
    if only_triage:
        q = q.where(Message.triage_status == "pending")
    out = []
    for m in s.scalars(q.order_by(Message.seq.desc()).limit(200)):
        c = s.get(ValidationCase, m.case_id)
        p = s.get(ProcessDefinition, c.process_id)
        who = s.get(Actor, m.actor_id) if m.actor_id else None
        out.append({"id": m.id, "channel": m.channel, "body": m.body, "case_id": c.id,
                    "municipality": municipality_dto(s.get(Municipality, c.municipality_id)),
                    "process": {"code": p.code, "name": p.name}, "actor": who.name if who else None,
                    "substantive": m.substantive, "flagged": m.flagged, "triage": m.triage_status,
                    "round_id": m.round_id, "at": _utc(m.received_at).isoformat(), "case_state": c.state})
    return out


# ------------------------------------------------------------------ Portal


def portal_items(s: Session, actor: Actor) -> list[dict]:
    """Perguntas abertas das rodadas ativas de que a pessoa é destinatária (somente do seu município)."""
    out = []
    for r in s.scalars(select(ValidationRound).where(ValidationRound.recipient_id == actor.id,
                                                     ValidationRound.status == "waiting")):
        case = s.get(ValidationCase, r.case_id)
        if case.municipality_id != actor.municipality_id:
            continue
        p = s.get(ProcessDefinition, case.process_id)
        for it in open_items(s, r.id):
            out.append({
                "id": it.id, "round_id": r.id, "case_id": case.id, "process": {"code": p.code, "name": p.name},
                "question": it.question, "why": it.why, "answer_kind": it.answer_kind, "options": it.options,
                "deadline": deadline_dto(it.due_at), "position": it.position,
                "total": len(open_items(s, r.id)), "demo_hint": demo_hint(s, case, actor, "portal"),
            })
    out.sort(key=lambda x: (x["deadline"]["days"] if x["deadline"]["days"] is not None else 999, x["position"]))
    return out


def demo_hint(s: Session, case: ValidationCase, actor: Actor, channel: str) -> str | None:
    """Texto de roteiro (modo demonstração): só existe para o passo ainda não executado deste contato/canal."""
    for sid, sc in SCENARIOS.items():
        if sc["process_id"] != case.process_id:
            continue
        for st in sc["steps"]:
            if st.get("type") != "message" or st.get("actor") != actor.id or st.get("channel") != channel:
                continue
            done = s.scalar(select(Message).where(Message.case_id == case.id,
                                                  Message.external_key == f"script:{case.id}:{st['id']}"))
            if not done:
                return st["text"]
    return None
