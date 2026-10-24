"""Rodadas: planejamento por lacunas, entrega multicanal, prazos e espelhamento (v2 §8, §10.2)."""

from __future__ import annotations

import hashlib
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..clock import business_now
from ..persistence.flow_models import (
    ChannelDecision, Gap, Message, RoundItem, ValidationRound,
)
from ..persistence.models import (
    Actor, EffectReceipt, Municipality, OutboxMessage, ProcessDefinition, RoleAssignment, Setting, Ticket,
    TicketComment, ValidationCase, new_id,
)
from .common import AppError, audit, enqueue, move_case, open_intervention

ITEM_DEADLINE_HOURS = 72
REMINDER_HOURS = (24, 48)
RETRY_BACKOFF = (1, 5)
MAX_SEND_ATTEMPTS = 3
SETTINGS = {"first_message_review": True}  # modo copiloto: revisar a primeira mensagem de cada destinatário
ALL_CHANNELS = ("whatsapp", "portal", "pylon")


# ------------------------------------------------------------ destinatário


def responders(s: Session, case: ValidationCase) -> list[tuple[Actor, RoleAssignment]]:
    out = []
    q = select(RoleAssignment).where(RoleAssignment.role == "responder", RoleAssignment.revoked_at.is_(None))
    for ra in s.scalars(q):
        scoped = ra.process_id == case.process_id or (ra.process_id is None and ra.municipality_id == case.municipality_id)
        if not scoped:
            continue
        a = s.get(Actor, ra.actor_id)
        if a and a.merged_into is None and a.municipality_id == case.municipality_id:
            out.append((a, ra))
    return out


def recipient_for(s: Session, case: ValidationCase, gap: Gap) -> Actor | None:
    """Responder autorizado cujo escopo cobre o assunto; assunto exato vence escopo amplo."""
    cands = responders(s, case)
    exact = [a for a, ra in cands if ra.topic == gap.topic]
    if exact:
        return sorted(exact, key=lambda a: a.id)[0]
    broad = [a for a, ra in cands if ra.topic in (None, "geral") or gap.topic == "geral"]
    return sorted(broad, key=lambda a: a.id)[0] if broad else None


def active_round(s: Session, case_id: str) -> ValidationRound | None:
    return s.scalar(select(ValidationRound).where(ValidationRound.case_id == case_id,
                                                  ValidationRound.status.in_(["ready", "sending", "waiting"])))


def open_items(s: Session, round_id: str) -> list[RoundItem]:
    return list(s.scalars(select(RoundItem).where(RoundItem.round_id == round_id, RoundItem.status == "open")
                          .order_by(RoundItem.position)))


# ---------------------------------------------------------- planejamento


def compose_message(s: Session, case: ValidationCase, rnd: ValidationRound, items: list[RoundItem]) -> str:
    """Texto genérico derivado de lacunas e pedidos; nenhuma pergunta fixa por formulário."""
    p = s.get(ProcessDefinition, case.process_id)
    who = s.get(Actor, rnd.recipient_id)
    first = who.name.split()[0]
    lines = [f"Olá, {first}. Aqui é a equipe de implantação da Aprova, sobre {p.code} · {p.name}.", ""]
    if rnd.summary:
        lines += ["O que entendemos até agora:", rnd.summary, ""]
    n = len(items)
    lines.append(f"Para seguir, precisamos de {n} informaç{'ão' if n == 1 else 'ões'}:")
    for i, it in enumerate(items, 1):
        extra = f" (opções: {', '.join(it.options)})" if it.options else ""
        lines.append(f"{i}. {it.question}{extra}")
    lines += ["", "Você pode responder aqui mesmo ou pelo Portal. Se isso não for com você, diga quem pode ajudar."]
    return "\n".join(lines)


def plan_round(s: Session, case: ValidationCase) -> ValidationRound | None:
    """Agrupa as lacunas abertas do mesmo destinatário; o resto fica para rodadas sequenciais (I04)."""
    gaps = list(s.scalars(select(Gap).where(Gap.case_id == case.id, Gap.status == "open", Gap.blocking == True)  # noqa: E712
                          .order_by(Gap.created_at, Gap.ref)))
    gaps.sort(key=lambda g: int(g.ref[1:]))
    if not gaps:
        return None
    # rodada ativa anterior (ex.: indicação) é substituída; itens abertos voltam ao pool de lacunas
    cur = active_round(s, case.id)
    revision = 1
    if cur:
        cur.status = "superseded"
        revision = cur.revision + 1
        s.flush()
    first = recipient_for(s, case, gaps[0])
    if first is None:
        return None
    same = [g for g in gaps if (recipient_for(s, case, g) or first).id == first.id and recipient_for(s, case, g)]
    later = [g for g in gaps if g not in same]
    seq = (s.scalar(select(func.max(ValidationRound.seq)).where(ValidationRound.case_id == case.id)) or 0) + 1
    reqs = []
    for g in same:
        if g.request_id:
            from ..persistence.models import ChangeRequest
            cr = s.get(ChangeRequest, g.request_id)
            if cr and cr.summary not in reqs:
                reqs.append(cr.summary)
    summary = "\n".join(f"- {r}" for r in reqs)
    topics = sorted({g.topic for g in same})
    objective = f"Completar {len(same)} informação(ões) sobre {', '.join(topics)}"
    note = f"{len(same)} lacuna(s) agrupada(s) para {first.name}: o mesmo destinatário responde tudo de uma vez."
    if later:
        note += f" {len(later)} lacuna(s) de outro responsável ficam para a próxima rodada."
    rnd = ValidationRound(id=new_id("rd_"), case_id=case.id, municipality_id=case.municipality_id, seq=seq,
                          recipient_id=first.id, objective=objective, summary=summary, grouping_note=note,
                          status="ready", revision=revision, created_at=business_now())
    s.add(rnd)
    s.flush()
    items = []
    for i, g in enumerate(same, 1):
        why = "Para fechar o pedido: " + (s.get(ChangeRequestModel(), g.request_id).summary if g.request_id else g.question)
        it = RoundItem(id=new_id("ri_"), round_id=rnd.id, gap_id=g.id, position=i, question=g.question, why=why,
                       answer_kind=g.answer_kind, options=g.options)
        s.add(it)
        items.append(it)
    s.flush()
    audit(s, actor="sistema", action="round_planned", case=case,
          detail={"round_id": rnd.id, "seq": seq, "items": len(items), "recipient": first.id, "revision": revision},
          why=note)
    return rnd


def ChangeRequestModel():
    from ..persistence.models import ChangeRequest
    return ChangeRequest


def is_first_contact(s: Session, actor_id: str) -> bool:
    return s.scalar(select(func.count()).select_from(ValidationRound).where(
        ValidationRound.recipient_id == actor_id, ValidationRound.sent_at.is_not(None))) == 0


def release_round(s: Session, case: ValidationCase, rnd: ValidationRound, actor: str) -> None:
    """Política permite o envio (revisão da primeira mensagem concluída ou dispensada)."""
    if case.state != "ROUND_READY":
        raise AppError("INVALID_TRANSITION", f"a rodada não está pronta para envio ({case.state})", 409)
    move_case(s, case, "policy_allows_send", actor=actor, why="Política permite o envio da rodada")
    rnd.status = "sending"
    enqueue(s, "send_round", case.id, {"round_id": rnd.id}, dedupe_key=f"send:{rnd.id}:{rnd.revision}:0")


# ---------------------------------------------------------------- entrega


def channels_for(s: Session, case: ValidationCase, rnd: ValidationRound) -> list[str]:
    cd = s.scalar(select(ChannelDecision).where(ChannelDecision.case_id == case.id,
                                                ChannelDecision.actor_id == rnd.recipient_id))
    if cd:
        return [cd.channel]
    m = s.get(Municipality, case.municipality_id)
    chans = ["whatsapp"]
    if m.portal_enabled:
        chans.append("portal")
    chans.append("pylon")
    return chans


def faults(s: Session) -> dict:
    row = s.get(Setting, "sim_faults")
    return row.value if row else {}


def set_fault(s: Session, channel: str, mode: str | None) -> None:
    row = s.get(Setting, "sim_faults")
    cur = dict(row.value) if row else {}
    if mode:
        cur[channel] = mode
    else:
        cur.pop(channel, None)
    if row:
        row.value = cur
    else:
        s.add(Setting(key="sim_faults", value=cur))


def start_send(s: Session, case: ValidationCase, rnd: ValidationRound) -> None:
    """Cria uma entrega (outbox) por canal; chave inclui caso, rodada/revisão, destinatário, canal e parte."""
    rnd.channels = channels_for(s, case, rnd)
    for ch in rnd.channels:
        key = f"send:{case.id}:{rnd.id}:{rnd.revision}:{rnd.recipient_id}:{ch}:0"
        if not s.scalar(select(OutboxMessage).where(OutboxMessage.idempotency_key == key)):
            s.add(OutboxMessage(case_id=case.id, kind="send", idempotency_key=key,
                                payload={"round_id": rnd.id, "channel": ch, "part": 0}))
    s.flush()


def _deliver(s: Session, case: ValidationCase, rnd: ValidationRound, channel: str, part: int, key: str) -> None:
    """Efeito idempotente: o receptor simulado grava um recibo único pela chave."""
    if s.scalar(select(EffectReceipt).where(EffectReceipt.idempotency_key == key)):
        return
    items = open_items(s, rnd.id)
    body = compose_message(s, case, rnd, items)
    msg = Message(seq=next_seq(s), case_id=case.id, municipality_id=case.municipality_id, actor_id=rnd.recipient_id,
                  channel=channel, direction="out", body=body, body_hash=hashlib.sha256(body.encode()).hexdigest(),
                  round_id=rnd.id, part=part, external_key=f"out:{key}", received_at=business_now(), consolidated=True)
    s.add(msg)
    if channel == "pylon":
        t = s.get(Ticket, case.ticket_id)
        s.add(TicketComment(ticket_id=t.id, visibility="public", author="Aprova Command", body=body,
                            external_key=f"out:{key}"))
    s.add(EffectReceipt(idempotency_key=key, kind=f"send_{channel}", case_id=case.id,
                        detail={"round_id": rnd.id, "channel": channel, "part": part}))


def next_seq(s: Session) -> int:
    return (s.scalar(select(func.max(Message.seq))) or 0) + 1


def process_send(s: Session, case: ValidationCase, rnd: ValidationRound) -> str:
    """Uma passada por todas as entregas pendentes. Devolve 'retry' | 'done'."""
    f = faults(s)
    outs = list(s.scalars(select(OutboxMessage).where(OutboxMessage.case_id == case.id,
                                                      OutboxMessage.kind == "send",
                                                      OutboxMessage.payload["round_id"].as_string() == rnd.id)))
    retry = False
    for ob in outs:
        if ob.status in ("done", "failed"):
            continue
        ch = ob.payload["channel"]
        if f.get(ch) == "down":
            ob.attempts += 1
            ob.error = f"canal {ch} indisponível"
            if ob.attempts >= MAX_SEND_ATTEMPTS:
                ob.status = "failed"
            else:
                ob.available_at = business_now() + timedelta(seconds=RETRY_BACKOFF[min(ob.attempts - 1, 1)])
                retry = True
            continue
        _deliver(s, case, rnd, ch, ob.payload["part"], ob.idempotency_key)
        ob.status, ob.attempts = "done", ob.attempts + 1
    s.flush()
    if retry:
        return "retry"
    ok = [o for o in outs if o.status == "done"]
    bad = [o for o in outs if o.status == "failed"]
    results = {o.payload["channel"]: ("delivered" if o.status == "done" else "failed") for o in outs}
    now = business_now()
    if not ok:
        open_intervention(s, case, code="TODOS_CANAIS_FALHARAM", urgency=1,
                          reason="A rodada não foi entregue em nenhum canal autorizado.",
                          needed="Corrigir o canal de contato do destinatário e reenviar")
        move_case(s, case, "all_channels_failed", actor="sistema", why="Todos os canais esgotaram as tentativas")
        return "failed"
    rnd.status, rnd.sent_at, rnd.reminders_sent = "waiting", now, 0
    rnd.channels = [o.payload["channel"] for o in ok]
    for it in open_items(s, rnd.id):
        it.due_at = now + timedelta(hours=ITEM_DEADLINE_HOURS)
    audit(s, actor="sistema", action="round_delivered", case=case, detail={"round_id": rnd.id, "channels": results},
          why="Sucesso parcial: mantemos a espera nos canais entregues" if bad else "Rodada entregue em todos os canais")
    has_primary = s.scalar(select(ChannelDecision).where(ChannelDecision.case_id == case.id,
                                                         ChannelDecision.actor_id == rnd.recipient_id))
    move_case(s, case, "next_round_delivered" if has_primary else "first_round_delivered", actor="sistema",
              why="Rodada entregue")
    case.next_action = "Aguardar a resposta da prefeitura"
    return "done"


# --------------------------------------------------------------- prazos


def tick_deadlines(s: Session) -> int:
    """Lembretes (24h, 48h) e intervenção (72h) por relógio de negócio; máximo um passo por rodada e por tick."""
    now = business_now()
    n = 0
    for rnd in s.scalars(select(ValidationRound).where(ValidationRound.status == "waiting")):
        case = s.get(ValidationCase, rnd.case_id)
        if case.state not in ("WAITING_ANY_CHANNEL", "WAITING_PRIMARY_CHANNEL"):
            continue  # pausa/intervenção suspende lembretes
        sent = rnd.sent_at.replace(tzinfo=now.tzinfo) if rnd.sent_at.tzinfo is None else rnd.sent_at
        hours = (now - sent).total_seconds() / 3600
        if hours >= 72:
            open_intervention(s, case, code="SEM_RESPOSTA", urgency=1,
                              reason=f"Sem resposta substantiva há mais de 72 horas ({s.get(Actor, rnd.recipient_id).name}).",
                              needed="Acionar o contato central ou indicar outro responsável")
            move_case(s, case, "round_timeout", actor="sistema", why="Sem resposta em 72 horas")
            n += 1
        elif hours >= REMINDER_HOURS[1] and rnd.reminders_sent == 1:
            _reminder(s, case, rnd, 2)
            n += 1
        elif hours >= REMINDER_HOURS[0] and rnd.reminders_sent == 0:
            _reminder(s, case, rnd, 1)
            n += 1
    return n


def _reminder(s: Session, case: ValidationCase, rnd: ValidationRound, number: int) -> None:
    """Lembrete só no canal principal/entregue; não é nova rodada."""
    open_n = len(open_items(s, rnd.id))
    ch = (s.scalar(select(ChannelDecision).where(ChannelDecision.case_id == case.id,
                                                 ChannelDecision.actor_id == rnd.recipient_id)))
    chans = [ch.channel] if ch else list(rnd.channels or [])
    rnd.reminders_sent = number
    key = f"remind:{rnd.id}:{rnd.revision}:{number}"
    for c in chans:
        k = f"{key}:{c}"
        if s.scalar(select(EffectReceipt).where(EffectReceipt.idempotency_key == k)):
            continue
        body = (f"Lembrete: ainda aguardamos {open_n} informação(ões) sobre este processo. "
                f"Se não for com você, indique quem pode ajudar.")
        s.add(Message(seq=next_seq(s), case_id=case.id, municipality_id=case.municipality_id,
                      actor_id=rnd.recipient_id, channel=c, direction="out", body=body,
                      body_hash=hashlib.sha256(body.encode()).hexdigest(), round_id=rnd.id,
                      external_key=f"out:{k}", received_at=business_now(), consolidated=True))
        s.add(EffectReceipt(idempotency_key=k, kind="reminder", case_id=case.id, detail={"channel": c, "n": number}))
    audit(s, actor="sistema", action="reminder_sent", case=case,
          detail={"round_id": rnd.id, "number": number}, why=f"Lembrete {number} de 2 por falta de resposta")


def shift_deadlines(s: Session, case_id: str, delta: timedelta) -> None:
    """Retomada após pausa preserva o saldo restante, sem rajada de lembretes."""
    for rnd in s.scalars(select(ValidationRound).where(ValidationRound.case_id == case_id,
                                                       ValidationRound.status == "waiting")):
        if rnd.sent_at:
            rnd.sent_at = rnd.sent_at + delta
        for it in open_items(s, rnd.id):
            if it.due_at:
                it.due_at = it.due_at + delta
