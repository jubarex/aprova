"""Loader das instruções versionadas (fonte única). Cada ação registra id e hash (INSTRUCTIONS.md)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

INSTRUCTIONS_DIR = Path(__file__).resolve().parents[3] / "INSTRUCTIONS"


@dataclass(frozen=True)
class LoadedInstruction:
    id: str
    sha256: str
    text: str


def load(instruction_id: str) -> LoadedInstruction:
    path = INSTRUCTIONS_DIR / f"{instruction_id}.md"
    text = path.read_text(encoding="utf-8")
    return LoadedInstruction(instruction_id, hashlib.sha256(text.encode("utf-8")).hexdigest(), text)


def load_many(ids: list[str]) -> list[LoadedInstruction]:
    return [load(i) for i in ids]
