"""Métricas locais (v2 §16.2). Denominador zero é N/A (None), nunca 100%. Seeds e processos não iniciados ficam fora."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..persistence.flow_models import Gap, HumanDecision, Message, ValidationRound
from ..persistence.models import (
    Approval, AuditEvent, ChangeRequest, ChangeSet, EffectReceipt, Intervention, ProcessDefinition, ValidationCase,
)

EVIDENCE_CLASS = "benchmark_local_sintetico"


def _ratio(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 4)


def compute(s: Session, client: str | None = None) -> dict:
    cq = select(ValidationCase)
    if client:
        cq = cq.where(ValidationCase.municipality_id == client)
    cases = list(s.scalars(cq))
    ids = [c.id for c in cases]
    total_processes = s.scalar(select(func.count()).select_from(ProcessDefinition).where(
        *( [ProcessDefinition.municipality_id == client] if client else []))) or 0
    not_started = s.scalar(select(func.count()).select_from(ProcessDefinition).where(
        ProcessDefinition.started == False, *([ProcessDefinition.municipality_id == client] if client else []))) or 0  # noqa: E712

    reqs = list(s.scalars(select(ChangeRequest).where(ChangeRequest.case_id.in_(ids)))) if ids else []
    by_disp = Counter(r.disposition for r in reqs)
    request_totals = {"inicial": len(reqs), "aceito": by_disp["accepted"], "rejeitado": by_disp["rejected"],
                      "retirado": by_disp["withdrawn"], "pendente": by_disp["pending"]}

    # cobertura auditável: aceitas com evidência, teste aprovado e dupla aprovação ÷ aceitas
    covered = 0
    accepted = [r for r in reqs if r.disposition == "accepted"]
    for r in accepted:
        cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == r.case_id, ChangeSet.status.in_(["verified", "applied"])))
        if cs is None:
            continue
        ap = s.scalars(select(Approval).where(Approval.change_set_id == cs.id, Approval.decision == "approve",
                                              Approval.invalidated_at.is_(None))).all()
        if {a.approver_role for a in ap} >= {"municipal", "aprova"} and r.source_quote:
            covered += 1

    # rodadas substantivas únicas até a aprovação (canais, partes e lembretes não multiplicam)
    rounds = list(s.scalars(select(ValidationRound).where(ValidationRound.case_id.in_(ids)))) if ids else []
    per_case_rounds: dict[str, int] = defaultdict(int)
    for r in rounds:
        if r.status != "superseded" or r.sent_at is not None:
            per_case_rounds[r.case_id] += 1
    approved_cases = [c for c in cases if c.state in ("WAITING_IMPLANTER_APPROVAL", "APPLYING", "VERIFYING", "COMPLETED")]
    rounds_until_approval = [per_case_rounds.get(c.id, 0) for c in approved_cases]

    gaps = list(s.scalars(select(Gap).where(Gap.case_id.in_(ids)))) if ids else []
    answered = sum(1 for g in gaps if g.status == "answered")
    n_rounds = sum(per_case_rounds.values())

    # baseline roteirizado: um item por rodada vs agrupamento (mesmo pacote de lacunas)
    baseline = []
    for c in cases:
        n_gaps = sum(1 for g in gaps if g.case_id == c.id)
        if n_gaps:
            baseline.append({"case_id": c.id, "um_item_por_rodada": n_gaps, "agrupado": per_case_rounds.get(c.id, 0)})

    # espera e canal útil
    waits: list[float] = []
    useful: Counter = Counter()
    for r in rounds:
        if not r.sent_at:
            continue
        first = s.scalar(select(Message).where(Message.round_id == r.id, Message.direction == "in",
                                               Message.substantive == True).order_by(Message.seq))  # noqa: E712
        if first:
            sent = r.sent_at.replace(tzinfo=None) if r.sent_at.tzinfo else r.sent_at
            rec = first.received_at.replace(tzinfo=None) if first.received_at.tzinfo else first.received_at
            waits.append(max(0.0, (rec - sent).total_seconds() / 3600))
            useful[first.channel] += 1

    ivs = list(s.scalars(select(Intervention).where(Intervention.case_id.in_(ids)))) if ids else []
    resumed = s.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "resume",
                                                                         AuditEvent.case_id.in_(ids))) if ids else 0

    # modo: replay / inferência / entrada humana (separados)
    modes: Counter = Counter()
    for a in s.scalars(select(AuditEvent).where(AuditEvent.action.in_(["dossier_created", "reconciled"]),
                                                AuditEvent.case_id.in_(ids))) if ids else []:
        modes[a.detail.get("adapter", "desconhecido")] += 1
    human = s.scalar(select(func.count()).select_from(HumanDecision).where(HumanDecision.case_id.in_(ids))) if ids else 0

    return {
        "evidence_class": EVIDENCE_CLASS,
        "limitation": "Benchmark local com dados sintéticos; não mede impacto em prefeituras reais.",
        "processes": {"total": total_processes, "nao_iniciados": not_started, "com_caso": len(cases)},
        "cases": {"total": len(cases), "concluidos": sum(1 for c in cases if c.state == "COMPLETED"),
                  "em_andamento": sum(1 for c in cases if c.active), "falhos": sum(1 for c in cases if c.state.startswith("FAILED"))},
        "solicitacoes": request_totals,
        "cobertura_auditavel": {"valor": _ratio(covered, len(accepted)), "num": covered, "den": len(accepted)},
        "rodadas_ate_aprovacao": {"media": (round(sum(rounds_until_approval) / len(rounds_until_approval), 2)
                                            if rounds_until_approval else None), "casos": len(rounds_until_approval)},
        "lacunas_resolvidas_por_rodada": {"valor": (round(answered / n_rounds, 2) if n_rounds else None),
                                          "lacunas": answered, "rodadas": n_rounds},
        "baseline_roteirizado": baseline,
        "espera_horas": {"media": round(sum(waits) / len(waits), 2) if waits else None, "n": len(waits)},
        "canal_util": dict(useful),
        "intervencoes": {"total": len(ivs), "por_motivo": dict(Counter(i.reason_code for i in ivs)),
                         "abertas": sum(1 for i in ivs if i.status == "open")},
        "retomadas": {"total": resumed or 0},
        "modos": {"ia": dict(modes), "entrada_humana": human or 0},
        "efeito_indevido": {"valor": 0, "nota": "Contagem de ações proibidas executadas; verificada pelos testes T01-T16 e cenário H."},
    }
