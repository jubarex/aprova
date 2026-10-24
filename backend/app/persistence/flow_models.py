"""Fatias 2-3: lacunas, rodadas, mensagens, anexos, indicações e decisões humanas (v2 §5.1, §8)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id, utcnow


class Gap(Base):
    """Informação faltante que bloqueia a candidata até ser respondida."""

    __tablename__ = "gap"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("gap_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("change_request.id"))
    ref: Mapped[str] = mapped_column(String)  # G1, G2... estável dentro do caso
    question: Mapped[str] = mapped_column(Text)
    answer_kind: Mapped[str] = mapped_column(String, default="text")  # yes_no | choose_options | number | text | document
    options: Mapped[list] = mapped_column(JSON, default=list)
    topic: Mapped[str] = mapped_column(String, default="geral")
    blocking: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String, default="open")  # open | answered | obsolete | disputed
    answer_evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("case_id", "ref"),)


class ValidationRound(Base):
    __tablename__ = "validation_round"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("rd_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"))
    seq: Mapped[int] = mapped_column(Integer)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("actor.id"))
    objective: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    grouping_note: Mapped[str] = mapped_column(Text, default="")
    # planned | ready | sending | waiting | completed | superseded
    status: Mapped[str] = mapped_column(String, default="planned")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    primary_channel: Mapped[str | None] = mapped_column(String)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (
        UniqueConstraint("case_id", "seq"),
        # uma rodada ativa por caso (I04)
        Index("uq_round_active", "case_id", unique=True,
              sqlite_where=(status.in_(["ready", "sending", "waiting"]))),
    )


class RoundItem(Base):
    __tablename__ = "round_item"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("ri_"))
    round_id: Mapped[str] = mapped_column(ForeignKey("validation_round.id"), index=True)
    gap_id: Mapped[str] = mapped_column(ForeignKey("gap.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text, default="")
    answer_kind: Mapped[str] = mapped_column(String, default="text")
    options: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="open")  # open | answered
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    """Mensagem de qualquer canal; persistida antes de ser interpretada (I02)."""

    __tablename__ = "message"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("msg_"))
    seq: Mapped[int] = mapped_column(Integer, index=True)  # sequência de recepção persistida
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)  # pylon | whatsapp | portal
    direction: Mapped[str] = mapped_column(String)  # in | out
    body: Mapped[str] = mapped_column(Text)
    body_hash: Mapped[str] = mapped_column(String(64))
    round_id: Mapped[str | None] = mapped_column(String, index=True)
    round_item_id: Mapped[str | None] = mapped_column(String)
    part: Mapped[int] = mapped_column(Integer, default=0)
    external_key: Mapped[str | None] = mapped_column(String)
    mirror_of_message_id: Mapped[str | None] = mapped_column(String)
    substantive: Mapped[bool] = mapped_column(Boolean, default=False)
    consolidated: Mapped[bool] = mapped_column(Boolean, default=False)
    triage_status: Mapped[str | None] = mapped_column(String)  # pending | linked
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("channel", "external_key"),)


class Attachment(Base):
    __tablename__ = "attachment"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("att_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"))
    message_id: Mapped[str] = mapped_column(ForeignKey("message.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    internal_name: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String, default="stored")  # stored | extracted | needs_review | reviewed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DerivedArtifact(Base):
    __tablename__ = "derived_artifact"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("da_"))
    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachment.id"), index=True)
    case_id: Mapped[str] = mapped_column(String, index=True)
    text: Mapped[str] = mapped_column(Text, default="")
    adapter: Mapped[str] = mapped_column(String)  # native_text | simulated_sidecar | none
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String)  # ok | unsupported
    source_hash: Mapped[str] = mapped_column(String(64))
    consolidated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HumanDecision(Base):
    __tablename__ = "human_decision"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("hd_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)  # resolve_conflict | provide_answer | fix_interpretation | dispose_request | review_attachment
    text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    consolidated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContactReferral(Base):
    """Indicação: quem indicou quem e qual assunto foi transferido (v2 §8.3)."""

    __tablename__ = "contact_referral"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("rf_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    municipality_id: Mapped[str] = mapped_column(ForeignKey("municipality.id"))
    from_actor_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    sector: Mapped[str] = mapped_column(String, default="")
    alias: Mapped[str] = mapped_column(String, default="")
    topic: Mapped[str] = mapped_column(String, default="geral")
    gap_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | authorized | rejected
    new_actor_id: Mapped[str | None] = mapped_column(String)
    decided_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChannelDecision(Base):
    """Canal principal por destinatário no caso (v2 §8.2)."""

    __tablename__ = "channel_decision"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("cd_"))
    case_id: Mapped[str] = mapped_column(ForeignKey("validation_case.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)  # preferencia_explicita | primeira_resposta
    __table_args__ = (UniqueConstraint("case_id", "actor_id"),)


class PortalAccess(Base):
    """Link mágico por contato: guarda só o hash do token (adendo v2.1 §5.4)."""

    __tablename__ = "portal_access"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("pa_"))
    actor_id: Mapped[str] = mapped_column(String, index=True)
    municipality_id: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResponsibilityClaim(Base):
    """Declaração do contato no primeiro acesso. É só uma declaração: não concede papel (I18)."""

    __tablename__ = "responsibility_claim"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("rc_"))
    actor_id: Mapped[str] = mapped_column(String, index=True)
    municipality_id: Mapped[str] = mapped_column(String, index=True)
    process_id: Mapped[str] = mapped_column(String)
    answer: Mapped[str] = mapped_column(String)  # mine | refer | unknown
    refer_name: Mapped[str] = mapped_column(String, default="")
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("actor_id", "process_id"),)


class ContactOnboarding(Base):
    __tablename__ = "contact_onboarding"
    actor_id: Mapped[str] = mapped_column(String, primary_key=True)
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_access_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    identity_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_channel_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
