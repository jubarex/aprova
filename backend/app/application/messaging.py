"""Recepção multicanal: persistir antes de interpretar, correlacionar sem adivinhar, consolidar em janela (v2 §8.2, §10.1)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import business_now
from ..domain.states import CaseState
from ..persistence.flow_models import (
    Attachment, ChannelDecision, DerivedArtifact, HumanDecision, Message, RoundItem, ValidationRound,
)
from ..persistence.models import Actor, EffectReceipt, Ticket, TicketComment, ValidationCase, WorkItem
from .common import AppError, audit, enqueue, has_role, move_case, open_intervention
from .rounds import next_seq

QUIET_SECONDS = 2  # rajada: consolida 2 s após o último recebimento
MAX_WINDOW_SECONDS = 10  # teto desde o primeiro recebimento
CHANNELS = ("pylon", "whatsapp", "portal")

ACK = {"ok", "okay", "certo", "blz", "beleza", "obrigado", "obrigada", "valeu", "recebido", "entendi",
       "combinado", "show", "perfeito", "joia", "depois vejo", "vou ver", "vou olhar", "ja vejo", "bom dia",
       "boa tarde", "boa noite", "ola", "oi", "sim obrigado", "ok obrigado", "ok obrigada", "tudo bem"}
INJECTION = re.compile(
    r"(ignore|desconsidere|esque[cç]a).{0,40}(instru[cç][oõ]es|regras|prompt)|aprove (automaticamente|esta|a vers)|"
    r"voc[eê] agora [eé]|system prompt|<\s*system\s*>|autorize (o contato|este contato)|feche o ticket|"
    r"apague|delete (the|all)|reveal .{0,20}(prompt|key)", re.I)


def normalize(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", t).split())


def is_substantive(body: str, has_attachment: bool = False) -> bool:
    """Substantiva altera intenção, lacuna, responsável ou decisão; 'ok' e recibo não encerram espera."""
    if has_attachment:
        return True
    n = normalize(body)
    return bool(n) and n not in ACK


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION.search(text or ""))


def authorized_responder(s: Session, actor: Actor, case: ValidationCase) -> bool:
    from ..persistence.models import ProcessDefinition
    p = s.get(ProcessDefinition, case.process_id)
    return actor.municipality_id == case.municipality_id and (
        has_role(s, actor, "responder", p) or has_role(s, actor, "municipal_approver", p))


def ingest(s: Session, case: ValidationCase, actor: Actor, *, channel: str, body: str, external_key: str | None,
           reply_to_round_id: str | None = None, round_item_id: str | None = None,
           has_attachment: bool = False) -> tuple[Message, bool]:
    """Persiste a mensagem (I02). Devolve (mensagem, criada_agora). Repetição idêntica devolve a original."""
    if channel not in CHANNELS:
        raise AppError("VALIDATION_ERROR", "canal inválido", 422)
    if actor.municipality_id != case.municipality_id:
        raise AppError("NOT_FOUND", "recurso fora do escopo", 404)
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if external_key:
        prior = s.scalar(select(Message).where(Message.channel == channel, Message.external_key == external_key))
        if prior:
            if prior.body_hash != h or prior.case_id != case.id:
                raise AppError("IDEMPOTENCY_CONFLICT", "a chave externa já foi usada com outro conteúdo", 409)
            return prior, False
    authorized = authorized_responder(s, actor, case)
    rnd_id = None
    item_id = None
    if round_item_id:
        it = s.get(RoundItem, round_item_id)
        rnd = s.get(ValidationRound, it.round_id) if it else None
        if not it or not rnd or rnd.case_id != case.id or rnd.recipient_id != actor.id:
            raise AppError("NOT_FOUND", "item de rodada fora do escopo", 404)
        rnd_id, item_id = rnd.id, it.id
    elif reply_to_round_id:
        rnd = s.get(ValidationRound, reply_to_round_id)
        if not rnd or rnd.case_id != case.id:
            raise AppError("NOT_FOUND", "rodada fora do escopo", 404)
        rnd_id = rnd.id
    sub = is_substantive(body, has_attachment) and authorized
    flagged = looks_like_injection(body)
    m = Message(seq=next_seq(s), case_id=case.id, municipality_id=case.municipality_id, actor_id=actor.id,
                channel=channel, direction="in", body=body, body_hash=h, round_id=rnd_id, round_item_id=item_id,
                external_key=external_key, substantive=sub, flagged=flagged, received_at=business_now(),
                triage_status="pending" if (sub and rnd_id is None) else None)
    s.add(m)
    s.flush()
    audit(s, actor=actor.id, action="message_received", case=case,
          detail={"message_id": m.id, "channel": channel, "round_id": rnd_id, "substantive": sub},
          why="Mensagem persistida antes da interpretação")
    if not authorized:
        open_intervention(s, case, code="CONTATO_NAO_AUTORIZADO", urgency=2,
                          reason=f"{actor.name} escreveu, mas não tem autorização para este assunto. A mensagem foi guardada e não foi usada.",
                          needed="Decidir se autoriza o contato ou ignora a mensagem")
    if flagged:
        m.substantive = False
        open_intervention(s, case, code="INSTRUCAO_SUSPEITA", urgency=1,
                          reason="A mensagem contém um trecho que tenta dar ordens ao sistema. Ele foi tratado como texto, sem efeito.",
                          needed="Revisar a mensagem")
        audit(s, actor="sistema", action="injection_flagged", case=case, detail={"message_id": m.id})
    if m.substantive:
        _on_substantive(s, case, actor, m)
        _mirror(s, case, m)
    return m, True


def _on_substantive(s: Session, case: ValidationCase, actor: Actor, m: Message) -> None:
    st = CaseState(case.state)
    if m.round_id is None:
        return  # triagem: nunca se atribui à rodada mais recente por conveniência
    # canal principal: preferência explícita prevalece; senão, a primeira evidência substantiva validada
    cd = s.scalar(select(ChannelDecision).where(ChannelDecision.case_id == case.id, ChannelDecision.actor_id == actor.id))
    if cd is None:
        s.add(ChannelDecision(case_id=case.id, actor_id=actor.id, channel=m.channel, reason="primeira_resposta"))
        audit(s, actor="sistema", action="primary_channel_set", case=case,
              detail={"actor_id": actor.id, "channel": m.channel}, why="Primeira resposta substantiva define o canal principal")
    kick(s, case, m)


def kick(s: Session, case: ValidationCase, m: Message | None = None) -> None:
    """Há evidência não consolidada: leva o caso a PROCESSING_REPLY e agenda a consolidação."""
    st = CaseState(case.state)
    window = timedelta(seconds=QUIET_SECONDS)
    if st in (CaseState.WAITING_ANY_CHANNEL, CaseState.WAITING_PRIMARY_CHANNEL):
        move_case(s, case, "reply_correlated", actor="sistema", why="Resposta correlacionada à rodada")
    elif st in (CaseState.CHANGES_READY, CaseState.READY_FOR_APPROVAL, CaseState.WAITING_MUNICIPAL_APPROVAL,
                CaseState.WAITING_IMPLANTER_APPROVAL):
        case.resume_state = st.value
        move_case(s, case, "material_evidence", actor="sistema",
                  why="Nova evidência potencialmente material: aprovação e aplicação ficam bloqueadas até reconciliar")
    elif st == CaseState.APPLYING:
        move_case(s, case, "pending_evidence", actor="sistema", why="Evidência chegou antes do commit da aplicação")
    elif st in (CaseState.WAITING_OWNER, CaseState.WAITING_REFERRAL, CaseState.BUILDING_ROUND, CaseState.ROUND_READY):
        case.resume_state = st.value
        move_case(s, case, "material_evidence", actor="sistema", why="Nova evidência durante o planejamento")
    elif st == CaseState.PROCESSING_REPLY:
        pass  # a janela abaixo é estendida
    else:
        return  # pausa, intervenção, falha, verificação, conclusão: só persiste
    schedule_consolidation(s, case, window)


def schedule_consolidation(s: Session, case: ValidationCase, window: timedelta) -> None:
    now = business_now()
    pending = s.scalar(select(WorkItem).where(WorkItem.case_id == case.id, WorkItem.kind == "consolidate",
                                              WorkItem.status == "pending"))
    if pending:
        first = pending.payload.get("first_at")
        cap = (now if not first else _parse(first)) + timedelta(seconds=MAX_WINDOW_SECONDS)
        pending.available_at = min(now + window, cap)
        return
    s.add(WorkItem(case_id=case.id, kind="consolidate", payload={"first_at": now.isoformat()},
                   available_at=now + window))


def _parse(iso: str):
    from datetime import datetime
    return datetime.fromisoformat(iso)


def pending_evidence(s: Session, case_id: str) -> int:
    """Mensagem substantiva, artefato ou decisão ainda não consolidados, e anexos sem interpretação."""
    msgs = s.scalar(select(func.count()).select_from(Message).where(
        Message.case_id == case_id, Message.direction == "in", Message.substantive == True,  # noqa: E712
        Message.consolidated == False, Message.round_id.is_not(None)))  # noqa: E712
    arts = s.scalar(select(func.count()).select_from(DerivedArtifact).where(
        DerivedArtifact.case_id == case_id, DerivedArtifact.status == "ok", DerivedArtifact.consolidated == False))  # noqa: E712
    decs = s.scalar(select(func.count()).select_from(HumanDecision).where(
        HumanDecision.case_id == case_id, HumanDecision.consolidated == False))  # noqa: E712
    review = s.scalar(select(func.count()).select_from(Attachment).where(
        Attachment.case_id == case_id, Attachment.status == "needs_review"))
    return (msgs or 0) + (arts or 0) + (decs or 0) + (review or 0)


def triage_queue(s: Session, municipality_id: str | None = None) -> list[Message]:
    q = select(Message).where(Message.triage_status == "pending", Message.direction == "in")
    if municipality_id:
        q = q.where(Message.municipality_id == municipality_id)
    return list(s.scalars(q.order_by(Message.seq)))


def link_message(s: Session, case: ValidationCase, m: Message, round_id: str, actor: str) -> None:
    """Triagem manual: o implantador liga a mensagem a uma rodada do mesmo caso."""
    rnd = s.get(ValidationRound, round_id)
    if m.triage_status != "pending" or not rnd or rnd.case_id != case.id or m.case_id != case.id:
        raise AppError("NOT_FOUND", "mensagem ou rodada fora do escopo", 404)
    m.round_id, m.triage_status = rnd.id, "linked"
    audit(s, actor=actor, action="message_linked", case=case, detail={"message_id": m.id, "round_id": rnd.id},
          why="Triagem manual vinculou a mensagem à rodada")
    ac = s.get(Actor, m.actor_id)
    _on_substantive(s, case, ac, m)
    _mirror(s, case, m)


def _mirror(s: Session, case: ValidationCase, m: Message) -> None:
    """Espelha respostas do Portal/WhatsApp como comentário público no Pylon (I17: nunca reingerido)."""
    if m.channel == "pylon":
        return
    from ..persistence.models import Municipality
    if not s.get(Municipality, case.municipality_id).pylon_mirror_enabled:
        return
    key = f"mirror:{m.id}"
    if s.scalar(select(EffectReceipt).where(EffectReceipt.idempotency_key == key)):
        return
    actor = s.get(Actor, m.actor_id)
    where = {"portal": "no Portal Aprova Command", "whatsapp": "por WhatsApp"}[m.channel]
    body = f"Respondido {where} por {actor.name} em {business_now():%d/%m} às {business_now():%H:%M}: \"{m.body[:400]}\""
    t = s.get(Ticket, case.ticket_id)
    s.add(TicketComment(ticket_id=t.id, visibility="public", author="Aprova Command", body=body, external_key=key))
    s.add(Message(seq=next_seq(s), case_id=case.id, municipality_id=case.municipality_id, actor_id=m.actor_id,
                  channel="pylon", direction="out", body=body, body_hash=hashlib.sha256(body.encode()).hexdigest(),
                  mirror_of_message_id=m.id, external_key=key, consolidated=True, received_at=business_now()))
    s.add(EffectReceipt(idempotency_key=key, kind="mirror", case_id=case.id, detail={"message_id": m.id}))


def pylon_webhook(s: Session, case: ValidationCase, actor: Actor, *, external_key: str, body: str) -> dict:
    """Entrada do webhook do Pylon simulado: espelhos são reconhecidos e ignorados (I17, T17)."""
    if external_key.startswith("mirror:") or external_key.startswith("out:"):
        audit(s, actor="sistema", action="mirror_ignored", case=case, detail={"external_key": external_key},
              why="Evento do Pylon é o espelho de uma resposta já recebida; não vira evidência")
        return {"ignored": "mirror"}
    # o comentário nasce no ticket onde a rodada foi publicada: com uma única rodada ativa por caso, a correlação é inequívoca
    m, created = ingest(s, case, actor, channel="pylon", body=body, external_key=external_key,
                        reply_to_round_id=_active_round_id(s, case.id))
    return {"message_id": m.id, "created": created}


def _active_round_id(s: Session, case_id: str) -> str | None:
    from .rounds import active_round
    r = active_round(s, case_id)
    return r.id if r else None
