"""Cenário G e regressões T01-T06, T14, T15 (v2 §15)."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app.agent import fixtures
from app.application import cases, changes
from app.application.common import AppError, get_actor
from app.clock import real_now
from app.domain.forms import FormSchema
from app.persistence.db import tx
from app.persistence.models import (
    Approval, ChangeSet, EffectReceipt, FormVersion, Intervention, ProcessDefinition, Ticket, ValidationCase,
    WorkItem,
)
from app.worker import runner

PID = "proc_vr_iss012"


def open_case(factory, reply=fixtures.SCENARIO_G_REPLY):
    with tx(factory) as s:
        t = cases.create_ticket(s, process_id=PID, title="Ajustes no alvará", description="",
                                initial_reply=reply, actor="act_rui")
        c = cases.start_case(s, t.id, "act_rui")
        return t.id, c.id


def state(factory, case_id):
    with tx(factory) as s:
        c = s.get(ValidationCase, case_id)
        return c.state, c.version


def cs_of(factory, case_id):
    with tx(factory) as s:
        return s.scalar(select(ChangeSet).where(ChangeSet.case_id == case_id)).id


def prepare(factory):
    """Ticket -> candidata pronta -> aprovação municipal pedida."""
    tid, cid = open_case(factory)
    runner.drain(factory)
    assert state(factory, cid)[0] == "CHANGES_READY"
    csid = cs_of(factory, cid)
    with tx(factory) as s:
        changes.review_tests(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"))
    with tx(factory) as s:
        v = s.get(ValidationCase, cid).version
        changes.submit_for_approval(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), v)
    assert state(factory, cid)[0] == "WAITING_MUNICIPAL_APPROVAL"
    return tid, cid, csid


def municipal_approve(factory, csid, cid, actor="act_ana"):
    with tx(factory) as s:
        v = s.get(ValidationCase, cid).version
        changes.decide_municipal(s, s.get(ChangeSet, csid), get_actor(s, actor), decision="approve",
                                 expected_version=v, channel="portal")


def implanter_approve(factory, csid, cid, actor="act_rui"):
    with tx(factory) as s:
        v = s.get(ValidationCase, cid).version
        changes.decide_implanter(s, s.get(ChangeSet, csid), get_actor(s, actor), decision="approve",
                                 expected_version=v)


def test_cenario_g_ciclo_completo(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    assert state(env, cid)[0] == "WAITING_IMPLANTER_APPROVAL"
    implanter_approve(env, csid, cid)
    runner.drain(env)
    with tx(env) as s:
        c = s.get(ValidationCase, cid)
        assert c.state == "COMPLETED" and not c.active
        assert s.get(Ticket, tid).status == "closed"
        cs = s.get(ChangeSet, csid)
        p = s.get(ProcessDefinition, PID)
        assert p.current_version_id == cs.applied_version_id
        v = s.get(FormVersion, p.current_version_id)
        assert v.sha256 == cs.candidate_hash and v.version == 2
        kinds = {r.kind for r in s.scalars(select(EffectReceipt).where(EffectReceipt.case_id == cid))}
        assert kinds == {"apply", "verify", "note", "close"}
        schema = FormSchema.model_validate_json(v.content)
        assert schema.field("ramo").label == "Ramo de atividade"


def test_bypass_de_papel_e_aprovacao(env):
    tid, cid, csid = prepare(env)
    with tx(env) as s:
        v = s.get(ValidationCase, cid).version
    with pytest.raises(AppError) as e:  # João responde, mas não aprova
        with tx(env) as s:
            changes.decide_municipal(s, s.get(ChangeSet, csid), get_actor(s, "act_joao"), decision="approve",
                                     expected_version=v)
    assert e.value.status == 403
    with pytest.raises(AppError) as e:  # Marcos é de outro município
        with tx(env) as s:
            changes.decide_municipal(s, s.get(ChangeSet, csid), get_actor(s, "act_marcos"), decision="approve",
                                     expected_version=v)
    assert e.value.status == 404
    with pytest.raises(AppError) as e:  # aprovação da Aprova antes da municipal
        implanter_approve(env, csid, cid)
    assert e.value.code == "INVALID_TRANSITION"


def test_t01_dois_comandos_mesma_revisao(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    with tx(env) as s:
        v = s.get(ValidationCase, cid).version
    # dois comandos com a mesma revisão: o primeiro vence, o segundo recebe conflito
    with tx(env) as s:
        changes.decide_implanter(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), decision="approve",
                                 expected_version=v)
    with pytest.raises(AppError) as e:
        with tx(env) as s:
            changes.decide_implanter(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), decision="approve",
                                     expected_version=v)
    assert e.value.code in ("VERSION_CONFLICT", "INVALID_TRANSITION")
    with tx(env) as s:
        assert s.scalar(select(func.count()).select_from(Approval).where(Approval.approver_role == "aprova")) == 1


def test_t03_queda_apos_aplicar_antes_do_ack(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    implanter_approve(env, csid, cid)
    changes.FAULTS.add("after_apply_commit")
    with pytest.raises(changes.SimulatedCrash):
        runner.drain(env)
    # reinício: o lease vence e o trabalho é retomado
    with tx(env) as s:
        s.execute(update(WorkItem).where(WorkItem.status == "running")
                  .values(lease_expires_at=real_now() - timedelta(seconds=1)))
    runner.drain(env)
    with tx(env) as s:
        assert s.get(ValidationCase, cid).state == "COMPLETED"
        assert s.scalar(select(func.count()).select_from(EffectReceipt).where(
            EffectReceipt.idempotency_key == f"apply:{csid}")) == 1
        assert s.scalar(select(func.count()).select_from(FormVersion).where(FormVersion.process_id == PID)) == 2


def test_t14_lease_antigo_nao_confirma(env):
    tid, cid = open_case(env)
    job_id, token = runner.claim(env)
    with pytest.raises(runner.LeaseLost):
        runner.finish(env, job_id, "token-antigo")
    runner.finish(env, job_id, token)


def test_t04_edicao_de_teste_invalida_as_duas_aprovacoes(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    with tx(env) as s:
        changes.edit_tests(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), [
            {"name": "novo", "kind": "positivo", "inputs": {"ramo": "outro", "razao_social": "x"},
             "expected_codes": []}])
    with tx(env) as s:
        assert s.get(ValidationCase, cid).state == "CHANGES_READY"
        assert not changes.valid_approvals(s, csid)
    with pytest.raises(AppError):  # sem aprovação válida nem testes revisados não há como aplicar
        implanter_approve(env, csid, cid)


def test_t05_base_vigente_mudou(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    # outro ticket aplica uma versão antes da nossa
    with tx(env) as s:
        p = s.get(ProcessDefinition, PID)
        other = cases.store_version(s, p, fixtures.base_schema().model_copy(deep=True), p.current_version_id)
        p.current_version_id = other.id
        other_id = other.id
    implanter_approve(env, csid, cid)
    runner.drain(env)
    with tx(env) as s:
        assert s.get(ProcessDefinition, PID).current_version_id == other_id  # vigente preservado
        c = s.get(ValidationCase, cid)
        assert c.state == "BLOCKED_HUMAN"
        assert not changes.valid_approvals(s, csid)
        assert s.scalar(select(Intervention).where(Intervention.reason_code == "BASE_VERSION_CONFLICT"))


def test_t06_teste_falhando_impede_aprovacao(env):
    tid, cid = open_case(env)
    runner.drain(env)
    csid = cs_of(env, cid)
    with tx(env) as s:
        changes.edit_tests(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), [
            {"name": "errado", "kind": "negativo", "inputs": {"ramo": "outro", "razao_social": "x"},
             "expected_codes": ["REGRA_inexistente"]}])
        changes.review_tests(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"))
    with pytest.raises(AppError) as e:
        with tx(env) as s:
            v = s.get(ValidationCase, cid).version
            changes.submit_for_approval(s, s.get(ChangeSet, csid), get_actor(s, "act_rui"), v)
    assert e.value.code == "TESTS_NOT_PASSED"


def test_t15_vigente_divergente_bloqueia_fechamento(env):
    tid, cid, csid = prepare(env)
    municipal_approve(env, csid, cid)
    implanter_approve(env, csid, cid)
    # roda apply e verify, mas não o fechamento
    while True:
        with tx(env) as s:
            pending = s.scalar(select(WorkItem).where(WorkItem.status == "pending"))
            if pending is None or pending.kind == "close_ticket":
                break
        runner.run_one(env)
    with tx(env) as s:  # outro ticket muda o vigente depois do read-back
        p = s.get(ProcessDefinition, PID)
        other = cases.store_version(s, p, fixtures.base_schema(), p.current_version_id)
        p.current_version_id = other.id
    runner.drain(env)
    with tx(env) as s:
        assert s.get(ValidationCase, cid).state == "BLOCKED_HUMAN"
        assert s.get(Ticket, tid).status == "open"


def test_replay_miss_nao_inventa_analise(env):
    tid, cid = open_case(env, reply="Texto desconhecido sem gravação.")
    runner.drain(env)
    with tx(env) as s:
        c = s.get(ValidationCase, cid)
        assert c.state == "BLOCKED_HUMAN"
        assert s.scalar(select(Intervention).where(Intervention.reason_code == "REPLAY_MISS"))
        assert s.scalar(select(func.count()).select_from(ChangeSet)) == 0


def test_um_ciclo_ativo_por_ticket(env):
    tid, cid = open_case(env)
    with pytest.raises(AppError) as e:
        with tx(env) as s:
            cases.start_case(s, tid, "act_rui")
    assert e.value.code == "CASE_ALREADY_ACTIVE"
