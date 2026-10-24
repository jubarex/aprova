"""Adaptador de replay identificado (v2 §2.1, §11.3).

Gravações são fixtures de teste indexadas por entrada normalizada + versão do contrato.
Entrada sem gravação => ReplayMiss (REPLAY_MISS); nunca se inventa análise.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .contracts import AgentEnvelope

CONTRACT_VERSION = "1"
ADAPTER_NAME = "offline_replay"


class ReplayMiss(Exception):
    code = "REPLAY_MISS"


@dataclass(frozen=True)
class AnalysisInput:
    ticket_reply: str
    base_hash: str

    def key(self) -> str:
        norm = json.dumps(
            {"reply": " ".join(self.ticket_reply.split()), "base": self.base_hash, "v": CONTRACT_VERSION},
            sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()


_REGISTRY: dict[str, tuple[str, dict]] = {}


def register(fixture_id: str, inp: AnalysisInput, output: dict) -> None:
    _REGISTRY[inp.key()] = (fixture_id, output)


def clear() -> None:
    _REGISTRY.clear()


def analyze(inp: AnalysisInput, case_id: str, case_version: int) -> tuple[AgentEnvelope, dict]:
    hit = _REGISTRY.get(inp.key())
    if hit is None:
        raise ReplayMiss("sem gravação correspondente para esta entrada")
    fixture_id, output = hit
    env = AgentEnvelope.model_validate({**output, "case_id": case_id, "expected_case_version": case_version})
    meta = {"adapter": ADAPTER_NAME, "fixture_id": fixture_id, "input_hash": inp.key(), "simulated": True}
    return env, meta
