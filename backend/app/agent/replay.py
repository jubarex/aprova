"""Adaptador de replay identificado (v2 §2.1, §11.3).

Gravações são fixtures de teste indexadas por entrada normalizada + versão do contrato.
Entrada sem gravação => ReplayMiss (REPLAY_MISS); nunca se inventa análise.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .contracts import AgentEnvelope, AgentOutput

CONTRACT_VERSION = "2"
ADAPTER_NAME = "offline_replay"


class ReplayMiss(Exception):
    code = "REPLAY_MISS"


def _norm(t: str) -> str:
    return " ".join(t.split())


@dataclass(frozen=True)
class AnalysisInput:
    """Entrada normalizada: estágio, resposta inicial, base e fontes na ordem de recepção."""

    ticket_reply: str
    base_hash: str
    stage: str = "initial"
    sources: tuple[str, ...] = field(default_factory=tuple)  # textos de S1..Sn
    open_gaps: tuple[str, ...] = field(default_factory=tuple)  # perguntas das lacunas abertas, G1..Gn

    def key(self) -> str:
        norm = json.dumps(
            {"stage": self.stage, "reply": _norm(self.ticket_reply), "base": self.base_hash,
             "sources": [_norm(s) for s in self.sources], "gaps": [_norm(g) for g in self.open_gaps],
             "v": CONTRACT_VERSION},
            sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()


_REGISTRY: dict[str, tuple[str, dict]] = {}


def register(fixture_id: str, inp: AnalysisInput, output: dict) -> None:
    AgentOutput.model_validate(output)  # fixture inválida falha cedo
    _REGISTRY[inp.key()] = (fixture_id, output)


def clear() -> None:
    _REGISTRY.clear()


def registered() -> list[str]:
    return sorted(f for f, _ in _REGISTRY.values())


def analyze(inp: AnalysisInput, case_id: str, case_version: int) -> tuple[AgentEnvelope, dict]:
    hit = _REGISTRY.get(inp.key())
    if hit is None:
        raise ReplayMiss("sem gravação correspondente para esta entrada")
    fixture_id, output = hit
    env = AgentEnvelope.model_validate({**output, "case_id": case_id, "expected_case_version": case_version})
    meta = {"adapter": ADAPTER_NAME, "fixture_id": fixture_id, "input_hash": inp.key(), "simulated": True}
    return env, meta
