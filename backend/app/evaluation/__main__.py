"""CLI: python -m app.evaluation --gate offline|generalization  (saída não zero em falha ou configuração ausente)."""

from __future__ import annotations

import argparse
import json
import sys

from . import generalization, offline


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="evaluate")
    ap.add_argument("--gate", choices=["offline", "generalization"], default="offline")
    ap.add_argument("--no-tests", action="store_true", help="não executa a suíte pytest dentro do gate offline")
    ap.add_argument("--refreeze", action="store_true", help="recria o congelamento do conjunto F (decisão explícita)")
    a = ap.parse_args(argv)
    if a.refreeze:
        generalization.FREEZE_FILE.write_text(json.dumps(generalization.freeze_hashes(), indent=2, ensure_ascii=False),
                                              encoding="utf-8")
        print("congelamento recriado")
    if a.gate == "offline":
        rep = offline.run(with_tests=not a.no_tests)
        for r in rep["scenarios"]:
            print(f"{'OK ' if r['passed'] else 'FALHA'} {r['title']} ({r['seconds']}s)")
            for c in r["checks"]:
                if not c["passed"]:
                    print(f"     x {c['check']}: {c['detail']}")
        if rep["tests"]:
            print(f"pytest: exit {rep['tests']['exit_code']} {' '.join(rep['tests']['tail'])}")
        print(f"F: {rep['F']['result']} — {rep['F']['reason']}")
        print(f"resultado offline: {rep['result']}  (artifacts/evaluation-{rep['run_id']}.json)")
        return 0 if rep["result"] == "passed" else 1
    rep = generalization.run()
    print(f"F (generalização): {rep['result']}" + (f" — {rep.get('reason')}" if rep.get("reason") else ""))
    if rep.get("metrics"):
        m = rep["metrics"]
        print(f"precisão {m['precision']:.2f} · recall {m['recall']:.2f} · citações {m['citations_valid']:.2f} · "
              f"lacunas {m['blocking_gaps_found']:.2f} · execuções {m['runs']} (falhas: {m['failed_runs']})")
    print(f"artifacts/evaluation-{rep['run_id']}.json")
    return {"passed": 0, "failed": 1, "not_run": 2}[rep["result"]]


if __name__ == "__main__":
    sys.exit(main())
