"""Projeções determinísticas: Hoje, explicação, detalhe (adendo v2.1 §3, §4, §8).

Nada aqui é armazenado nem gerado por LLM: é função do estado persistido e do relógio de negócio.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import business_now
from ..domain.states import CaseState, ball_owner
from . import rounds as rounds_mod
from ..persistence.models import (
    Actor, Approval, AuditEvent, ChangeRequest, ChangeSet, Intervention, Municipality, ProcessDefinition,
    Secretariat, Ticket, ValidationCase,
)

STATE_LABEL = {
    "DRAFT": "Rascunho", "INTAKE": "Recebendo o ticket", "UNDERSTANDING_FORM": "Lendo o formulário",
    "ANALYZING_INITIAL_REPLY": "Analisando a resposta inicial", "BUILDING_ROUND": "Montando a rodada de perguntas",
    "ROUND_READY": "Rodada pronta", "SENDING_ROUND": "Enviando a rodada",
    "WAITING_ANY_CHANNEL": "Aguardando resposta", "WAITING_PRIMARY_CHANNEL": "Aguardando resposta",
    "PROCESSING_REPLY": "Processando resposta", "RECONCILING_RESPONSES": "Consolidando respostas",
    "WAITING_OWNER": "Procurando responsável", "WAITING_REFERRAL": "Aguardando indicação",
    "CHANGES_READY": "Alterações prontas para revisão", "READY_FOR_APPROVAL": "Pronto para aprovação",
    "WAITING_MUNICIPAL_APPROVAL": "Aguardando aprovação da prefeitura",
    "WAITING_IMPLANTER_APPROVAL": "Aguardando aprovação da Aprova", "APPLYING": "Aplicando a versão",
    "VERIFYING": "Verificando a versão", "COMPLETED": "Concluído", "PAUSED": "Pausado",
    "BLOCKED_HUMAN": "Sua decisão", "FAILED_RETRYABLE": "Falha, tentando de novo",
    "FAILED_PERMANENT": "Falha permanente",
}

# eixo 2 do direcionamento visual (estado do caso)
def state_axis(state: str) -> str:
    return {
        "BLOCKED_HUMAN": "blocked", "WAITING_IMPLANTER_APPROVAL": "blocked", "CHANGES_READY": "blocked",
        "READY_FOR_APPROVAL": "blocked", "WAITING_ANY_CHANNEL": "waiting", "WAITING_PRIMARY_CHANNEL": "waiting",
        "WAITING_REFERRAL": "waiting", "WAITING_OWNER": "waiting", "WAITING_MUNICIPAL_APPROVAL": "waiting",
        "PAUSED": "paused", "FAILED_RETRYABLE": "failed", "FAILED_PERMANENT": "failed", "COMPLETED": "completed",
    }.get(state, "running")


def municipality_dto(m: Municipality) -> dict:
    return {"id": m.id, "name": m.name, "short": m.short, "city": m.city, "color_slot": m.color_slot}


def _utc(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def deadline_dto(due: datetime | None, now: datetime | None = None, done: bool = False) -> dict:
    """Eixo Prazo: em dia > 3 dias; em risco <= 3 dias ou hoje; atrasado se vencido."""
    now = now or business_now()
    if due is None:
        return {"status": "ontrack", "due_at": None, "days": None}
    due = _utc(due)
    days = (due.date() - now.date()).days
    if done:
        status = "ontrack"
    elif due < now and days < 0:
        status = "late"
    elif days <= 3:
        status = "atrisk"
    else:
        status = "ontrack"
    return {"status": status, "due_at": due.isoformat(), "days": days}


def _rank(status: str) -> int:
    return {"late": 0, "atrisk": 1, "ontrack": 2}[status]


def explanation(s: Session, case: ValidationCase) -> dict:
    """what/why/next/who/since por template determinístico, a partir do estado e do último evento."""
    st = case.state
    cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == case.id).order_by(ChangeSet.created_at.desc()))
    ivs = list(s.scalars(select(Intervention).where(Intervention.case_id == case.id, Intervention.status == "open")))
    last = s.scalar(select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.seq.desc()))
    h = cs.candidate_hash[:8] if cs else ""
    t = {
        "UNDERSTANDING_FORM": ("O agente está lendo o formulário vigente", "É preciso conhecer os campos antes de interpretar o pedido", "Analisar a resposta inicial do ticket"),
        "ANALYZING_INITIAL_REPLY": ("O agente está analisando a resposta inicial", "Para separar os pedidos e citar a fonte de cada um", "Montar a candidata ou perguntar à prefeitura"),
        "CHANGES_READY": ("A candidata e os testes estão prontos", "Uma pessoa precisa revisar os resultados esperados antes de pedir a aprovação", "Revisar os testes e pedir a aprovação da prefeitura"),
        "READY_FOR_APPROVAL": ("Pronto para pedir aprovação", "Candidata, diff e testes passaram", "Registrar o pedido de aprovação municipal"),
        "WAITING_MUNICIPAL_APPROVAL": ("A prefeitura precisa aprovar a versão", f"Nenhuma alteração é aplicada sem a aprovação de quem responde pelo processo (versão {h})", "Aguardar a aprovação ou cobrar a prefeitura"),
        "WAITING_IMPLANTER_APPROVAL": ("A prefeitura aprovou; falta a aprovação da Aprova", f"A mesma versão ({h}) precisa de uma segunda aprovação independente", "Revisar o diff e os testes e aprovar"),
        "APPLYING": ("A versão aprovada está sendo aplicada", "As duas aprovações estão válidas", "Verificar a persistência no motor"),
        "VERIFYING": ("O sistema está lendo de volta a versão aplicada", "Só se fecha o ticket depois de confirmar o que foi gravado", "Rodar os testes de novo e fechar o ticket"),
        "COMPLETED": ("Versão aplicada, verificada e ticket fechado", "Todos os passos foram confirmados com recibo", "Nada a fazer"),
        "PAUSED": ("O caso está pausado", case.blocked_reason or "Pausa solicitada", "Retomar quando for seguro"),
        "BLOCKED_HUMAN": ("O caso parou e precisa da sua decisão", case.blocked_reason or "Há uma intervenção aberta", "Resolver a intervenção"),
        "FAILED_RETRYABLE": ("Uma etapa falhou e será repetida", "Falha transitória registrada", "O sistema tenta de novo automaticamente"),
        "FAILED_PERMANENT": ("Falha de integridade", "O sistema não consegue continuar sozinho", "Diagnosticar e decidir"),
    }.get(st, (STATE_LABEL.get(st, st), "Etapa do fluxo", case.next_action or ""))
    if ivs and st == "BLOCKED_HUMAN":
        t = (ivs[0].reason, f"Decisão necessária: {ivs[0].needed_decision}" if ivs[0].needed_decision else t[1], t[2])
    return {
        "what": t[0], "why": t[1], "next": t[2], "who": ball_owner(CaseState(st)),
        "since": _utc(case.state_since).isoformat(),
        "last_event": {"action": last.action, "why": last.why, "at": _utc(last.created_at).isoformat()} if last else None,
        "source_refs": [{"type": "audit", "id": last.id}] if last else [],
    }


def case_card(s: Session, case: ValidationCase) -> dict:
    m = s.get(Municipality, case.municipality_id)
    p = s.get(ProcessDefinition, case.process_id)
    sec = s.get(Secretariat, p.secretariat_id) if p.secretariat_id else None
    return {
        "id": case.id, "municipality": municipality_dto(m), "process": {"id": p.id, "code": p.code, "name": p.name},
        "secretariat": sec.name if sec else None, "state": case.state, "state_label": STATE_LABEL.get(case.state),
        "axis": state_axis(case.state), "version": case.version, "cycle": case.cycle_number,
        "ball_owner": ball_owner(CaseState(case.state)),
        "deadline": deadline_dto(p.due_date, done=case.state == "COMPLETED"),
        "since": _utc(case.state_since).isoformat(), "explanation": explanation(s, case),
    }


def _task(kind: str, case_card_: dict, title: str, why_code: str, why: str, since: datetime, action: dict,
          urgency: int = 3) -> dict:
    return {
        "task_id": f"{kind}:{case_card_['id']}:{case_card_['version']}", "kind": kind,
        "client": case_card_["municipality"], "process": case_card_["process"], "case_id": case_card_["id"],
        "title": title, "why": {"code": why_code, "text": why}, "since": _utc(since).isoformat(),
        "deadline": case_card_["deadline"], "primary_action": action, "urgency": urgency,
        "secretariat": case_card_["secretariat"],
    }


def today(s: Session, client_id: str | None = None) -> dict:
    now = business_now()
    tasks: list[dict] = []
    waiting: list[dict] = []
    agent: list[dict] = []
    q = select(ValidationCase).where(ValidationCase.active == True)  # noqa: E712
    if client_id:
        q = q.where(ValidationCase.municipality_id == client_id)
    for c in s.scalars(q):
        card = case_card(s, c)
        code = card["process"]["code"]
        route = f"/processes/{c.id}"
        open_iv = list(s.scalars(select(Intervention).where(Intervention.case_id == c.id,
                                                            Intervention.status == "open")))
        if open_iv:
            iv = open_iv[0]
            tasks.append(_task("intervention", card, f"Resolver: {iv.reason}", iv.reason_code,
                               iv.needed_decision or iv.reason, iv.created_at,
                               {"label": "Abrir decisão", "route": route}, iv.urgency))
        elif c.state == "ROUND_READY":
            rnd = rounds_mod.active_round(s, c.id)
            who = s.get(Actor, rnd.recipient_id).name if rnd else "o destinatário"
            tasks.append(_task("review_first_message", card, f"Revisar a primeira mensagem para {who}",
                               "ROUND_READY", "É o primeiro contato com esta pessoa: uma revisão humana antes do envio.",
                               c.state_since, {"label": "Revisar e enviar", "route": route}, 2))
        elif c.state == "WAITING_OWNER":
            from ..persistence.flow_models import Gap as GapM
            g = s.scalar(select(GapM).where(GapM.case_id == c.id, GapM.status == "open").order_by(GapM.created_at))
            tasks.append(_task("define_owner", card, f"Definir quem responde sobre {g.topic if g else 'o assunto'} em {code}",
                               "WAITING_OWNER", "Nenhum contato autorizado cobre este assunto; a pergunta não pode sair.",
                               c.state_since, {"label": "Definir responsável", "route": route}, 2))
        elif c.state == "WAITING_REFERRAL":
            from ..persistence.flow_models import ContactReferral as RF
            for rf in s.scalars(select(RF).where(RF.case_id == c.id, RF.status == "pending")):
                frm = s.get(Actor, rf.from_actor_id)
                tasks.append(_task("authorize_referral", card,
                                   f"Autorizar {rf.name} a responder sobre {rf.topic} em {code}. Indicada por {frm.name if frm else '—'}",
                                   "WAITING_REFERRAL", "Receber um nome não concede autorização: só o assunto indicado será repassado.",
                                   rf.created_at, {"label": "Autorizar escopo", "route": route}, 2))
        elif c.state == "WAITING_IMPLANTER_APPROVAL":
            cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == c.id).order_by(ChangeSet.created_at.desc()))
            tasks.append(_task("approve_implanter", card, f"Aprovar pela Aprova a versão {cs.candidate_hash[:8]} de {code}",
                               "WAITING_IMPLANTER_APPROVAL", "A prefeitura já aprovou; falta a segunda aprovação.",
                               c.state_since, {"label": "Revisar e aprovar", "route": route}, 1))
        elif c.state in ("CHANGES_READY", "READY_FOR_APPROVAL"):
            tasks.append(_task("review_tests", card, f"Revisar resultados esperados dos testes de {code}",
                               "CHANGES_READY", "Uma pessoa precisa validar os testes antes de pedir a aprovação.",
                               c.state_since, {"label": "Abrir testes", "route": route}, 2))
        elif c.state == "WAITING_MUNICIPAL_APPROVAL":
            if now - _utc(c.state_since) > timedelta(hours=24):
                tasks.append(_task("chase_municipal", card, f"Cobrar aprovação municipal da versão de {code}",
                                   "WAITING_MUNICIPAL_APPROVAL", "A prefeitura não respondeu há mais de 24 horas.",
                                   c.state_since, {"label": "Enviar lembrete", "route": route}, 2))
            waiting.append(card)
        elif card["ball_owner"] == "prefeitura":
            waiting.append(card)
        elif card["ball_owner"] in ("agente", "sistema"):
            agent.append(card)
    # mensagens sem rodada inequívoca (triagem) e possíveis novas solicitações
    from ..persistence.flow_models import Message as Msg
    tq = select(Msg).where(Msg.triage_status == "pending", Msg.direction == "in")
    if client_id:
        tq = tq.where(Msg.municipality_id == client_id)
    for m in s.scalars(tq):
        c = s.get(ValidationCase, m.case_id)
        card = case_card(s, c)
        who = s.get(Actor, m.actor_id).name if m.actor_id else "contato"
        done = c.state == "COMPLETED"
        title = (f"Avaliar possível nova solicitação de {who} em {card['process']['code']}" if done
                 else f"Classificar mensagem de {who} ({m.channel})")
        tasks.append(_task("triage", card, title, "TRIAGEM",
                           "A mensagem não tem rodada inequívoca; o sistema não a atribui por conveniência.",
                           m.received_at, {"label": "Abrir", "route": f"/inbox?triage=1"}, 2))
    # declarações do primeiro acesso: "indicar outra pessoa" ou "não sei" viram tarefa para o implantador
    from ..persistence.flow_models import ResponsibilityClaim as RCl
    cq = select(RCl).where(RCl.handled == False, RCl.answer.in_(["refer", "unknown"]))  # noqa: E712
    if client_id:
        cq = cq.where(RCl.municipality_id == client_id)
    for cl in s.scalars(cq):
        p = s.get(ProcessDefinition, cl.process_id)
        who = s.get(Actor, cl.actor_id)
        m = s.get(Municipality, cl.municipality_id)
        txt = (f"{who.name} indicou {cl.refer_name}" if cl.answer == "refer" else f"{who.name} disse não saber")
        tasks.append({
            "task_id": f"claim:{cl.id}", "kind": "claim", "client": municipality_dto(m),
            "process": {"id": p.id, "code": p.code, "name": p.name}, "case_id": None,
            "title": f"Definir o responsável por {p.code}: {txt}", "why": {"code": "PRIMEIRO_ACESSO",
            "text": "Declarar não é autorizar: um responsável da Aprova precisa definir quem responde por este processo."},
            "since": _utc(cl.created_at).isoformat(), "deadline": deadline_dto(p.due_date),
            "primary_action": {"label": "Definir responsável", "route": f"/clients?claim={cl.id}&process={p.id}"},
            "urgency": 3, "secretariat": None})
    # processos do cronograma em risco/atrasados sem caso iniciado
    pq = select(ProcessDefinition).where(ProcessDefinition.started == False)  # noqa: E712
    if client_id:
        pq = pq.where(ProcessDefinition.municipality_id == client_id)
    for p in s.scalars(pq):
        dl = deadline_dto(p.due_date)
        if dl["status"] in ("late", "atrisk"):
            m = s.get(Municipality, p.municipality_id)
            when = "Atrasado" if dl["status"] == "late" else f"Vence em {dl['days']} dia(s)"
            tasks.append({
                "task_id": f"start:{p.id}", "kind": "start_case", "client": municipality_dto(m),
                "process": {"id": p.id, "code": p.code, "name": p.name}, "case_id": None,
                "title": f"Iniciar validação de {p.code}", "why": {"code": "PRAZO", "text": f"{when} e ainda não iniciado."},
                "since": _utc(p.due_date).isoformat(), "deadline": dl,
                "primary_action": {"label": "Iniciar caso", "route": f"/processes/new?process={p.id}"},
                "urgency": 3, "secretariat": None})
    tasks.sort(key=lambda t: (_rank(t["deadline"]["status"]), t["urgency"], t["since"]))
    per_client: dict[str, int] = {}
    for t in tasks:
        per_client[t["client"]["id"]] = per_client.get(t["client"]["id"], 0) + 1
    return {"tasks": tasks, "waiting": waiting, "agent": agent, "counts_by_client": per_client,
            "generated_at": now.isoformat()}


def case_detail(s: Session, case: ValidationCase) -> dict:
    card = case_card(s, case)
    ticket = s.get(Ticket, case.ticket_id)
    crs = list(s.scalars(select(ChangeRequest).where(ChangeRequest.case_id == case.id)))
    cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == case.id).order_by(ChangeSet.created_at.desc()))
    approvals = list(s.scalars(select(Approval).where(Approval.case_id == case.id).order_by(Approval.created_at)))
    ivs = list(s.scalars(select(Intervention).where(Intervention.case_id == case.id).order_by(Intervention.created_at)))
    return {
        **card,
        "ticket": {"id": ticket.id, "title": ticket.title, "description": ticket.description,
                   "initial_reply": ticket.initial_reply, "status": ticket.status},
        "change_requests": [{"id": r.id, "summary": r.summary, "quote": r.source_quote, "clarity": r.clarity,
                             "feasibility": r.feasibility, "risk": r.risk, "disposition": r.disposition}
                            for r in crs],
        "change_set_id": cs.id if cs else None,
        "approvals": [{"id": a.id, "role": a.approver_role, "decision": a.decision, "actor_id": a.actor_id,
                       "channel": a.channel, "rationale": a.rationale, "candidate_hash": a.candidate_hash,
                       "at": _utc(a.created_at).isoformat(), "valid": a.invalidated_at is None,
                       "invalidated_reason": a.invalidated_reason} for a in approvals],
        "interventions": [{"id": i.id, "code": i.reason_code, "reason": i.reason, "needed": i.needed_decision,
                           "status": i.status, "resolution": i.resolution, "urgency": i.urgency} for i in ivs],
        "next_action": case.next_action,
    }


def timeline(s: Session, case_id: str) -> list[dict]:
    rows = s.scalars(select(AuditEvent).where(AuditEvent.case_id == case_id).order_by(AuditEvent.seq))
    return [{"seq": r.seq, "actor": r.actor, "action": r.action, "from": r.from_state, "to": r.to_state,
             "why": r.why, "detail": r.detail, "at": _utc(r.created_at).isoformat()} for r in rows]
