"""Worker local: claim atômico com lease/token, retry 1s/5s, recuperação de leases vencidos (v2 §10)."""

from __future__ import annotations

import secrets
import time
from datetime import timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ..application import cases, changes
from ..application.common import AppError, audit, move_case, open_intervention
from ..clock import business_now, real_now
from ..persistence.db import tx
from ..persistence.models import ChangeSet, ValidationCase, WorkItem

LEASE_SECONDS = 120
BACKOFF = [1, 5]
MAX_ATTEMPTS = 3
_heartbeat = {"at": None, "last_error": None}


class LeaseLost(Exception):
    pass


def heartbeat() -> dict:
    return dict(_heartbeat)


def claim(factory: sessionmaker[Session]) -> tuple[str, str] | None:
    now = real_now()
    with tx(factory) as s:
        row = s.scalar(select(WorkItem).where(WorkItem.status == "pending", WorkItem.available_at <= business_now())
                       .order_by(WorkItem.available_at, WorkItem.id).limit(1))
        if row is None:
            return None
        token = secrets.token_hex(8)
        res = s.execute(update(WorkItem).where(WorkItem.id == row.id, WorkItem.status == "pending")
                        .values(status="running", lease_token=token, lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
                                attempts=WorkItem.attempts + 1))
        if res.rowcount != 1:
            return None
        return row.id, token


def finish(factory, job_id: str, token: str, status: str = "done", error: str | None = None) -> None:
    with tx(factory) as s:
        res = s.execute(update(WorkItem).where(WorkItem.id == job_id, WorkItem.lease_token == token,
                                               WorkItem.status == "running")
                        .values(status=status, error=error, lease_token=None))
        if res.rowcount != 1:
            raise LeaseLost(job_id)  # token antigo não confirma trabalho (T14)


def recover_leases(factory) -> int:
    with tx(factory) as s:
        res = s.execute(update(WorkItem).where(WorkItem.status == "running", WorkItem.lease_expires_at < real_now())
                        .values(status="pending", lease_token=None, available_at=business_now()))
        return res.rowcount


def _run_handler(factory, job: WorkItem) -> None:
    cid = job.case_id
    if job.kind in ("understand_form", "analyze_initial_reply"):
        with tx(factory) as s:
            case = s.get(ValidationCase, cid)
            expect = {"understand_form": "UNDERSTANDING_FORM", "analyze_initial_reply": "ANALYZING_INITIAL_REPLY"}[job.kind]
            if case.state != expect:
                return  # obsoleto: cancelado sem efeito
            (cases.handle_understand_form if job.kind == "understand_form" else cases.handle_analyze)(s, case)
    elif job.kind == "apply_change_set":
        cs_id = job.payload["change_set_id"]
        try:
            with tx(factory) as s:
                changes.apply_change_set(s, cs_id)
            changes.maybe_crash("after_apply_commit")
        except changes.BaseVersionConflict:
            with tx(factory) as s:
                changes.handle_base_conflict(s, cs_id)
    elif job.kind == "verify_change_set":
        with tx(factory) as s:
            changes.verify_change_set(s, job.payload["change_set_id"])
    elif job.kind == "close_ticket":
        with tx(factory) as s:
            changes.close_ticket(s, job.payload["change_set_id"])
    else:
        raise AppError("UNKNOWN_JOB", job.kind, 500)


def run_one(factory: sessionmaker[Session]) -> bool:
    _heartbeat["at"] = real_now().isoformat()
    recover_leases(factory)
    got = claim(factory)
    if got is None:
        return False
    job_id, token = got
    with tx(factory) as s:
        job = s.get(WorkItem, job_id)
        s.expunge(job)
    try:
        _run_handler(factory, job)
    except AppError as e:  # regra de negócio: não retenta
        _heartbeat["last_error"] = e.code
        finish(factory, job_id, token, "failed", f"{e.code}: {e.message}")
        return True
    except Exception as e:  # falha transitória: retry 1s/5s
        _heartbeat["last_error"] = type(e).__name__
        _retry_or_fail(factory, job, token, e)
        return True
    finish(factory, job_id, token)
    return True


def _retry_or_fail(factory, job: WorkItem, token: str, err: Exception) -> None:
    with tx(factory) as s:
        w = s.get(WorkItem, job.id)
        if w.lease_token != token:
            raise LeaseLost(job.id)
        if w.attempts < MAX_ATTEMPTS:
            w.status, w.lease_token = "pending", None
            w.available_at = business_now() + timedelta(seconds=BACKOFF[min(w.attempts - 1, len(BACKOFF) - 1)])
            w.error = f"{type(err).__name__}: {err}"
            return
        w.status, w.lease_token, w.error = "failed", None, f"{type(err).__name__}: {err}"
        if w.case_id:
            case = s.get(ValidationCase, w.case_id)
            open_intervention(s, case, code="TRABALHO_FALHOU", urgency=1,
                              reason=f"A tarefa '{w.kind}' falhou após {MAX_ATTEMPTS} tentativas.",
                              needed="Investigar a falha e retomar")
            if case.state not in ("COMPLETED", "BLOCKED_HUMAN"):
                try:
                    move_case(s, case, "transient_failure", actor="sistema", why="Falha transitória")
                    move_case(s, case, "retry_exhausted", actor="sistema", why="Tentativas esgotadas")
                except AppError:
                    pass


def drain(factory, limit: int = 200) -> int:
    """Executa tudo que está disponível (testes e modo síncrono)."""
    n = 0
    while n < limit and run_one(factory):
        n += 1
    return n


def loop(factory, stop: Callable[[], bool], interval: float = 0.5) -> None:
    while not stop():
        try:
            if not run_one(factory):
                time.sleep(interval)
        except changes.SimulatedCrash:
            pass
        except Exception:  # o worker nunca morre por erro de um job
            time.sleep(interval)
