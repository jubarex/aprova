"""Tabela declarativa estado + evento -> destino (plano v2 §9.1).

Combinação não registrada levanta InvalidTransition, sem efeitos.
Guardas dependentes de dados ficam nos serviços; aqui só a topologia.
"""

from __future__ import annotations

from enum import StrEnum


class CaseState(StrEnum):
    DRAFT = "DRAFT"
    INTAKE = "INTAKE"
    UNDERSTANDING_FORM = "UNDERSTANDING_FORM"
    ANALYZING_INITIAL_REPLY = "ANALYZING_INITIAL_REPLY"
    BUILDING_ROUND = "BUILDING_ROUND"
    ROUND_READY = "ROUND_READY"
    SENDING_ROUND = "SENDING_ROUND"
    WAITING_ANY_CHANNEL = "WAITING_ANY_CHANNEL"
    WAITING_PRIMARY_CHANNEL = "WAITING_PRIMARY_CHANNEL"
    PROCESSING_REPLY = "PROCESSING_REPLY"
    RECONCILING_RESPONSES = "RECONCILING_RESPONSES"
    WAITING_OWNER = "WAITING_OWNER"
    WAITING_REFERRAL = "WAITING_REFERRAL"
    CHANGES_READY = "CHANGES_READY"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    WAITING_MUNICIPAL_APPROVAL = "WAITING_MUNICIPAL_APPROVAL"
    WAITING_IMPLANTER_APPROVAL = "WAITING_IMPLANTER_APPROVAL"
    APPLYING = "APPLYING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    BLOCKED_HUMAN = "BLOCKED_HUMAN"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"


S = CaseState

TERMINAL = {S.COMPLETED}

# Estados anteriores à aplicação: evidência nova, rejeição e revogação os afetam.
PRE_APPLY = {
    S.INTAKE, S.UNDERSTANDING_FORM, S.ANALYZING_INITIAL_REPLY, S.BUILDING_ROUND, S.ROUND_READY,
    S.SENDING_ROUND, S.WAITING_ANY_CHANNEL, S.WAITING_PRIMARY_CHANNEL, S.PROCESSING_REPLY,
    S.RECONCILING_RESPONSES, S.WAITING_OWNER, S.WAITING_REFERRAL, S.CHANGES_READY,
    S.READY_FOR_APPROVAL, S.WAITING_MUNICIPAL_APPROVAL, S.WAITING_IMPLANTER_APPROVAL,
}

# Estados em que o caso executa trabalho persistido (podem falhar de forma transitória).
WORK_STATES = {
    S.UNDERSTANDING_FORM, S.ANALYZING_INITIAL_REPLY, S.BUILDING_ROUND, S.SENDING_ROUND,
    S.PROCESSING_REPLY, S.RECONCILING_RESPONSES, S.APPLYING, S.VERIFYING,
}

ACTIVE = {s for s in CaseState if s not in TERMINAL and s != S.DRAFT}

# (origem, evento) -> destino
_T: dict[tuple[CaseState, str], CaseState] = {
    (S.DRAFT, "start"): S.INTAKE,
    (S.INTAKE, "ticket_persisted"): S.UNDERSTANDING_FORM,
    (S.UNDERSTANDING_FORM, "schema_validated"): S.ANALYZING_INITIAL_REPLY,
    (S.ANALYZING_INITIAL_REPLY, "dossier_needs_round"): S.BUILDING_ROUND,
    (S.ANALYZING_INITIAL_REPLY, "dossier_changes_ready"): S.CHANGES_READY,
    (S.ANALYZING_INITIAL_REPLY, "dossier_needs_owner"): S.WAITING_OWNER,
    (S.ANALYZING_INITIAL_REPLY, "dossier_blocked"): S.BLOCKED_HUMAN,
    (S.BUILDING_ROUND, "round_planned"): S.ROUND_READY,
    (S.ROUND_READY, "policy_allows_send"): S.SENDING_ROUND,
    (S.SENDING_ROUND, "first_round_delivered"): S.WAITING_ANY_CHANNEL,
    (S.SENDING_ROUND, "next_round_delivered"): S.WAITING_PRIMARY_CHANNEL,
    (S.WAITING_ANY_CHANNEL, "reply_correlated"): S.PROCESSING_REPLY,
    (S.WAITING_PRIMARY_CHANNEL, "reply_correlated"): S.PROCESSING_REPLY,
    (S.PROCESSING_REPLY, "evidence_validated"): S.RECONCILING_RESPONSES,
    (S.RECONCILING_RESPONSES, "reconciled_changes_ready"): S.CHANGES_READY,
    (S.RECONCILING_RESPONSES, "reconciled_new_round"): S.BUILDING_ROUND,
    (S.RECONCILING_RESPONSES, "reconciled_incomplete"): S.WAITING_PRIMARY_CHANNEL,
    (S.RECONCILING_RESPONSES, "reconciled_conflict"): S.BLOCKED_HUMAN,
    (S.WAITING_OWNER, "referral_requested"): S.WAITING_REFERRAL,
    (S.WAITING_REFERRAL, "contact_authorized"): S.BUILDING_ROUND,
    (S.CHANGES_READY, "candidate_valid"): S.READY_FOR_APPROVAL,
    (S.READY_FOR_APPROVAL, "approval_requested"): S.WAITING_MUNICIPAL_APPROVAL,
    (S.WAITING_MUNICIPAL_APPROVAL, "municipal_approved"): S.WAITING_IMPLANTER_APPROVAL,
    (S.WAITING_IMPLANTER_APPROVAL, "implanter_approved"): S.APPLYING,
    (S.APPLYING, "apply_receipt"): S.VERIFYING,
    (S.VERIFYING, "verified_and_closed"): S.COMPLETED,
    (S.FAILED_RETRYABLE, "retry_exhausted"): S.BLOCKED_HUMAN,
    (S.FAILED_PERMANENT, "correction_authorized"): S.BLOCKED_HUMAN,
    # editar candidata/testes invalida as aprovações e volta para revisão (I09)
    (S.READY_FOR_APPROVAL, "candidate_edited"): S.CHANGES_READY,
    (S.WAITING_MUNICIPAL_APPROVAL, "candidate_edited"): S.CHANGES_READY,
    (S.WAITING_IMPLANTER_APPROVAL, "candidate_edited"): S.CHANGES_READY,
    # indicação de responsável, falta de destinatário e falhas de entrega (fatias 2-3)
    (S.WAITING_ANY_CHANNEL, "referral_requested"): S.WAITING_REFERRAL,
    (S.WAITING_PRIMARY_CHANNEL, "referral_requested"): S.WAITING_REFERRAL,
    (S.RECONCILING_RESPONSES, "referral_requested"): S.WAITING_REFERRAL,
    (S.BUILDING_ROUND, "no_recipient"): S.WAITING_OWNER,
    (S.BUILDING_ROUND, "nothing_to_ask"): S.BLOCKED_HUMAN,
    (S.WAITING_REFERRAL, "referral_rejected"): S.BUILDING_ROUND,
    (S.WAITING_OWNER, "contact_authorized"): S.BUILDING_ROUND,
    (S.ROUND_READY, "round_blocked"): S.BLOCKED_HUMAN,
    (S.SENDING_ROUND, "all_channels_failed"): S.BLOCKED_HUMAN,
    (S.WAITING_ANY_CHANNEL, "round_timeout"): S.BLOCKED_HUMAN,
    (S.WAITING_PRIMARY_CHANNEL, "round_timeout"): S.BLOCKED_HUMAN,
    # evidência nova durante a aplicação, antes do commit, impede aplicar
    (S.APPLYING, "pending_evidence"): S.PROCESSING_REPLY,
    # base vigente mudou durante a aplicação (BASE_VERSION_CONFLICT) ou read-back divergente
    (S.APPLYING, "base_conflict"): S.BLOCKED_HUMAN,
    (S.VERIFYING, "readback_failed"): S.BLOCKED_HUMAN,
    (S.VERIFYING, "version_diverged"): S.BLOCKED_HUMAN,
}

for _s in PRE_APPLY:
    _T[(_s, "material_evidence")] = S.PROCESSING_REPLY
    _T[(_s, "rejected_or_revoked")] = S.BLOCKED_HUMAN
for _s in ACTIVE - {S.PAUSED, S.FAILED_PERMANENT}:
    _T[(_s, "pause")] = S.PAUSED
for _s in WORK_STATES:
    _T[(_s, "transient_failure")] = S.FAILED_RETRYABLE
for _s in ACTIVE - {S.FAILED_PERMANENT}:
    _T[(_s, "integrity_error")] = S.FAILED_PERMANENT

# Retomada (PAUSED, BLOCKED_HUMAN, FAILED_RETRYABLE) tem destino calculado pelo
# serviço após revalidar guardas; o cliente nunca escolhe o destino (v2 §9.2).
RESUMABLE = {S.PAUSED, S.BLOCKED_HUMAN, S.FAILED_RETRYABLE}


def can_resume_to(origin: CaseState, target: CaseState, resume_state: CaseState | None) -> bool:
    """Destino válido: o estado seguro registrado no checkpoint ou BLOCKED_HUMAN."""
    return origin in RESUMABLE and (target == resume_state or target == S.BLOCKED_HUMAN)


class InvalidTransition(Exception):
    code = "INVALID_TRANSITION"

    def __init__(self, state: CaseState, event: str):
        super().__init__(f"transição inválida: {state} + {event}")
        self.state, self.event = state, event


def transition(state: CaseState, event: str) -> CaseState:
    try:
        return _T[(state, event)]
    except KeyError:
        raise InvalidTransition(state, event) from None


def allowed_events(state: CaseState) -> list[str]:
    return sorted(e for (s, e) in _T if s == state)


def all_edges() -> list[tuple[CaseState, str, CaseState]]:
    return [(s, e, d) for (s, e), d in _T.items()]


# Com quem está a bola (adendo v2.1 §4.3)
def ball_owner(state: CaseState) -> str:
    if state in {S.BLOCKED_HUMAN, S.WAITING_IMPLANTER_APPROVAL, S.PAUSED, S.READY_FOR_APPROVAL, S.CHANGES_READY}:
        return "implantador"
    if state in {S.WAITING_ANY_CHANNEL, S.WAITING_PRIMARY_CHANNEL, S.WAITING_REFERRAL,
                 S.WAITING_MUNICIPAL_APPROVAL, S.WAITING_OWNER}:
        return "prefeitura"
    if state in {S.SENDING_ROUND, S.APPLYING, S.VERIFYING, S.FAILED_RETRYABLE, S.FAILED_PERMANENT}:
        return "sistema"
    if state == S.COMPLETED:
        return "nenhum"
    return "agente"
