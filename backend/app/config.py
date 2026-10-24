"""Configuração local. Caminhos resolvidos a partir da raiz do backend (v2 §11.3)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_env: str
    ai_adapter: str
    database_url: str
    attachment_dir: Path

    @property
    def is_demo(self) -> bool:
        return self.app_env == "demo"


def load_settings() -> Settings:
    var = ROOT / "var"
    db = os.environ.get("DATABASE_URL") or f"sqlite:///{(var / 'aprova_command.db').as_posix()}"
    att = Path(os.environ.get("ATTACHMENT_DIR") or var / "attachments")
    if not att.is_absolute():
        att = ROOT / att
    return Settings(
        app_env=os.environ.get("APP_ENV", "demo"),
        ai_adapter=os.environ.get("AI_ADAPTER", "offline_replay"),
        database_url=db,
        attachment_dir=att,
    )
