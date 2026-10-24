"""Popula a demonstração com um dia de trabalho realista: cada cenário em um estado diferente.

Usa os mesmos serviços e o mesmo worker da aplicação (nada é inserido "por fora"), então os casos
carregam auditoria, evidências e recibos como os criados à mão. Idempotente: não faz nada se já há casos.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ..clock import business_now
from ..persistence.db import tx
from ..persistence.models import ChangeSet, ProcessDefinition, ValidationCase
from ..scenarios import SCENARIOS
from ..worker import runner
from . import cases, changes, messaging, rounds, scenario_runner
from .common import get_actor


def _drain(f: sessionmaker[Session], release: set[str] | None = None) -> None:
    """Executa o worker até estabilizar; libera a primeira mensagem só dos casos indicados."""
    release = release or set()
    for _ in range(40):
        n = runner.drain(f)
        freed = 0
        with tx(f) as s:
            for c in s.scalars(select(ValidationCase).where(ValidationCase.state == "ROUND_READY")):
                if c.id in release:
                    rounds.release_round(s, c, rounds.active_round(s, c.id), "act_rui")
                    freed += 1
        if n == 0 and freed == 0:
            return


def _start(f, sid: str) -> str:
    sc = SCENARIOS[sid]
    with tx(f) as s:
        t = cases.create_ticket(s, process_id=sc["process_id"], title=sc["ticket_title"], description="Dados de exemplo",
                                initial_reply=sc["reply"], actor="act_rui")
        return cases.start_case(s, t.id, "act_rui").id


def _step(f, att_dir, cid: str, step_id: str) -> None:
    with tx(f) as s:
        scenario_runner.run_step(s, att_dir, s.get(ValidationCase, cid), step_id, get_actor(s, "act_rui"))


def populate(f: sessionmaker[Session], att_dir) -> dict:
    with tx(f) as s:
        if s.scalar(select(func.count()).select_from(ValidationCase)):
            return {"skipped": True, "reason": "já existem casos; use Restaurar para recomeçar"}
    quiet = messaging.QUIET_SECONDS
    messaging.QUIET_SECONDS = 0  # sem espera artificial da janela de rajada ao popular
    out: dict[str, str] = {}
    try:
        # G — a prefeitura já aprovou pelo Portal; falta a aprovação da Aprova (tarefa no Hoje)
        g = _start(f, "G"); _drain(f)
        with tx(f) as s:
            cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == g))
            csid = cs.id
            changes.review_tests(s, cs, get_actor(s, "act_rui"))
        with tx(f) as s:
            changes.submit_for_approval(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), s.get(ValidationCase, g).version)
        with tx(f) as s:
            changes.decide_municipal(s, s.get(ChangeSet, csid), get_actor(s, "act_ana"), decision="approve",
                                     expected_version=s.get(ValidationCase, g).version, channel="portal")
        out["G"] = g

        # A — rodada enviada à Ana; ela respondeu parte pelo Portal (resta uma lacuna + a rodada de Obras)
        a = _start(f, "A"); _drain(f, {a}); _step(f, att_dir, a, "a1"); _drain(f, {a})
        out["A"] = a

        # B — Vigilância sem responsável; Ana indicou o técnico, falta o implantador autorizar o escopo
        b = _start(f, "B"); _drain(f); _step(f, att_dir, b, "b1"); _drain(f)
        out["B"] = b

        # C — primeira mensagem a João aguarda a revisão do implantador
        out["C"] = _start(f, "C"); _drain(f)

        # D — Marcos e Luiza se contradizem: conflito aguardando a decisão
        d = _start(f, "D"); _drain(f, {d}); _step(f, att_dir, d, "d1"); _step(f, att_dir, d, "d2"); _drain(f)
        out["D"] = d

        # E — pedido fora do playbook aguardando decisão humana
        out["E"] = _start(f, "E"); _drain(f)

        # prazos variados no cronograma: alguns atrasados e alguns em risco (sem caso iniciado)
        with tx(f) as s:
            now = business_now()
            for mid in ("vr", "sa"):
                for i, delta in enumerate((-3, -1, 1, 3)):
                    p = s.get(ProcessDefinition, f"proc_{mid}_f{i:03d}")
                    if p and not p.started:
                        p.due_date = now + timedelta(days=delta)
    finally:
        messaging.QUIET_SECONDS = quiet
    return {"skipped": False, "cases": out}
