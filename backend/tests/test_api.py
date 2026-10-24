import pytest
from fastapi.testclient import TestClient

from app.agent import replay
from app.api.main import create_app
from app.application import changes
from app.config import Settings
from app.worker import runner


@pytest.fixture()
def api(tmp_path):
    replay.clear()
    changes.FAULTS.clear()
    st = Settings("demo", "offline_replay", f"sqlite:///{(tmp_path / 'api.db').as_posix()}", tmp_path / "att")
    app = create_app(st, start_worker=False)
    with TestClient(app) as c:
        c.factory = app.state.factory
        yield c


def login(api, actor_id):
    r = api.post("/api/demo/session", json={"actor_id": actor_id})
    assert r.status_code == 200
    return {"X-Demo-Token": r.json()["token"]}


def idem(h, key):
    return {**h, "Idempotency-Key": key}


def test_cenario_g_via_http_com_portal(api):
    rui = login(api, "act_rui")
    ana = login(api, "act_ana")
    cid = api.post("/api/demo/scenarios/G/start", headers=rui).json()["case_id"]
    runner.drain(api.factory)
    case = api.get(f"/api/cases/{cid}", headers=rui).json()
    assert case["state"] == "CHANGES_READY"
    assert case["municipality"]["short"] == "VR"
    assert len(case["change_requests"]) == 2

    # Hoje: aparece a tarefa de revisar testes, com cliente e motivo
    today = api.get("/api/today", headers=rui).json()
    t = next(x for x in today["tasks"] if x["kind"] == "review_tests")
    assert t["client"]["name"] == "Prefeitura de Vale do Ribeiro" and t["why"]["text"]

    cs = api.get(f"/api/cases/{cid}/change-sets", headers=rui).json()[0]
    assert api.post(f"/api/change-sets/{cs['id']}/tests/review", headers=rui).status_code == 200
    r = api.post(f"/api/change-sets/{cs['id']}/request-approval",
                 json={"expected_case_version": case["version"]}, headers=idem(rui, "k1"))
    assert r.status_code == 200 and r.json()["state"] == "WAITING_MUNICIPAL_APPROVAL"

    # Portal: Ana vê "Seu próximo passo" e o diff em linguagem simples
    home = api.get("/api/portal/me", headers=ana).json()
    assert home["next_step"]["kind"] == "approval" and home["municipality"]["short"] == "VR"
    view = api.get(f"/api/portal/approvals/{cs['id']}", headers=ana).json()
    assert view["can_decide"] is True
    texts = " ".join(c["text"] for c in view["changes"])
    assert "Ramo de atividade" in texts and "obrigatório" in texts
    assert any("Alimentação" in e["when"] for e in view["examples"])

    body = {"decision": "approve", "expected_case_version": view["case_version"]}
    r = api.post(f"/api/portal/approvals/{cs['id']}", json=body, headers=idem(ana, "ap1"))
    assert r.status_code == 200 and r.json()["state"] == "WAITING_IMPLANTER_APPROVAL"
    # retry legítimo devolve o resultado original (T16), não 409 de revisão consumida
    r2 = api.post(f"/api/portal/approvals/{cs['id']}", json=body, headers=idem(ana, "ap1"))
    assert r2.status_code == 200 and r2.json() == r.json()
    # mesma chave com outro conteúdo => conflito
    r3 = api.post(f"/api/portal/approvals/{cs['id']}", json={**body, "rationale": "x"}, headers=idem(ana, "ap1"))
    assert r3.status_code == 409 and r3.json()["code"] == "IDEMPOTENCY_CONFLICT"

    v = api.get(f"/api/cases/{cid}", headers=rui).json()["version"]
    r = api.post(f"/api/change-sets/{cs['id']}/implanter-approval",
                 json={"decision": "approve", "expected_case_version": v}, headers=idem(rui, "ap2"))
    assert r.status_code == 200
    runner.drain(api.factory)
    final = api.get(f"/api/cases/{cid}", headers=rui).json()
    assert final["state"] == "COMPLETED" and final["ticket"]["status"] == "closed"
    tl = api.get(f"/api/cases/{cid}/timeline", headers=rui).json()
    assert [e["action"] for e in tl][-1] == "verified_and_closed"


def test_sem_sessao_e_papel(api):
    assert api.get("/api/today").status_code == 401
    ana = login(api, "act_ana")
    assert api.get("/api/today", headers=ana).status_code == 403  # contato não vê a tela do implantador
    rui = login(api, "act_rui")
    assert api.get("/api/portal/me", headers=rui).status_code == 403  # implantador não usa o portal


def test_portal_isolamento_entre_municipios(api):
    rui = login(api, "act_rui")
    marcos = login(api, "act_marcos")  # contato de Serra Alta
    cid = api.post("/api/demo/scenarios/G/start", headers=rui).json()["case_id"]
    runner.drain(api.factory)
    cs = api.get(f"/api/cases/{cid}/change-sets", headers=rui).json()[0]
    assert api.get(f"/api/portal/approvals/{cs['id']}", headers=marcos).status_code == 404
    r = api.post(f"/api/portal/approvals/{cs['id']}", json={"decision": "approve", "expected_case_version": 1},
                 headers=idem(marcos, "x"))
    assert r.status_code == 404
    home = api.get("/api/portal/me", headers=marcos).json()
    assert home["municipality"]["short"] == "SA" and not home["today"]


def test_joao_responde_mas_nao_aprova(api):
    rui, joao = login(api, "act_rui"), login(api, "act_joao")
    cid = api.post("/api/demo/scenarios/G/start", headers=rui).json()["case_id"]
    runner.drain(api.factory)
    cs = api.get(f"/api/cases/{cid}/change-sets", headers=rui).json()[0]
    api.post(f"/api/change-sets/{cs['id']}/tests/review", headers=rui)
    v = api.get(f"/api/cases/{cid}", headers=rui).json()["version"]
    api.post(f"/api/change-sets/{cs['id']}/request-approval", json={"expected_case_version": v},
             headers=idem(rui, "r1"))
    v = api.get(f"/api/cases/{cid}", headers=rui).json()["version"]
    r = api.post(f"/api/portal/approvals/{cs['id']}", json={"decision": "approve", "expected_case_version": v},
                 headers=idem(joao, "j1"))
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    view = api.get(f"/api/portal/approvals/{cs['id']}", headers=joao).json()
    assert view["can_decide"] is False


def test_erro_padrao_e_idempotency_key_obrigatoria(api):
    rui = login(api, "act_rui")
    r = api.post("/api/tickets", json={"process_id": "proc_vr_iss012", "title": "abc", "initial_reply": "x"},
                 headers=rui)
    assert r.status_code == 400
    body = r.json()
    assert set(body) == {"code", "message", "details", "request_id", "retryable"}


def test_reset_exige_confirmacao(api):
    rui = login(api, "act_rui")
    assert api.post("/api/demo/reset", json={"confirm": "nao"}, headers=rui).status_code == 400
    assert api.post("/api/demo/reset", json={"confirm": "RESETAR"}, headers=rui).status_code == 200
