import pytest
from fastapi.testclient import TestClient

from app import clock
from app.agent import replay
from app.api.main import create_app
from app.application import changes, rounds
from app.config import Settings
from app.worker import runner
from tests.helpers import settle


@pytest.fixture()
def api(tmp_path):
    from datetime import timedelta
    replay.clear()
    changes.FAULTS.clear()
    clock.set_offset(timedelta(0))
    rounds.SETTINGS["first_message_review"] = True
    st = Settings("demo", "offline_replay", f"sqlite:///{(tmp_path / 'api.db').as_posix()}", tmp_path / "att")
    app = create_app(st, start_worker=False)
    with TestClient(app) as c:
        c.factory = app.state.factory
        yield c


def login(api, actor_id):
    r = api.post("/api/demo/session", json={"actor_id": actor_id})
    return {"X-Demo-Token": r.json()["token"]}


def idem(h, k):
    return {**h, "Idempotency-Key": k}


def start(api, rui, sid):
    r = api.post(f"/api/demo/scenarios/{sid}/start", headers=rui)
    assert r.status_code == 200, r.text
    return r.json()["case_id"]


def test_portal_responde_pendencia_e_cria_delta(api):
    rui, ana = login(api, "act_rui"), login(api, "act_ana")
    cid = start(api, rui, "A")
    runner.drain(api.factory)
    # primeira mensagem a este destinatário aguarda revisão humana
    case = api.get(f"/api/cases/{cid}", headers=rui).json()
    assert case["state"] == "ROUND_READY"
    today = api.get("/api/today", headers=rui).json()
    assert any(t["kind"] == "review_first_message" for t in today["tasks"])
    rnd = api.get(f"/api/cases/{cid}/rounds", headers=rui).json()[0]
    assert rnd["awaiting_review"] and "Para seguir, precisamos de 3" in rnd["preview"]
    r = api.post(f"/api/rounds/{rnd['id']}/release", json={}, headers=idem(rui, "rel1"))
    assert r.status_code == 200
    settle(api.factory)

    # Portal: Ana vê "Seu próximo passo" com a pergunta e o motivo
    home = api.get("/api/portal/me", headers=ana).json()
    assert home["next_step"]["kind"] == "question" and home["next_step"]["why"]
    items = api.get("/api/portal/pending", headers=ana).json()
    assert len(items) == 3 and items[0]["demo_hint"]
    # João (outro assunto) não vê as perguntas de Ana
    joao = login(api, "act_joao")
    assert api.get("/api/portal/pending", headers=joao).json() == []
    assert api.get(f"/api/portal/items/{items[0]['id']}", headers=joao).status_code == 404

    hint = items[0]["demo_hint"]
    r = api.post(f"/api/portal/items/{items[0]['id']}/answer", data={"text": hint}, headers=idem(ana, "ans1"))
    assert r.status_code == 200 and r.json()["received"]
    again = api.post(f"/api/portal/items/{items[0]['id']}/answer", data={"text": hint}, headers=idem(ana, "ans1"))
    assert again.json() == r.json()  # retry legítimo devolve o resultado original
    settle(api.factory)
    gaps = {g["ref"]: g["status"] for g in api.get(f"/api/cases/{cid}/gaps", headers=rui).json()}
    assert gaps["G1"] == "answered" and gaps["G3"] == "open"
    # espelho no Pylon e histórico no Portal
    convo = api.get(f"/api/cases/{cid}/conversations", headers=rui).json()
    assert any(m["mirror"] and m["channel"] == "pylon" for m in convo["messages"])
    hist = api.get("/api/portal/history", headers=ana).json()
    assert hist and hist[0]["channel"] == "portal"


def test_link_magico_e_isolamento(api):
    rui = login(api, "act_rui")
    link = api.post("/api/demo/portal-links", json={"actor_id": "act_ana"}, headers=rui).json()
    token = link["url"].split("t=")[1]
    sess = api.post("/api/portal/session", json={"token": token})
    assert sess.status_code == 200
    me = api.get("/api/portal/me", headers={"X-Demo-Token": sess.json()["token"]})
    assert me.status_code == 200 and me.json()["municipality"]["short"] == "VR"
    assert api.post("/api/portal/session", json={"token": "invalido"}).status_code == 401


def test_cenario_b_pela_api(api, tmp_path):
    rui, ana = login(api, "act_rui"), login(api, "act_ana")
    cid = start(api, rui, "B")
    runner.drain(api.factory)
    assert api.get(f"/api/cases/{cid}", headers=rui).json()["state"] == "WAITING_OWNER"
    today = api.get("/api/today", headers=rui).json()
    assert any(t["kind"] == "define_owner" for t in today["tasks"])
    r = api.post(f"/api/cases/{cid}/referrals", json={"name": "Carlos Menezes", "topic": "vigilancia"},
                 headers=idem(ana, "rf1"))
    assert r.status_code == 200
    today = api.get("/api/today", headers=rui).json()
    t = next(x for x in today["tasks"] if x["kind"] == "authorize_referral")
    assert "Carlos Menezes" in t["title"] and "Ana" in t["title"]
    # contato não autoriza ninguém
    assert api.post(f"/api/referrals/{r.json()['referral_id']}/authorize", json={}, headers=idem(ana, "x")).status_code == 403
    ok = api.post(f"/api/referrals/{r.json()['referral_id']}/authorize", json={}, headers=idem(rui, "rf2"))
    assert ok.status_code == 200 and ok.json()["actor_id"]
    settle(api.factory)
    assert api.get(f"/api/cases/{cid}", headers=rui).json()["state"] == "WAITING_ANY_CHANNEL"
    carlos = ok.json()["actor_id"]
    files = {"files": ("ref.txt", "Para empresas de alimentação, exigir o alvará sanitário emitido pela Vigilância, com validade de 12 meses.".encode(), "text/plain")}
    rnd = api.get(f"/api/cases/{cid}/rounds", headers=rui).json()[-1]
    r = api.post(f"/api/cases/{cid}/messages", headers=rui, files=files, data={
        "actor_id": carlos, "channel": "whatsapp", "text": "Segue o documento de referência da Vigilância.",
        "reply_to_round_id": rnd["id"], "external_key": "wa-carlos-1"})
    assert r.status_code == 200 and r.json()["substantive"]
    settle(api.factory)
    assert api.get(f"/api/cases/{cid}", headers=rui).json()["state"] == "CHANGES_READY"
    att = api.get(f"/api/cases/{cid}/conversations", headers=rui).json()["messages"]
    a = next(m for m in att if m["attachments"])["attachments"][0]
    dl = api.get(f"/api/attachments/{a['id']}", headers=rui)
    assert dl.status_code == 200 and dl.headers["x-content-type-options"] == "nosniff"
    assert api.get(f"/api/attachments/{a['id']}", headers=login(api, "act_marcos")).status_code == 404


def test_cenario_d_decisao_pela_api_e_triagem(api):
    rui = login(api, "act_rui")
    cid = start(api, rui, "D")
    settle(api.factory)
    for k in ("d1", "d2"):
        assert api.post(f"/api/cases/{cid}/script/{k}", headers=rui).status_code == 200
    settle(api.factory)
    c = api.get(f"/api/cases/{cid}", headers=rui).json()
    assert c["state"] == "BLOCKED_HUMAN"
    iv = c["interventions"][0]
    bad = api.post(f"/api/cases/{cid}/decisions", json={"kind": "resolve_conflict", "text": "x"}, headers=idem(rui, "d0"))
    assert bad.status_code == 422
    r = api.post(f"/api/cases/{cid}/decisions", headers=idem(rui, "d1"), json={
        "kind": "resolve_conflict", "intervention_id": iv["id"],
        "text": "Decisão do secretário: a licença sanitária vale somente para Alimentação."})
    assert r.status_code == 200, r.text
    settle(api.factory)
    assert api.get(f"/api/cases/{cid}", headers=rui).json()["state"] == "CHANGES_READY"
    # mensagem sem correlação vai para triagem e aparece no Hoje e na Caixa de entrada
    luiza = "act_luiza"
    r = api.post(f"/api/cases/{cid}/messages", headers=rui, data={"actor_id": luiza, "channel": "whatsapp",
                 "text": "Falta também o campo telefone.", "external_key": "wa-l-9"})
    assert r.json()["triage"] == "pending"
    inbox = api.get("/api/inbox?triage=true", headers=rui).json()
    assert len(inbox) == 1
    assert any(t["kind"] == "triage" for t in api.get("/api/today", headers=rui).json()["tasks"])


def test_upload_recusado_pela_api(api):
    rui = login(api, "act_rui")
    cid = start(api, rui, "A")
    settle(api.factory)
    r = api.post(f"/api/cases/{cid}/messages", headers=rui, files={"files": ("x.zip", b"PK\x03\x04abc", "application/zip")},
                 data={"actor_id": "act_ana", "channel": "whatsapp", "text": "segue", "external_key": "z1"})
    assert r.status_code == 422 and r.json()["code"] == "UPLOAD_REJECTED"
    assert api.get(f"/api/cases/{cid}/conversations", headers=rui).json()["messages"][-1]["direction"] == "out"
