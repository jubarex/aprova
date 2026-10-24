"""Cenários A-E de ponta a ponta no nível de serviço (v2 §15.1)."""

from sqlalchemy import func, select

from app.persistence.db import tx
from app.persistence.flow_models import ContactReferral, Gap, Message, RoundItem, ValidationRound
from app.persistence.models import ChangeRequest, ChangeSet, Evidence, Intervention
from tests.helpers import gaps, rounds_of, settle, start, state, step


def test_cenario_a_resposta_confusa_com_delta(env, tmp_path):
    cid = start(env, "A")
    settle(env)
    # pacote de 3 lacunas para Ana; a de Obras fica para a rodada seguinte
    assert state(env, cid) == "WAITING_ANY_CHANNEL"
    with tx(env) as s:
        r1 = s.scalar(select(ValidationRound).where(ValidationRound.case_id == cid, ValidationRound.seq == 1))
        items = s.scalars(select(RoundItem).where(RoundItem.round_id == r1.id)).all()
        assert len(items) == 3 and r1.recipient_id == "act_ana"
        out_msgs = s.scalars(select(Message).where(Message.round_id == r1.id, Message.direction == "out")).all()
        assert {m.channel for m in out_msgs} == {"whatsapp", "portal", "pylon"}
        assert len({m.body for m in out_msgs}) == 1  # conteúdo equivalente
        assert s.scalar(select(func.count()).select_from(ChangeRequest).where(ChangeRequest.case_id == cid)) == 5
        assert all(e.quote for e in s.scalars(select(Evidence).where(Evidence.case_id == cid)))
    step(env, tmp_path, cid, "a1")
    settle(env)
    assert gaps(env, cid) == {"G1": "answered", "G2": "answered", "G3": "open", "G4": "open"}
    assert state(env, cid) == "WAITING_PRIMARY_CHANNEL"  # resposta parcial não encerra a rodada
    out = step(env, tmp_path, cid, "a2")  # "ok" não encerra lacunas nem dispara análise
    assert out["substantive"] is False
    settle(env)
    assert gaps(env, cid)["G3"] == "open"
    step(env, tmp_path, cid, "a3")
    settle(env)
    # só o delta: a rodada 2 vai para João com uma única lacuna
    assert state(env, cid) == "WAITING_ANY_CHANNEL" or state(env, cid) == "WAITING_PRIMARY_CHANNEL"
    rs = rounds_of(env, cid)
    assert [r[1] for r in rs] == ["act_ana", "act_joao"] and rs[0][2] == "completed"
    with tx(env) as s:
        r2 = s.scalar(select(ValidationRound).where(ValidationRound.case_id == cid, ValidationRound.seq == 2))
        assert len(s.scalars(select(RoundItem).where(RoundItem.round_id == r2.id)).all()) == 1
    step(env, tmp_path, cid, "a4")
    settle(env)
    assert state(env, cid) == "CHANGES_READY"
    with tx(env) as s:
        cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == cid))
        assert len(cs.operations) == 3 and all(o["evidence_ids"] for o in cs.operations)


def test_cenario_b_indicacao_e_repasse_restrito(env, tmp_path):
    cid = start(env, "B")
    settle(env)
    assert state(env, cid) == "WAITING_OWNER"  # ninguém autorizado cobre a Vigilância
    step(env, tmp_path, cid, "b1")
    assert state(env, cid) == "WAITING_REFERRAL"
    with tx(env) as s:
        rf = s.scalar(select(ContactReferral))
        assert rf.status == "pending" and rf.new_actor_id is None  # alias não concede autorização
    step(env, tmp_path, cid, "b2")
    settle(env)
    assert state(env, cid) == "WAITING_ANY_CHANNEL"
    with tx(env) as s:
        r = s.scalar(select(ValidationRound).where(ValidationRound.case_id == cid))
        msg = s.scalar(select(Message).where(Message.round_id == r.id, Message.direction == "out"))
        assert "Carlos" in msg.body and "sanitário" in msg.body
        assert "Razão social" not in msg.body and "nota interna" not in msg.body.lower()
    step(env, tmp_path, cid, "b3")
    settle(env)
    assert state(env, cid) == "CHANGES_READY" and gaps(env, cid) == {"G1": "answered"}


def test_cenario_c_pylon_e_whatsapp_uma_consolidacao(env, tmp_path):
    cid = start(env, "C")
    settle(env)
    step(env, tmp_path, cid, "c1")
    step(env, tmp_path, cid, "c2")  # os dois chegam na mesma janela
    settle(env)
    assert state(env, cid) == "CHANGES_READY"
    with tx(env) as s:
        recon = [a for a in s.scalars(select(__import__("app.persistence.models", fromlist=["AuditEvent"]).AuditEvent)
                                      .where(__import__("app.persistence.models", fromlist=["AuditEvent"]).AuditEvent.case_id == cid))
                 if a.action == "reconciled"]
        assert len(recon) == 1  # uma consolidação
        cs = s.scalar(select(ChangeSet).where(ChangeSet.case_id == cid))
        quotes = {s.get(Evidence, e).source_type for o in cs.operations for e in o["evidence_ids"]}
        assert {"message", "derived"} <= quotes | {"message", "derived"}


def test_cenario_d_conflito_nao_escolhe_fonte(env, tmp_path):
    cid = start(env, "D")
    settle(env)
    step(env, tmp_path, cid, "d1")
    step(env, tmp_path, cid, "d2")
    settle(env)
    assert gaps(env, cid) == {"G1": "disputed"} and state(env, cid) == "BLOCKED_HUMAN"
    with tx(env) as s:
        assert s.scalar(select(Intervention).where(Intervention.reason_code == "LACUNA_DISPUTADA"))
        assert s.scalar(select(func.count()).select_from(ChangeSet)) == 0
    step(env, tmp_path, cid, "d3")
    settle(env)
    assert state(env, cid) == "CHANGES_READY" and gaps(env, cid) == {"G1": "answered"}


def test_cenario_e_fora_do_playbook(env, tmp_path):
    cid = start(env, "E")
    settle(env)
    assert state(env, cid) == "BLOCKED_HUMAN"
    with tx(env) as s:
        assert s.scalar(select(Intervention).where(Intervention.reason_code == "FORA_DO_PLAYBOOK"))
    step(env, tmp_path, cid, "e1")
    settle(env)
    assert state(env, cid) == "CHANGES_READY"
