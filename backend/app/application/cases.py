"""Ticket -> caso -> dossiê -> ChangeSet candidata (v2 §7, §9, §11)."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..clock import business_now
from ..domain.forms import FormSchema, canonical_bytes, schema_hash, validate_schema
from ..persistence.models import (
    ChangeRequest, ChangeSet, Evidence, FormTestCase, FormVersion, ProcessDefinition, Ticket,
    ValidationCase, new_id,
)
from .common import AppError, audit, enqueue, move_case, open_intervention


def load_schema(version: FormVersion) -> FormSchema:
    return FormSchema.model_validate_json(version.content)


def store_version(s: Session, process: ProcessDefinition, schema: FormSchema,
                  base_version_id: str | None) -> FormVersion:
    nxt = (s.scalar(select(func.max(FormVersion.version)).where(FormVersion.process_id == process.id)) or 0) + 1
    content = canonical_bytes(schema)
    v = FormVersion(id=new_id("fv_"), process_id=process.id, version=nxt, base_version_id=base_version_id,
                    content=content.decode("utf-8"), sha256=schema_hash(schema), created_at=business_now())
    s.add(v)
    s.flush()
    return v


def create_ticket(s: Session, *, process_id: str, title: str, description: str, initial_reply: str,
                  actor: str) -> Ticket:
    process = s.get(ProcessDefinition, process_id)
    if process is None:
        raise AppError("NOT_FOUND", "processo inexistente", 404)
    t = Ticket(id=new_id("tk_"), municipality_id=process.municipality_id, process_id=process.id,
               title=title, description=description, initial_reply=initial_reply, created_at=business_now())
    s.add(t)
    audit(s, actor=actor, action="ticket_created", municipality_id=process.municipality_id,
          detail={"ticket_id": t.id})
    return t


def start_case(s: Session, ticket_id: str, actor: str) -> ValidationCase:
    """DRAFT -> INTAKE -> UNDERSTANDING_FORM; fixa a base e agenda a leitura do schema."""
    ticket = s.get(Ticket, ticket_id)
    if ticket is None:
        raise AppError("NOT_FOUND", "ticket inexistente", 404)
    process = s.get(ProcessDefinition, ticket.process_id)
    if not process.current_version_id:
        raise AppError("NO_BASE_FORM", "processo sem formulário vigente", 409)
    active = s.scalar(select(ValidationCase).where(ValidationCase.ticket_id == ticket.id,
                                                   ValidationCase.active == True))  # noqa: E712
    if active:
        raise AppError("CASE_ALREADY_ACTIVE", "já existe um ciclo ativo para este ticket", 409,
                       {"case_id": active.id})
    cycle = (s.scalar(select(func.max(ValidationCase.cycle_number)).where(
        ValidationCase.ticket_id == ticket.id)) or 0) + 1
    prev = s.scalar(select(ValidationCase.id).where(ValidationCase.ticket_id == ticket.id,
                                                    ValidationCase.cycle_number == cycle - 1))
    case = ValidationCase(id=new_id("cs_"), municipality_id=ticket.municipality_id, ticket_id=ticket.id,
                          process_id=process.id, cycle_number=cycle, previous_case_id=prev, state="DRAFT",
                          base_version_id=process.current_version_id, next_action="Ler o formulário",
                          state_since=business_now())
    s.add(case)
    try:
        s.flush()
    except IntegrityError as e:
        raise AppError("CASE_ALREADY_ACTIVE", "já existe um ciclo ativo para este ticket", 409) from e
    process.started = True
    audit(s, actor=actor, action="case_created", case=case, why="Caso criado a partir do ticket")
    move_case(s, case, "start", actor=actor, why="Ticket válido; versão-base fixada")
    move_case(s, case, "ticket_persisted", actor=actor, why="Ticket e referência persistidos")
    enqueue(s, "understand_form", case.id, dedupe_key=f"understand:{case.id}")
    return case


# ---------------------------------------------------------------- worker


def handle_understand_form(s: Session, case: ValidationCase) -> None:
    base = s.get(FormVersion, case.base_version_id)
    errors = validate_schema(load_schema(base))
    if errors:
        open_intervention(s, case, code="SCHEMA_INVALIDO", reason="O formulário-base não passou na validação: "
                          + "; ".join(errors[:3]), needed="Corrigir o formulário-base")
        move_case(s, case, "integrity_error", actor="sistema", why="Schema-base inválido")
        return
    move_case(s, case, "schema_validated", actor="sistema", why="Schema-base validado")
    enqueue(s, "analyze_initial_reply", case.id, dedupe_key=f"analyze:{case.id}")


def handle_analyze(s: Session, case: ValidationCase) -> None:
    from . import flow  # evita ciclo de import
    flow.handle_analyze(s, case)
