"""Modelos SQLAlchemy (plano v2 §5.1 + adendo v2.1 §9).

Datas em UTC, IDs estáveis (texto), JSON validado nas fronteiras.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Municipality(Base):
    __tablename__ = "municipality"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    short: Mapped[str] = mapped_column(String(4))
    city: Mapped[str] = mapped_column(String)
    color_slot: Mapped[int] = mapped_column(Integer, default=1)
    # Implantação (uma por prefeitura na demo)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portal_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pylon_mirror_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_item_budget: Mapped[int] = mapped_column(Integer, default=5)


class Secretariat(Base):
    __tablename__ = "secretariat"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    name: Mapped[str] = mapped_column(String)


class Actor(Base):
    """Persona sintética (implantador, aprovador Aprova, contato da prefeitura)."""

    __tablename__ = "actor"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # implantador | aprova | contato | operador
    municipality_id: Mapped[str | None] = mapped_column(ForeignKey("municipality.id"), index=True)
    secretariat_id: Mapped[str | None] = mapped_column(ForeignKey("secretariat.id"))
    preferred_channel: Mapped[str | None] = mapped_column(String)


class RoleAssignment(Base):
    """Papel por processo/escopo. Responder != aprovar (v2 §8.3, I07)."""

    __tablename__ = "role_assignment"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ra_"))
    actor_id: Mapped[str] = mapped_column(ForeignKey("actor.id"), index=True)
    process_id: Mapped[str | None] = mapped_column(ForeignKey("process_definition.id"), index=True)
    municipality_id: Mapped[str | None] = mapped_column(ForeignKey("municipality.id"))
    role: Mapped[str] = mapped_column(String)  # municipal_approver | aprova_approver | responder | implanter
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessDefinition(Base):
    __tablename__ = "process_definition"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    secretariat_id: Mapped[str | None] = mapped_column(ForeignKey("secretariat.id"))
    code: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    wave: Mapped[int] = mapped_column(Integer, default=1)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Ponteiro vigente do motor de formulários simulado (compare-and-swap em apply)
    current_version_id: Mapped[str | None] = mapped_column(String)
    started: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("municipality_id", "code"),)


class FormVersion(Base):
    """Snapshot imutável do formulário (v2 §7.1)."""

    __tablename__ = "form_version"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    process_id: Mapped[str] = mapped_column(ForeignKey("process_definition.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    base_version_id: Mapped[str | None] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)  # bytes canônicos em UTF-8
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("process_id", "version"),)


class Ticket(Base):
    __tablename__ = "ticket"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    process_id: Mapped[str] = mapped_column(ForeignKey("process_definition.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    initial_reply: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TicketComment(Base):
    __tablename__ = "ticket_comment"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("tc_"))
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    visibility: Mapped[str] = mapped_column(String)  # public | internal
    author: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    external_key: Mapped[str | None] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ValidationCase(Base):
    __tablename__ = "validation_case"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("ticket.id"), index=True)
    process_id: Mapped[str] = mapped_column(ForeignKey("process_definition.id"), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer, default=1)
    previous_case_id: Mapped[str | None] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, index=True)
    resume_state: Mapped[str | None] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)  # revisão otimista
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    base_version_id: Mapped[str | None] = mapped_column(String)
    next_action: Mapped[str] = mapped_column(String, default="")
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    state_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("ticket_id", "cycle_number"),
        # no máximo um ciclo ativo por ticket (índice parcial no SQLite)
        Index("uq_case_active_ticket", "ticket_id", unique=True, sqlite_where=(active == True)),  # noqa: E712
    )


class ChangeRequest(Base):
    __tablename__ = "change_request"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("cr_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    source_quote: Mapped[str] = mapped_column(Text, default="")
    clarity: Mapped[str] = mapped_column(String, default="clear")
    feasibility: Mapped[str] = mapped_column(String, default="supported")
    risk: Mapped[str] = mapped_column(String, default="low")
    next_action: Mapped[str] = mapped_column(String, default="propose_change")
    disposition: Mapped[str] = mapped_column(String, default="pending")


class ChangeSet(Base):
    __tablename__ = "change_set"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("cs_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    process_id: Mapped[str] = mapped_column(ForeignKey("process_definition.id"))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    base_version_id: Mapped[str] = mapped_column(ForeignKey("form_version.id"))
    operations: Mapped[list] = mapped_column(JSON)
    candidate_content: Mapped[str] = mapped_column(Text)
    candidate_hash: Mapped[str] = mapped_column(String(64))
    # draft | testing | ready | approved_municipal | approved | applied | verified | superseded | rejected
    status: Mapped[str] = mapped_column(String, default="draft", index=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    applied_version_id: Mapped[str | None] = mapped_column(String)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FormTestCase(Base):
    __tablename__ = "form_test_case"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("tcase_"))
    change_set_id: Mapped[str] = mapped_column(ForeignKey("change_set.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # positivo | negativo | limite | identidade
    inputs: Mapped[dict] = mapped_column(JSON)
    expected_codes: Mapped[list] = mapped_column(JSON)  # códigos de erro esperados; [] = válido
    requirement: Mapped[str] = mapped_column(Text, default="")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suite_revision: Mapped[int] = mapped_column(Integer, default=1)


class FormTestRun(Base):
    __tablename__ = "form_test_run"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("trun_"))
    change_set_id: Mapped[str] = mapped_column(ForeignKey("change_set.id"), index=True)
    phase: Mapped[str] = mapped_column(String)  # pre_approval | post_readback
    candidate_hash: Mapped[str] = mapped_column(String(64))
    suite_hash: Mapped[str] = mapped_column(String(64))
    results: Mapped[list] = mapped_column(JSON)
    passed: Mapped[bool] = mapped_column(Boolean)
    executor: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Approval(Base):
    __tablename__ = "approval"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ap_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    change_set_id: Mapped[str] = mapped_column(ForeignKey("change_set.id"), index=True)
    base_form_version_id: Mapped[str] = mapped_column(String)
    candidate_hash: Mapped[str] = mapped_column(String(64))
    test_suite_hash: Mapped[str] = mapped_column(String(64))
    test_run_id: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(ForeignKey("actor.id"))
    approver_role: Mapped[str] = mapped_column(String)  # municipal | aprova
    decision: Mapped[str] = mapped_column(String)  # approve | reject | revoke
    rationale: Mapped[str] = mapped_column(Text, default="")
    channel: Mapped[str] = mapped_column(String, default="command")  # command | portal
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_reason: Mapped[str | None] = mapped_column(Text)


class Intervention(Base):
    __tablename__ = "intervention"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("iv_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    reason_code: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    needed_decision: Mapped[str] = mapped_column(Text, default="")
    urgency: Mapped[int] = mapped_column(Integer, default=2)  # 1 alta .. 3 baixa
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("au_"))
    seq: Mapped[int] = mapped_column(Integer, index=True)
    case_id: Mapped[str | None] = mapped_column(String, index=True)
    municipality_id: Mapped[str | None] = mapped_column(String, index=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    from_state: Mapped[str | None] = mapped_column(String)
    to_state: Mapped[str | None] = mapped_column(String)
    case_version: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    why: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkItem(Base):
    __tablename__ = "work_item"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("wi_"))
    case_id: Mapped[str | None] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | running | done | failed | cancelled
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String, unique=True)
    error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("ix_work_status_avail", "status", "available_at"),)


class OutboxMessage(Base):
    __tablename__ = "outbox_message"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ob_"))
    case_id: Mapped[str | None] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String)  # apply | note | close | send
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_token: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class EffectReceipt(Base):
    """Comprovante único de aplicação, verificação, nota ou fechamento (I11)."""

    __tablename__ = "effect_receipt"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("rc_"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    kind: Mapped[str] = mapped_column(String)
    case_id: Mapped[str | None] = mapped_column(String, index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    """Unicidade HTTP: (ator, operação, recurso, chave) - v2 §13.1."""

    __tablename__ = "idempotency_record"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ik_"))
    actor_id: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    resource: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    payload_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("actor_id", "operation", "resource", "key"),)


class DemoSession(Base):
    __tablename__ = "demo_session"
    token: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("actor.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Evidence(Base):
    """Citação verificável: offsets [start,end) em pontos de código Unicode (v2 §5.3)."""

    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ev_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"))
    source_type: Mapped[str] = mapped_column(String)  # ticket_initial_reply | message | derived | human_decision
    source_id: Mapped[str] = mapped_column(String)
    source_hash: Mapped[str] = mapped_column(String(64))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
