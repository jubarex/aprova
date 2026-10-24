from datetime import timedelta

from sqlalchemy import select

from app import clock
from app.application import cases, rounds, scenario_runner, messaging
from app.application.common import get_actor
from app.persistence.db import tx
from app.persistence.flow_models import Gap, Message, RoundItem, ValidationRound
from app.persistence.models import ValidationCase
from app.scenarios import SCENARIOS
from app.worker import runner


def start(factory, sid):
    sc = SCENARIOS[sid]
    with tx(factory) as s:
        t = cases.create_ticket(s, process_id=sc["process_id"], title=sc["ticket_title"], description="",
                                initial_reply=sc["reply"], actor="act_rui")
        return cases.start_case(s, t.id, "act_rui").id


def settle(factory, release=True, rounds_=40):
    """Executa o worker até estabilizar; avança o relógio de negócio para fechar janelas e libera primeiras mensagens."""
    for _ in range(rounds_):
        n = runner.drain(factory)
        released = 0
        if release:
            with tx(factory) as s:
                for c in s.scalars(select(ValidationCase).where(ValidationCase.state == "ROUND_READY")):
                    rnd = rounds.active_round(s, c.id)
                    rounds.release_round(s, c, rnd, "act_rui")
                    released += 1
        clock.advance(0.002)  # ~7 s de negócio
        if n == 0 and released == 0:
            more = runner.drain(factory)
            if more == 0:
                return


def state(factory, cid):
    with tx(factory) as s:
        return s.get(ValidationCase, cid).state


def step(factory, tmp_path, cid, step_id):
    with tx(factory) as s:
        case = s.get(ValidationCase, cid)
        out = scenario_runner.run_step(s, tmp_path / "att", case, step_id, get_actor(s, "act_rui"))
    return out


def gaps(factory, cid):
    with tx(factory) as s:
        return {g.ref: g.status for g in s.scalars(select(Gap).where(Gap.case_id == cid))}


def rounds_of(factory, cid):
    with tx(factory) as s:
        return [(r.seq, r.recipient_id, r.status) for r in s.scalars(
            select(ValidationRound).where(ValidationRound.case_id == cid).order_by(ValidationRound.seq))]
