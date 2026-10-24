"""Métricas (N/A), adaptador ao vivo com transporte simulado e o gate F."""

import json

import httpx
import pytest

from app.agent import live, replay
from app.application import metrics
from app.application.common import AppError
from app.evaluation import generalization
from app.persistence.db import tx
from tests.helpers import settle, start, step


def test_metricas_denominador_zero_e_na(env):
    with tx(env) as s:
        m = metrics.compute(s)
    assert m["cobertura_auditavel"]["valor"] is None  # N/A, nunca 100%
    assert m["processes"]["total"] == 140 and m["processes"]["nao_iniciados"] == 140
    assert m["rodadas_ate_aprovacao"]["media"] is None


def test_metricas_com_caso_e_modos_separados(env, tmp_path):
    cid = start(env, "A")
    settle(env)
    step(env, tmp_path, cid, "a1")
    settle(env)
    with tx(env) as s:
        m = metrics.compute(s)
    assert m["processes"]["nao_iniciados"] == 139  # o caso iniciado sai dos não iniciados
    assert m["solicitacoes"]["inicial"] == 5 and m["solicitacoes"]["pendente"] == 5
    assert m["modos"]["ia"].get("offline_replay", 0) >= 2
    assert m["evidence_class"] == "benchmark_local_sintetico"
    assert m["baseline_roteirizado"][0]["um_item_por_rodada"] == 4


def _mock(content, calls=None):
    def handler(request: httpx.Request):
        if calls is not None:
            calls.append(json.loads(request.content))
        body = content if isinstance(content, str) else json.dumps(content)
        return httpx.Response(200, json={"choices": [{"message": {"content": body}}], "usage": {"total_tokens": 10}})
    return httpx.MockTransport(handler)


def _cfg(monkeypatch, key="k"):
    monkeypatch.setenv("LLM_BASE_URL", "http://fake")
    monkeypatch.setenv("LLM_API_KEY", key)
    monkeypatch.setenv("LLM_MODEL", "m")


def test_live_sem_configuracao_nao_cai_para_replay(monkeypatch):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(AppError) as e:
        live.analyze(replay.AnalysisInput("x", "h"), "c", 1, [], [])
    assert e.value.code == "LLM_NOT_CONFIGURED"


def test_live_corrige_uma_vez_e_limita_chamadas(monkeypatch):
    _cfg(monkeypatch)
    calls = []
    seq = iter(["isto nao e json", json.dumps({"stage": "initial", "evidence": [], "requests": []})])

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"choices": [{"message": {"content": next(seq)}}]})

    env, meta = live.analyze(replay.AnalysisInput("x", "h"), "c", 1, [], [], transport=httpx.MockTransport(handler))
    assert len(calls) == 2 and meta["calls"] == 2 and meta["simulated"] is False
    with pytest.raises(AppError) as e:  # duas saídas inválidas => falha explícita, sem terceira chamada
        live.analyze(replay.AnalysisInput("x", "h"), "c", 1, [], [], transport=_mock("lixo"))
    assert e.value.code == "LLM_FAILED"


def test_live_chave_nao_vaza_nas_mensagens(monkeypatch):
    _cfg(monkeypatch, "segredo-123")
    sent = []
    live.analyze(replay.AnalysisInput("x", "h"), "c", 1, [], [], transport=_mock({"stage": "initial"}, calls=sent))
    assert "segredo-123" not in json.dumps(sent)


def test_gate_f_nao_configurado_e_not_run(monkeypatch, tmp_path):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(generalization, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(generalization, "FREEZE_FILE", tmp_path / "freeze.json")
    rep = generalization.run()
    assert rep["result"] == "not_run" and "fabricado" in rep["reason"]
    assert list(tmp_path.glob("evaluation-*.json"))


def _ideal_output(form):
    """Saída construída a partir do gabarito, só para validar o comparador (não representa o agente)."""
    reply = form["reply"]
    gold_all = json.loads((generalization.HERE / "gold.json").read_text(encoding="utf-8"))["forms"]
    gold = next(g for g in gold_all if g["id"] == form["id"])
    ev, reqs, gaps, ops = [], [], [], []
    for i, g in enumerate(gold["intents"]):
        a = reply.index(g["quote"])
        ev.append({"source_ref": "TICKET", "start": a, "end": a + len(g["quote"]), "quote": g["quote"]})
        if g["kind"] == "supported":
            reqs.append({"summary": "s", "evidence_indexes": [i], "clarity": "clear", "feasibility": "supported",
                         "risk": "low", "next_action": "propose_change"})
            o = {"op": g["op"], "field_id": g["field_id"]}
            if g["op"] == "rename_label":
                o["label"] = "Novo"
            elif g["op"] == "set_help":
                o["help_text"] = "Informe rua e número"
            else:
                o["required"] = True
            ops.append({"operation": o, "evidence_indexes": [i]})
        elif g["kind"] == "ambiguous":
            reqs.append({"summary": "a", "evidence_indexes": [i], "clarity": "partial", "feasibility": "unknown",
                         "risk": "low", "next_action": "clarify"})
            gaps.append({"request_index": len(reqs) - 1, "question": "Qual o detalhe?", "answer_kind": "text",
                         "topic": "geral"})
        else:
            reqs.append({"summary": "r", "evidence_indexes": [i], "clarity": "clear",
                         "feasibility": "requires_product_review", "risk": "medium", "next_action": "escalate"})
    out = {"stage": "initial", "evidence": ev, "requests": reqs, "gaps": gaps}
    if ops:
        out["change_set"] = {"rationale": "r", "operations": ops, "tests": []}
    return out


def test_gate_f_com_transporte_simulado_valida_comparador(monkeypatch, tmp_path):
    monkeypatch.setattr(generalization, "ARTIFACTS", tmp_path)
    monkeypatch.setattr(generalization, "FREEZE_FILE", tmp_path / "freeze.json")
    _cfg(monkeypatch)
    forms = json.loads((generalization.HERE / "inputs.json").read_text(encoding="utf-8"))["forms"]
    seen = []

    def handler(request):
        user = json.loads(json.loads(request.content)["messages"][1]["content"])
        seen.append(json.dumps(user).lower())
        form = next(f for f in forms if f["reply"] == user["ticket_reply"]["text"])
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(_ideal_output(form))}}]})

    rep = generalization.run(transport=httpx.MockTransport(handler))
    m = rep["metrics"]
    assert m["runs"] == 9 and m["failed_runs"] == 0
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and rep["result"] == "passed"
    assert m["citations_valid"] == 1.0 and m["blocking_gaps_found"] == 1.0
    assert not any("blocking_gap" in x or '"intents"' in x for x in seen)  # o agente nunca recebe o gabarito
    # congelamento: mudar o gabarito invalida a execução
    (tmp_path / "freeze.json").write_text(json.dumps({"gold": "outro"}), encoding="utf-8")
    assert generalization.run(transport=httpx.MockTransport(handler))["result"] == "failed"
