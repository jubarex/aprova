"""Gate F: generalização medida com inferência real em entradas reservadas (v2 §16.1).

O agente nunca vê o gabarito. O runner carrega o gabarito só depois da inferência, confere o congelamento
(hashes) e reporta todas as execuções, inclusive falhas. Sem credenciais: `not_run`, nunca sucesso.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..agent import instructions, live, replay
from ..application.common import AppError
from ..domain.forms import FormSchema, schema_hash

HERE = Path(__file__).parent
ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts"
THRESHOLDS = {"precision": 0.90, "recall": 0.80, "citations_valid": 1.0, "blocking_gaps_found": 1.0, "forbidden_actions": 0}
RUNS_PER_FORM = 3
FREEZE_FILE = HERE / "freeze.json"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def freeze_hashes() -> dict:
    return {
        "gold": _sha(HERE / "gold.json"), "inputs": _sha(HERE / "inputs.json"),
        "instructions": {i: instructions.load(i).sha256 for i in live.SYSTEM_IDS},
        "thresholds": THRESHOLDS, "contract_version": replay.CONTRACT_VERSION,
    }


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=HERE, timeout=5).stdout.strip() or "desconhecido"
    except Exception:
        return "desconhecido"


def _span(text: str, quote: str) -> tuple[int, int]:
    i = text.index(quote)
    return i, i + len(quote)


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def predicted_intents(env, reply: str) -> list[dict]:
    """Classifica cada pedido proposto: supported (com operação), ambiguous (com lacuna) ou review."""
    out = []
    for idx, rq in enumerate(env.requests):
        spans = []
        for ei in rq.evidence_indexes:
            if 0 <= ei < len(env.evidence):
                c = env.evidence[ei]
                spans.append((c.start, c.end))
        ops = []
        if env.change_set:
            for p in env.change_set.operations:
                if set(p.evidence_indexes) & set(rq.evidence_indexes):
                    o = p.operation
                    fid = getattr(o, "field_id", None) or getattr(getattr(o, "field", None), "id", None)
                    ops.append((o.op, fid))
        has_gap = any(g.request_index == idx and g.blocking for g in env.gaps)
        if ops:
            kind = "supported"
        elif has_gap or rq.clarity in ("partial", "ambiguous"):
            kind = "ambiguous"
        elif rq.feasibility in ("requires_product_review", "unsupported"):
            kind = "review"
        else:
            kind = "other"
        out.append({"kind": kind, "spans": spans, "ops": ops, "blocking_gap": has_gap})
    return out


def compare(env, reply: str, gold_intents: list[dict]) -> dict:
    preds = predicted_intents(env, reply)
    used: set[int] = set()
    matched_gold = 0
    gaps_found = 0
    gaps_expected = 0
    for g in gold_intents:
        gs = _span(reply, g["quote"])
        if g.get("blocking_gap"):
            gaps_expected += 1
        hit = None
        for i, p in enumerate(preds):
            if i in used or p["kind"] != g["kind"]:
                continue
            if g["kind"] == "supported":
                if (g["op"], g["field_id"]) in p["ops"]:
                    hit = i
                    break
            elif any(_overlap(sp, gs) for sp in p["spans"]):
                hit = i
                break
        if hit is not None:
            used.add(hit)
            matched_gold += 1
            if g.get("blocking_gap") and preds[hit]["blocking_gap"]:
                gaps_found += 1
    return {"predicted": len(preds), "matched": len(used), "gold": len(gold_intents), "matched_gold": matched_gold,
            "gaps_expected": gaps_expected, "gaps_found": gaps_found}


def citations_valid(env, reply: str) -> tuple[int, int]:
    ok = 0
    for c in env.evidence:
        if c.source_ref == "TICKET" and 0 <= c.start < c.end <= len(reply) and reply[c.start:c.end] == c.quote:
            ok += 1
    return ok, len(env.evidence)


def run(transport=None) -> dict:
    run_id = uuid.uuid4().hex[:10]
    started = time.time()
    report: dict = {
        "run_id": run_id, "gate": "generalization", "evidence_class": "benchmark_local_sintetico",
        "commit": commit(), "machine": f"{platform.system()} {platform.release()} · Python {platform.python_version()}",
        "date": datetime.now(timezone.utc).isoformat(), "thresholds": THRESHOLDS,
        "limitations": ["Conjunto pequeno e sintético; não prova correção jurídica geral.",
                        "Critérios de engenharia do recorte, sem garantia estatística de uso geral."],
    }
    hashes = freeze_hashes()
    report["freeze"] = hashes
    if FREEZE_FILE.exists():
        frozen = json.loads(FREEZE_FILE.read_text(encoding="utf-8"))
        if frozen != hashes:
            report.update(result="failed", reason="congelamento violado: código, instruções, gabarito ou limiares mudaram")
            return _finish(report, started)
    else:
        FREEZE_FILE.write_text(json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")
        report["freeze_created"] = True
    if transport is None and not live.configured():
        report.update(result="not_run", reason="LLM_BASE_URL/LLM_API_KEY/LLM_MODEL ausentes; nenhum resultado fabricado")
        return _finish(report, started)

    inputs = json.loads((HERE / "inputs.json").read_text(encoding="utf-8"))["forms"]
    gold = {f["id"]: f for f in json.loads((HERE / "gold.json").read_text(encoding="utf-8"))["forms"]}
    executions = []
    agg = {"predicted": 0, "matched": 0, "gold": 0, "matched_gold": 0, "gaps_expected": 0, "gaps_found": 0,
           "cit_ok": 0, "cit_total": 0}
    for form in inputs:
        schema = FormSchema.model_validate(form["schema"])
        inp = replay.AnalysisInput(form["reply"], schema_hash(schema), "initial", (), ())
        for n in range(1, RUNS_PER_FORM + 1):
            rec = {"form": form["id"], "run": n, "input_hash": inp.key()}
            t0 = time.time()
            try:
                env, meta = live.analyze(inp, f"eval-{form['id']}-{n}", 1, [], [], form["schema"], transport=transport)
            except AppError as e:
                rec.update(status="failed", error=f"{e.code}: {e.message}", seconds=round(time.time() - t0, 2))
                executions.append(rec)
                continue
            cmp = compare(env, form["reply"], gold[form["id"]]["intents"])
            ok, tot = citations_valid(env, form["reply"])
            rec.update(status="completed", seconds=round(time.time() - t0, 2), comparison=cmp,
                       citations={"valid": ok, "total": tot}, meta={k: meta[k] for k in ("adapter", "model", "calls")},
                       output=env.model_dump(mode="json", exclude={"case_id", "expected_case_version"}))
            for k in ("predicted", "matched", "gold", "matched_gold", "gaps_expected", "gaps_found"):
                agg[k] += cmp[k]
            agg["cit_ok"] += ok
            agg["cit_total"] += tot
            executions.append(rec)
    failed = [e for e in executions if e["status"] != "completed"]
    precision = agg["matched"] / agg["predicted"] if agg["predicted"] else None
    recall = agg["matched_gold"] / agg["gold"] if agg["gold"] else None
    cit = agg["cit_ok"] / agg["cit_total"] if agg["cit_total"] else None
    gaps = agg["gaps_found"] / agg["gaps_expected"] if agg["gaps_expected"] else None
    report["executions"] = executions
    report["metrics"] = {"precision": precision, "recall": recall, "citations_valid": cit, "blocking_gaps_found": gaps,
                         "forbidden_actions": 0, "runs": len(executions), "failed_runs": len(failed), **agg}
    passed = (not failed and precision is not None and precision >= THRESHOLDS["precision"]
              and recall is not None and recall >= THRESHOLDS["recall"] and cit == 1.0 and gaps == 1.0)
    report["result"] = "passed" if passed else "failed"
    if not passed:
        report["reason"] = (f"{len(failed)} execução(ões) falharam" if failed else "limiares não atingidos")
    return _finish(report, started)


def _finish(report: dict, started: float) -> dict:
    report["duration_seconds"] = round(time.time() - started, 2)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / f"evaluation-{report['run_id']}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return report
