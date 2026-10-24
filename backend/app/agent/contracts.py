"""Contratos fechados das ações do agente (v2 §11.2). extra=forbid, limites e enums.

O agente propõe; o backend valida citações, catálogo e permissões antes de qualquer efeito.
Citações apontam para fontes por referência ordinal: TICKET (resposta inicial) ou S1, S2...
(mensagens, artefatos derivados e decisões humanas, na ordem de recepção). O backend resolve
cada referência para a fonte persistida e confere o trecho literal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.changeset import Operation

Clarity = Literal["clear", "partial", "ambiguous", "unknown"]
Feasibility = Literal["supported", "supported_with_conditions", "requires_product_review", "unsupported", "unknown"]
Risk = Literal["low", "medium", "high"]
NextAction = Literal["propose_change", "clarify", "find_owner", "escalate", "reject", "wait"]
AnswerKind = Literal["yes_no", "choose_options", "number", "text", "document"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCitation(Strict):
    source_ref: str = Field(pattern=r"^(TICKET|S[0-9]{1,3})$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)


class RequestProposal(Strict):
    summary: str = Field(min_length=1, max_length=500)
    evidence_indexes: list[int] = Field(min_length=1, max_length=5)
    clarity: Clarity
    feasibility: Feasibility
    risk: Risk
    next_action: NextAction


class GapProposal(Strict):
    request_index: int = Field(ge=0, description="índice em requests desta saída")
    question: str = Field(min_length=3, max_length=400)
    answer_kind: AnswerKind = "text"
    options: list[str] = Field(default_factory=list, max_length=12)
    topic: str = Field(default="geral", max_length=40)
    blocking: bool = True


class GapUpdate(Strict):
    gap_ref: str = Field(pattern=r"^G[0-9]{1,3}$")
    status: Literal["answered", "disputed", "obsolete"]
    evidence_indexes: list[int] = Field(default_factory=list, max_length=5)
    note: str = Field(default="", max_length=500)


class OperationProposal(Strict):
    operation: Operation
    evidence_indexes: list[int] = Field(min_length=1, max_length=5)


class TestProposal(Strict):
    name: str
    kind: Literal["positivo", "negativo", "limite", "identidade"]
    inputs: dict
    expected_codes: list[str]
    requirement: str = ""


class ChangeSetProposal(Strict):
    rationale: str = Field(max_length=1000)
    operations: list[OperationProposal] = Field(max_length=20)
    tests: list[TestProposal] = Field(max_length=20)


class InterventionProposal(Strict):
    code: str = Field(max_length=40)
    reason: str = Field(max_length=500)
    needed_decision: str = Field(default="", max_length=500)
    urgency: Literal[1, 2, 3] = 2


class AgentOutput(Strict):
    """Saída completa de uma análise (tudo ou nada)."""

    schema_version: Literal[1] = 1
    stage: Literal["initial", "reconcile"]
    evidence: list[SourceCitation] = Field(default_factory=list, max_length=40)
    requests: list[RequestProposal] = Field(default_factory=list, max_length=20)
    gaps: list[GapProposal] = Field(default_factory=list, max_length=20)
    gap_updates: list[GapUpdate] = Field(default_factory=list, max_length=40)
    change_set: ChangeSetProposal | None = None
    intervention: InterventionProposal | None = None
    no_safe_action: str | None = Field(default=None, max_length=500)


class AgentEnvelope(AgentOutput):
    """Saída + metadados que o backend acrescenta (o modelo nunca define autoridade)."""

    case_id: str
    expected_case_version: int
