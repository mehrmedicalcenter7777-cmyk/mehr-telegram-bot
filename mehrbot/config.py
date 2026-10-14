"""Loads settings, doctors, style guide and secrets."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"


@dataclass
class Secrets:
    telegram_token: str
    admin_chat_id: str
    gemini_api_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str


@dataclass
class Config:
    settings: dict
    doctors: list
    style: str
    secrets: Secrets


def _env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"{name} muhit o'zgaruvchisi (GitHub Secret) berilmagan")
    return value


def load_secrets(required: bool = True) -> Secrets:
    return Secrets(
        telegram_token=_env("TELEGRAM_BOT_TOKEN", required),
        admin_chat_id=_env("ADMIN_CHAT_ID", required),
        gemini_api_key=_env("GEMINI_API_KEY", required),
        elevenlabs_api_key=_env("ELEVENLABS_API_KEY", required),
        elevenlabs_voice_id=_env("ELEVENLABS_VOICE_ID", required),
    )


def load(require_secrets: bool = True) -> Config:
    settings = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))
    doctors = yaml.safe_load((CONFIG_DIR / "doctors.yaml").read_text(encoding="utf-8")) or {}
    style = (CONFIG_DIR / "style.md").read_text(encoding="utf-8")
    return Config(
        settings=settings,
        doctors=doctors.get("doctors") or [],
        style=style,
        secrets=load_secrets(require_secrets),
    )
