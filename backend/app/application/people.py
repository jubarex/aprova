"""Descoberta de responsável: indicação, autorização com escopo, repasse restrito e mesclagem (v2 §8.3)."""

from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..persistence.flow_models import ContactReferral, Gap, RoundItem, ValidationRound
from ..persistence.models import Actor, RoleAssignment, ValidationCase, new_id
from .common import AppError, audit, enqueue, move_case, require_role
from . import rounds


def _slug(name: str) -> str:
    t = unicodedata.normalize("NFKD", name.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:24]


def request_referral(s: Session, case: ValidationCase, from_actor: Actor, *, name: str, sector: str = "",
                     alias: str = "", topic: str = "geral", gap_ids: list[str] | None = None) -> ContactReferral:
    """Registra quem indicou quem e o assunto. Receber um alias NÃO concede autorização."""
    if from_actor.municipality_id != case.municipality_id:
        raise AppError("NOT_FOUND", "recurso fora do escopo", 404)
    if not name.strip():
        raise AppError("VALIDATION_ERROR", "informe o nome de quem sabe", 422)
    ids = gap_ids or []
    valid = {g.id for g in s.scalars(select(Gap).where(Gap.case_id == case.id, Gap.status == "open"))}
    if any(i not in valid for i in ids):
        raise AppError("NOT_FOUND", "lacuna fora do escopo do caso", 404)
    if not ids:
        ids = [g.id for g in s.scalars(select(Gap).where(Gap.case_id == case.id, Gap.status == "open",
                                                        Gap.topic == topic))] or sorted(valid)
    rf = ContactReferral(id=new_id("rf_"), case_id=case.id, municipality_id=case.municipality_id,
                         from_actor_id=from_actor.id, name=name.strip(), sector=sector, alias=alias, topic=topic,
                         gap_ids=ids)
    s.add(rf)
    s.flush()
    audit(s, actor=from_actor.id, action="referral_requested", case=case,
          detail={"referral_id": rf.id, "name": rf.name, "topic": topic, "gaps": len(ids)},
          why=f"{from_actor.name} indicou {rf.name}; falta a autorização de um responsável da Aprova")
    if case.state in ("WAITING_ANY_CHANNEL", "WAITING_PRIMARY_CHANNEL", "RECONCILING_RESPONSES", "WAITING_OWNER"):
        move_case(s, case, "referral_requested", actor=from_actor.id, why="Indicação aguardando autorização")
        case.next_action = "Autorizar a pessoa indicada"
    return rf


def authorize_referral(s: Session, rf: ContactReferral, implanter: Actor, *, decision: str = "authorize") -> ContactReferral:
    case = s.get(ValidationCase, rf.case_id)
    require_role(s, implanter, "implanter")
    if rf.status != "pending":
        raise AppError("ALREADY_DECIDED", "indicação já decidida", 409)
    if decision == "reject":
        rf.status, rf.decided_by = "rejected", implanter.id
        audit(s, actor=implanter.id, action="referral_rejected", case=case, detail={"referral_id": rf.id},
              why="Indicação recusada; o caso volta ao responsável anterior")
        if case.state == "WAITING_REFERRAL":
            move_case(s, case, "referral_rejected", actor=implanter.id, why="Indicação recusada")
            enqueue(s, "plan_round", case.id, dedupe_key=f"plan:{case.id}:{case.version}")
        return rf
    # a pessoa indicada vira contato da prefeitura, com papel e escopo explícitos
    existing = s.scalar(select(Actor).where(Actor.municipality_id == rf.municipality_id, Actor.name == rf.name,
                                            Actor.merged_into.is_(None)))
    actor = existing or Actor(id=f"act_{_slug(rf.name)}_{new_id()[:4]}", name=rf.name, kind="contato",
                              municipality_id=rf.municipality_id, preferred_channel="whatsapp",
                              aliases=[a for a in [rf.alias] if a])
    if existing is None:
        s.add(actor)
        s.flush()
    s.add(RoleAssignment(actor_id=actor.id, process_id=case.process_id, municipality_id=rf.municipality_id,
                         role="responder", topic=rf.topic))
    rf.status, rf.new_actor_id, rf.decided_by = "authorized", actor.id, implanter.id
    s.flush()
    audit(s, actor=implanter.id, action="contact_authorized", case=case,
          detail={"referral_id": rf.id, "actor_id": actor.id, "topic": rf.topic},
          why=f"{actor.name} autorizado(a) a responder apenas sobre {rf.topic} neste processo")
    if case.state in ("WAITING_REFERRAL", "WAITING_OWNER"):
        move_case(s, case, "contact_authorized", actor=implanter.id, why="Contato autorizado; replanejando a rodada")
        enqueue(s, "plan_round", case.id, dedupe_key=f"plan:{case.id}:{case.version}")
        case.next_action = "Montar a rodada para a pessoa indicada"
    return rf


def authorize_owner(s: Session, case: ValidationCase, implanter: Actor, *, name: str, topic: str,
                    existing_actor_id: str | None = None) -> Actor:
    """Quando não há responsável para o assunto (WAITING_OWNER): o implantador autoriza alguém conhecido."""
    require_role(s, implanter, "implanter")
    if existing_actor_id:
        actor = s.get(Actor, existing_actor_id)
        if not actor or actor.municipality_id != case.municipality_id:
            raise AppError("NOT_FOUND", "contato fora do escopo", 404)
    else:
        actor = Actor(id=f"act_{_slug(name)}_{new_id()[:4]}", name=name, kind="contato",
                      municipality_id=case.municipality_id, preferred_channel="whatsapp")
        s.add(actor)
        s.flush()
    s.add(RoleAssignment(actor_id=actor.id, process_id=case.process_id, municipality_id=case.municipality_id,
                         role="responder", topic=topic))
    s.flush()
    audit(s, actor=implanter.id, action="contact_authorized", case=case, detail={"actor_id": actor.id, "topic": topic},
          why=f"{actor.name} autorizado(a) sobre {topic}")
    if case.state in ("WAITING_OWNER", "WAITING_REFERRAL"):
        move_case(s, case, "contact_authorized", actor=implanter.id, why="Responsável definido")
        enqueue(s, "plan_round", case.id, dedupe_key=f"plan:{case.id}:{case.version}")
    return actor


def merge_contacts(s: Session, keep: Actor, drop: Actor, implanter: Actor, confirm: bool) -> Actor:
    """Mesclagem só com confirmação humana, mesmo município e aliases preservados (nunca por semelhança)."""
    require_role(s, implanter, "implanter")
    if not confirm:
        raise AppError("CONFIRMATION_REQUIRED", "a mesclagem exige confirmação humana", 400)
    if keep.municipality_id != drop.municipality_id or keep.id == drop.id:
        raise AppError("FORBIDDEN", "só é possível mesclar contatos do mesmo município", 403)
    keep.aliases = sorted(set((keep.aliases or []) + (drop.aliases or []) + [drop.name]))
    drop.merged_into = keep.id
    for ra in s.scalars(select(RoleAssignment).where(RoleAssignment.actor_id == drop.id)):
        ra.actor_id = keep.id
    audit(s, actor=implanter.id, action="contacts_merged", detail={"keep": keep.id, "drop": drop.id},
          municipality_id=keep.municipality_id, why=f"{drop.name} mesclado(a) em {keep.name}; aliases preservados")
    return keep


def set_preferred_channel(s: Session, case_id: str | None, actor: Actor, channel: str) -> None:
    """Preferência explícita do contato prevalece sobre a primeira resposta (v2 §8.2)."""
    from ..persistence.flow_models import ChannelDecision
    if channel not in ("pylon", "whatsapp", "portal"):
        raise AppError("VALIDATION_ERROR", "canal inválido", 422)
    actor.preferred_channel = channel
    if case_id:
        cd = s.scalar(select(ChannelDecision).where(ChannelDecision.case_id == case_id,
                                                    ChannelDecision.actor_id == actor.id))
        if cd:
            cd.channel, cd.reason = channel, "preferencia_explicita"
        else:
            s.add(ChannelDecision(case_id=case_id, actor_id=actor.id, channel=channel, reason="preferencia_explicita"))
    audit(s, actor=actor.id, action="preferred_channel_set", detail={"channel": channel},
          municipality_id=actor.municipality_id, why="Preferência explícita de canal registrada")
