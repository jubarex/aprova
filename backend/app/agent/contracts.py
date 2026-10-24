"""Contratos fechados das ações do agente (v2 §11.2). extra=forbid, limites e enums.

O agente propõe; o backend valida citações, catálogo e permissões antes de qualquer efeito.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain.changeset import Operation

Clarity = Literal["clear", "partial", "ambiguous", "unknown"]
Feasibility = Literal["supported", "supported_with_conditions", "requires_product_review", "unsupported", "unknown"]
Risk = Literal["low", "medium", "high"]
NextAction = Literal["propose_change", "clarify", "find_owner", "escalate", "reject", "wait"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Citation(Strict):
    source: Literal["ticket_initial_reply"]
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)


class ChangeRequestProposal(Strict):
    summary: str = Field(min_length=1, max_length=500)
    citation: Citation
    clarity: Clarity
    feasibility: Feasibility
    risk: Risk
    next_action: NextAction


class ProposeChangeRequests(Strict):
    action_type: Literal["propose_change_requests"] = "propose_change_requests"
    requests: list[ChangeRequestProposal] = Field(max_length=20)


class OperationProposal(Strict):
    operation: Operation
    citation_indexes: list[int] = Field(min_length=1, description="índices em ProposeChangeRequests.requests")


class ProposeChangeSet(Strict):
    action_type: Literal["propose_change_set"] = "propose_change_set"
    rationale: str = Field(max_length=1000)
    operations: list[OperationProposal] = Field(max_length=20)
    tests: list["TestProposal"] = Field(max_length=20)


class TestProposal(Strict):
    name: str
    kind: Literal["positivo", "negativo", "limite", "identidade"]
    inputs: dict
    expected_codes: list[str]
    requirement: str = ""


ProposeChangeSet.model_rebuild()


class AgentEnvelope(Strict):
    """Envelope completo de uma análise inicial: tudo ou nada."""

    schema_version: Literal[1] = 1
    case_id: str
    expected_case_version: int
    change_requests: ProposeChangeRequests
    change_set: ProposeChangeSet | None = None
