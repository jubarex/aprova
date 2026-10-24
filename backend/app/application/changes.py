"""Testes da candidata, aprovações, aplicação recuperável, read-back e fechamento (v2 §6.3, §7)."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..clock import business_now
from ..domain.changeset import diff_schemas
from ..domain.forms import FormSchema, schema_hash, validate_input
from ..persistence.models import (
    Actor, Approval, ChangeSet, EffectReceipt, FormTestCase, FormTestRun, FormVersion, Intervention,
    ProcessDefinition, Ticket, TicketComment, ValidationCase, new_id,
)
from .cases import load_schema, store_version
from .common import (
    AppError, audit, enqueue, move_case, open_intervention, open_interventions, require_role,
)

# Injeção de falhas para testes de recuperação (T02/T03): consumida uma vez.
FAULTS: set[str] = set()


class SimulatedCrash(BaseException):
    """Simula morte do processo; não é capturada por `except Exception`."""


def maybe_crash(point: str) -> None:
    if point in FAULTS:
        FAULTS.discard(point)
        raise SimulatedCrash(point)


# ------------------------------------------------------------------ testes


def suite_hash(cases: list[FormTestCase]) -> str:
    data = sorted(
        ({"name": c.name, "kind": c.kind, "inputs": c.inputs, "expected": sorted(c.expected_codes),
          "rev": c.suite_revision} for c in cases), key=lambda d: d["name"])
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def suite_cases(s: Session, cs_id: str) -> list[FormTestCase]:
    return list(s.scalars(select(FormTestCase).where(FormTestCase.change_set_id == cs_id)
                          .order_by(FormTestCase.name)))


def coverage_gaps(s: Session, cs: ChangeSet) -> list[str]:
    """Cada regra nova/alterada exige teste positivo e negativo; sem regras, ao menos um teste."""
    base = load_schema(s.get(FormVersion, cs.base_version_id))
    cand = FormSchema.model_validate_json(cs.candidate_content)
    cases = suite_cases(s, cs.id)
    gaps: list[str] = []
    changed = [r for r in cand.rules if r not in base.rules]
    if not cases:
        gaps.append("nenhum caso de teste")
    for r in changed:
        code = f"REGRA_{r.id}" if r.effect.op == "require" else getattr(r.effect, "code", "")
        if not any(code in c.expected_codes for c in cases):
            gaps.append(f"regra {r.id}: falta exemplo negativo (que dispare {code})")
        if not any(c.kind in ("positivo", "limite") and not c.expected_codes for c in cases):
            gaps.append(f"regra {r.id}: falta exemplo positivo")
    return gaps


def run_tests(s: Session, cs: ChangeSet, *, phase: str, executor: str,
              schema: FormSchema | None = None, candidate_hash: str | None = None) -> FormTestRun:
    schema = schema or FormSchema.model_validate_json(cs.candidate_content)
    cases = suite_cases(s, cs.id)
    results = []
    for c in cases:
        actual = sorted(i.code for i in validate_input(schema, c.inputs))
        ok = actual == sorted(c.expected_codes)
        results.append({"case_id": c.id, "name": c.name, "kind": c.kind, "expected": sorted(c.expected_codes),
                        "actual": actual, "passed": ok})
    gaps = coverage_gaps(s, cs)
    run = FormTestRun(id=new_id("trun_"), change_set_id=cs.id, phase=phase,
                      candidate_hash=candidate_hash or schema_hash(schema), suite_hash=suite_hash(cases),
                      results=results, passed=bool(results) and all(r["passed"] for r in results) and not gaps,
                      executor=executor, created_at=business_now())
    run.results = results + [{"coverage_gap": g, "passed": False} for g in gaps]
    s.add(run)
    audit(s, actor=executor, action=f"tests_run_{phase}", detail={"change_set_id": cs.id, "passed": run.passed,
          "candidate_hash": run.candidate_hash[:12]}, municipality_id=cs.municipality_id)
    return run


def latest_run(s: Session, cs_id: str, phase: str) -> FormTestRun | None:
    return s.scalar(select(FormTestRun).where(FormTestRun.change_set_id == cs_id, FormTestRun.phase == phase)
                    .order_by(FormTestRun.created_at.desc(), FormTestRun.id.desc()))


def review_tests(s: Session, cs: ChangeSet, actor: Actor) -> None:
    """Uma pessoa revisa o resultado esperado; sugestão do LLM não basta (v2 §6.3)."""
    process = s.get(ProcessDefinition, cs.process_id)
    require_role(s, actor, "implanter", process)
    now = business_now()
    for c in suite_cases(s, cs.id):
        c.reviewed_by, c.reviewed_at = actor.id, now
    audit(s, actor=actor.id, action="tests_reviewed", detail={"change_set_id": cs.id},
          municipality_id=cs.municipality_id)


def edit_tests(s: Session, cs: ChangeSet, actor: Actor, cases: list[dict]) -> list[FormTestCase]:
    """Editar testes cria nova revisão da suíte e invalida as duas aprovações (I09)."""
    process = s.get(ProcessDefinition, cs.process_id)
    require_role(s, actor, "implanter", process)
    case = s.get(ValidationCase, cs.case_id)
    rev = max((c.suite_revision for c in suite_cases(s, cs.id)), default=0) + 1
    for old in suite_cases(s, cs.id):
        s.delete(old)
    s.flush()
    out = []
    for c in cases:
        t = FormTestCase(change_set_id=cs.id, name=c["name"], kind=c["kind"], inputs=c["inputs"],
                         expected_codes=sorted(c.get("expected_codes", [])), requirement=c.get("requirement", ""),
                         suite_revision=rev)
        s.add(t)
        out.append(t)
    s.flush()
    audit(s, actor=actor.id, action="tests_edited", case=case, detail={"suite_revision": rev})
    invalidate_approvals(s, cs, case, reason="Casos de teste editados", actor=actor.id)
    return out


# --------------------------------------------------------------- aprovações


def valid_approvals(s: Session, cs_id: str) -> list[Approval]:
    return list(s.scalars(select(Approval).where(Approval.change_set_id == cs_id,
                                                 Approval.decision == "approve",
                                                 Approval.invalidated_at.is_(None))
                          .order_by(Approval.created_at)))


def invalidate_approvals(s: Session, cs: ChangeSet, case: ValidationCase, *, reason: str, actor: str) -> int:
    now = business_now()
    n = 0
    for a in valid_approvals(s, cs.id):
        a.invalidated_at, a.invalidated_reason = now, reason
        n += 1
    if n:
        audit(s, actor=actor, action="approvals_invalidated", case=case, why=reason, detail={"count": n})
    if cs.status in ("approved_municipal", "approved", "ready"):
        cs.status = "draft"
    if CaseState_in(case, ("READY_FOR_APPROVAL", "WAITING_MUNICIPAL_APPROVAL", "WAITING_IMPLANTER_APPROVAL")):
        move_case(s, case, "candidate_edited", actor=actor, why=reason)
        case.next_action = "Revisar os testes e pedir aprovação novamente"
    return n


def CaseState_in(case: ValidationCase, states: tuple[str, ...]) -> bool:
    return case.state in states


def _guards_before_approval(s: Session, cs: ChangeSet, case: ValidationCase) -> FormTestRun:
    if open_interventions(s, case.id):
        raise AppError("INTERVENTION_OPEN", "há intervenção aberta; resolva antes de aprovar", 409)
    from .messaging import pending_evidence
    if pending_evidence(s, case.id):
        raise AppError("EVIDENCE_PENDING", "há evidência ainda não processada; aguarde a consolidação", 409)
    run = latest_run(s, cs.id, "pre_approval")
    cases = suite_cases(s, cs.id)
    if run is None or not run.passed:
        raise AppError("TESTS_NOT_PASSED", "os testes da candidata ainda não passaram", 409)
    if run.candidate_hash != cs.candidate_hash or run.suite_hash != suite_hash(cases):
        raise AppError("TESTS_STALE", "a candidata ou a suíte mudou depois da última execução", 409)
    if not cases or any(c.reviewed_by is None for c in cases):
        raise AppError("TESTS_NOT_REVIEWED", "uma pessoa precisa revisar os resultados esperados", 409)
    return run


def submit_for_approval(s: Session, cs: ChangeSet, actor: Actor, expected_version: int) -> None:
    case = s.get(ValidationCase, cs.case_id)
    process = s.get(ProcessDefinition, cs.process_id)
    require_role(s, actor, "implanter", process)
    if case.state != "CHANGES_READY":
        raise AppError("INVALID_TRANSITION", f"estado atual não permite o pedido: {case.state}", 409)
    if case.version != expected_version:
        raise AppError("VERSION_CONFLICT", "o caso mudou; recarregue", 409)
    run = run_tests(s, cs, phase="pre_approval", executor=actor.id)
    s.flush()
    _guards_before_approval(s, cs, case)
    cs.status = "ready"
    move_case(s, case, "candidate_valid", actor=actor.id, why="Candidata, diff e testes válidos",
              expected_version=expected_version)
    move_case(s, case, "approval_requested", actor=actor.id, why="Pedido de aprovação municipal registrado")
    case.next_action = "Aguardar a aprovação da prefeitura"
    audit(s, actor=actor.id, action="approval_requested", case=case, detail={"candidate_hash": cs.candidate_hash,
          "test_run_id": run.id})


def _record(s: Session, cs: ChangeSet, case: ValidationCase, actor: Actor, role: str, decision: str,
            rationale: str, channel: str, run: FormTestRun) -> Approval:
    a = Approval(case_id=case.id, cycle_number=case.cycle_number, change_set_id=cs.id,
                 base_form_version_id=cs.base_version_id, candidate_hash=cs.candidate_hash,
                 test_suite_hash=run.suite_hash, test_run_id=run.id, actor_id=actor.id, approver_role=role,
                 decision=decision, rationale=rationale, channel=channel, created_at=business_now())
    s.add(a)
    return a


def decide_municipal(s: Session, cs: ChangeSet, actor: Actor, *, decision: str, expected_version: int,
                     rationale: str = "", channel: str = "command") -> Approval:
    case = s.get(ValidationCase, cs.case_id)
    process = s.get(ProcessDefinition, cs.process_id)
    if actor.municipality_id != cs.municipality_id:
        raise AppError("NOT_FOUND", "recurso fora do escopo", 404)
    require_role(s, actor, "municipal_approver", process)
    if case.state != "WAITING_MUNICIPAL_APPROVAL":
        raise AppError("INVALID_TRANSITION", f"a aprovação municipal não está aberta ({case.state})", 409)
    if case.version != expected_version:
        raise AppError("VERSION_CONFLICT", "o caso mudou; recarregue e decida novamente", 409)
    run = _guards_before_approval(s, cs, case)
    if decision == "reject":
        if not rationale.strip():
            raise AppError("RATIONALE_REQUIRED", "informe o motivo do pedido de ajuste", 422)
        a = _record(s, cs, case, actor, "municipal", "reject", rationale, channel, run)
        cs.status = "rejected"
        open_intervention(s, case, code="REJEITADA_MUNICIPIO", urgency=1,
                          reason=f"A prefeitura pediu ajuste: {rationale}",
                          needed="Corrigir a candidata ou esclarecer com a prefeitura")
        move_case(s, case, "rejected_or_revoked", actor=actor.id, why=rationale, expected_version=expected_version)
        return a
    a = _record(s, cs, case, actor, "municipal", "approve", rationale, channel, run)
    cs.status = "approved_municipal"
    move_case(s, case, "municipal_approved", actor=actor.id, why="Aprovação municipal da candidata exata",
              expected_version=expected_version, detail={"candidate_hash": cs.candidate_hash[:12], "channel": channel})
    case.next_action = "Aprovar pela Aprova"
    return a


def decide_implanter(s: Session, cs: ChangeSet, actor: Actor, *, decision: str, expected_version: int,
                     rationale: str = "") -> Approval:
    case = s.get(ValidationCase, cs.case_id)
    process = s.get(ProcessDefinition, cs.process_id)
    require_role(s, actor, "aprova_approver", process)
    if case.state != "WAITING_IMPLANTER_APPROVAL":
        raise AppError("INVALID_TRANSITION", f"a aprovação da Aprova não está aberta ({case.state})", 409)
    if case.version != expected_version:
        raise AppError("VERSION_CONFLICT", "o caso mudou; recarregue e decida novamente", 409)
    run = _guards_before_approval(s, cs, case)
    muni = [a for a in valid_approvals(s, cs.id) if a.approver_role == "municipal"]
    if not muni or muni[-1].candidate_hash != cs.candidate_hash or muni[-1].test_suite_hash != run.suite_hash:
        raise AppError("MUNICIPAL_APPROVAL_INVALID", "a aprovação municipal não vale para esta candidata", 409)
    if muni[-1].actor_id == actor.id:
        raise AppError("DISTINCT_APPROVERS_REQUIRED", "as duas aprovações exigem pessoas distintas", 403)
    if decision == "reject":
        if not rationale.strip():
            raise AppError("RATIONALE_REQUIRED", "informe o motivo da rejeição", 422)
        a = _record(s, cs, case, actor, "aprova", "reject", rationale, "command", run)
        cs.status = "rejected"
        open_intervention(s, case, code="REJEITADA_APROVA", urgency=1, reason=f"Rejeitada pela Aprova: {rationale}",
                          needed="Corrigir a candidata")
        move_case(s, case, "rejected_or_revoked", actor=actor.id, why=rationale, expected_version=expected_version)
        return a
    a = _record(s, cs, case, actor, "aprova", "approve", rationale, "command", run)
    cs.status = "approved"
    move_case(s, case, "implanter_approved", actor=actor.id, why="Aprovação da Aprova da mesma candidata",
              expected_version=expected_version)
    case.next_action = "Aplicando a versão aprovada"
    enqueue(s, "apply_change_set", case.id, {"change_set_id": cs.id}, dedupe_key=f"apply:{cs.id}:{case.version}")
    return a


def revoke(s: Session, cs: ChangeSet, actor: Actor, *, expected_version: int, rationale: str) -> None:
    case = s.get(ValidationCase, cs.case_id)
    process = s.get(ProcessDefinition, cs.process_id)
    if not (actor.kind == "aprova" or actor.municipality_id == cs.municipality_id):
        raise AppError("NOT_FOUND", "recurso fora do escopo", 404)
    if case.state in ("APPLYING", "VERIFYING", "COMPLETED"):
        raise AppError("TOO_LATE", "após a aplicação, a correção exige nova candidata aprovada", 409)
    if case.state not in ("WAITING_MUNICIPAL_APPROVAL", "WAITING_IMPLANTER_APPROVAL"):
        raise AppError("INVALID_TRANSITION", "não há aprovação a revogar neste estado", 409)
    require_role(s, actor, "municipal_approver" if actor.kind != "aprova" else "aprova_approver", process)
    invalidate_approvals(s, cs, case, reason=f"Revogada: {rationale}", actor=actor.id)
    open_intervention(s, case, code="REVOGADA", reason=f"Aprovação revogada: {rationale}", urgency=1)


# ----------------------------------------------------- aplicação (worker)


class BaseVersionConflict(Exception):
    code = "BASE_VERSION_CONFLICT"


def _receipt(s: Session, key: str) -> EffectReceipt | None:
    return s.scalar(select(EffectReceipt).where(EffectReceipt.idempotency_key == key))


def _approvals_match(s: Session, cs: ChangeSet) -> bool:
    ap = valid_approvals(s, cs.id)
    roles = {a.approver_role: a for a in ap}
    return ("municipal" in roles and "aprova" in roles
            and roles["municipal"].actor_id != roles["aprova"].actor_id
            and all(a.candidate_hash == cs.candidate_hash for a in ap))


def apply_change_set(s: Session, cs_id: str) -> str:
    """Efeito idempotente: CAS no ponteiro vigente + recibo único na mesma transação (T03/T05)."""
    cs = s.get(ChangeSet, cs_id)
    case = s.get(ValidationCase, cs.case_id)
    key = f"apply:{cs.id}"
    rc = _receipt(s, key)
    if rc:  # retry depois de queda: recupera o recibo, não reaplica
        if case.state == "APPLYING":
            move_case(s, case, "apply_receipt", actor="sistema", why="Recibo de aplicação recuperado")
            enqueue(s, "verify_change_set", case.id, {"change_set_id": cs.id}, dedupe_key=f"verify:{cs.id}")
        return rc.detail["version_id"]
    if case.state != "APPLYING":
        return ""  # evidência nova superou esta aplicação (ou o caso mudou): nada a fazer
    from .messaging import pending_evidence
    if pending_evidence(s, case.id):
        move_case(s, case, "pending_evidence", actor="sistema", why="Evidência pendente impede aplicar")
        from .messaging import schedule_consolidation
        from datetime import timedelta
        schedule_consolidation(s, case, timedelta(0))
        return ""
    if open_interventions(s, case.id) or not _approvals_match(s, cs):
        raise AppError("GUARD_FAILED", "guardas de aplicação não satisfeitas", 409)
    process = s.get(ProcessDefinition, cs.process_id)
    candidate = FormSchema.model_validate_json(cs.candidate_content)
    if schema_hash(candidate) != cs.candidate_hash:
        raise AppError("HASH_MISMATCH", "a candidata não corresponde ao hash aprovado", 409)
    new = store_version(s, process, candidate, cs.base_version_id)
    res = s.execute(update(ProcessDefinition)
                    .where(ProcessDefinition.id == process.id, ProcessDefinition.current_version_id == cs.base_version_id)
                    .values(current_version_id=new.id))
    if res.rowcount != 1:
        raise BaseVersionConflict(f"vigente mudou: esperado {cs.base_version_id}")
    cs.applied_version_id, cs.status = new.id, "applied"
    s.add(EffectReceipt(idempotency_key=key, kind="apply", case_id=case.id,
                        detail={"version_id": new.id, "sha256": new.sha256, "change_set_id": cs.id}))
    move_case(s, case, "apply_receipt", actor="sistema", why="Versão aprovada aplicada ao motor",
              detail={"version": new.version, "sha": new.sha256[:12]})
    case.next_action = "Verificando a persistência"
    enqueue(s, "verify_change_set", case.id, {"change_set_id": cs.id}, dedupe_key=f"verify:{cs.id}")
    return new.id


def handle_base_conflict(s: Session, cs_id: str) -> None:
    cs = s.get(ChangeSet, cs_id)
    case = s.get(ValidationCase, cs.case_id)
    invalidate_approvals(s, cs, case, reason="BASE_VERSION_CONFLICT", actor="sistema")
    cs.status = "superseded"
    open_intervention(s, case, code="BASE_VERSION_CONFLICT", urgency=1,
                      reason="Outra alteração mudou o formulário vigente; a versão vigente foi preservada.",
                      needed="Replanejar a candidata sobre a nova base e obter novas aprovações")
    if case.state == "APPLYING":
        move_case(s, case, "base_conflict", actor="sistema", why="Base vigente divergente")


def verify_change_set(s: Session, cs_id: str) -> bool:
    """Read-back do armazenamento do motor, sem reutilizar a candidata em memória."""
    cs = s.get(ChangeSet, cs_id)
    case = s.get(ValidationCase, cs.case_id)
    key = f"verify:{cs.id}"
    if _receipt(s, key):
        return True
    if case.state != "VERIFYING":
        raise AppError("INVALID_TRANSITION", f"estado inesperado para verificar: {case.state}", 409)
    s.expire_all()
    process = s.get(ProcessDefinition, cs.process_id)
    stored = s.get(FormVersion, cs.applied_version_id)
    schema = load_schema(stored)
    ok = (process.current_version_id == cs.applied_version_id and schema_hash(schema) == cs.candidate_hash
          and stored.sha256 == cs.candidate_hash)
    run = run_tests(s, cs, phase="post_readback", executor="sistema", schema=schema, candidate_hash=schema_hash(schema))
    if not (ok and run.passed):
        open_intervention(s, case, code="READBACK_DIVERGENTE", urgency=1,
                          reason="A leitura do motor não coincide com a versão aprovada ou os testes falharam.",
                          needed="Investigar e preparar uma nova candidata aprovada")
        move_case(s, case, "readback_failed", actor="sistema", why="Read-back divergente")
        return False
    s.add(EffectReceipt(idempotency_key=key, kind="verify", case_id=case.id,
                        detail={"sha256": stored.sha256, "test_run_id": run.id}))
    cs.status = "verified"
    audit(s, actor="sistema", action="readback_verified", case=case, why="Hash e testes conferem após leitura do motor")
    enqueue(s, "close_ticket", case.id, {"change_set_id": cs.id}, dedupe_key=f"close:{cs.id}")
    return True


def close_ticket(s: Session, cs_id: str) -> None:
    """Nota interna e fechamento como efeitos ordenados e idempotentes; revalida tudo ao fechar."""
    cs = s.get(ChangeSet, cs_id)
    case = s.get(ValidationCase, cs.case_id)
    ticket = s.get(Ticket, case.ticket_id)
    if _receipt(s, f"close:{cs.id}"):
        return
    if case.state != "VERIFYING":
        raise AppError("INVALID_TRANSITION", f"estado inesperado para fechar: {case.state}", 409)
    note_key = f"note:{cs.id}"
    if not _receipt(s, note_key):
        s.add(TicketComment(ticket_id=ticket.id, visibility="internal", author="Aprova Command",
                            external_key=note_key,
                            body=f"Versão {schema_hash(FormSchema.model_validate_json(cs.candidate_content))[:8]} "
                                 f"aplicada e verificada. Ciclo {case.cycle_number}."))
        s.add(EffectReceipt(idempotency_key=note_key, kind="note", case_id=case.id, detail={"ticket_id": ticket.id}))
        s.flush()
        maybe_crash("after_note")
    process = s.get(ProcessDefinition, case.process_id)
    from .messaging import pending_evidence
    if pending_evidence(s, case.id):
        open_intervention(s, case, code="EVIDENCIA_APOS_APLICACAO", urgency=1,
                          reason="Chegou evidência depois da aplicação; o fechamento foi bloqueado até a análise.",
                          needed="Avaliar se a nova informação exige correção (nova candidata aprovada)")
        move_case(s, case, "version_diverged", actor="sistema", why="Evidência posterior à aplicação")
        return
    if process.current_version_id != cs.applied_version_id or not _receipt(s, f"verify:{cs.id}") \
            or not _approvals_match(s, cs) or open_interventions(s, case.id):
        open_intervention(s, case, code="VERSAO_DIVERGENTE", urgency=1,
                          reason="A versão vigente difere da aprovada e verificada; o fechamento foi bloqueado.",
                          needed="Revalidar a versão vigente antes de fechar")
        move_case(s, case, "version_diverged", actor="sistema", why="Fechamento bloqueado")
        return
    ticket.status = "closed"
    s.add(EffectReceipt(idempotency_key=f"close:{cs.id}", kind="close", case_id=case.id,
                        detail={"ticket_id": ticket.id}))
    case.active = False
    move_case(s, case, "verified_and_closed", actor="sistema", why="Verificação, nota e fechamento confirmados")
    case.next_action = "Concluído"
    case.blocked_reason = None


def build_diff(s: Session, cs: ChangeSet) -> list[dict]:
    base = load_schema(s.get(FormVersion, cs.base_version_id))
    return diff_schemas(base, FormSchema.model_validate_json(cs.candidate_content))
