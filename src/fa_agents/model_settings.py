"""Local-only FA_Agent model routing and preferences; no provider secrets on disk.

All model IDs are explicit user choices; current deterministic specialists keep
their calculations regardless of model configuration.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

from .catalog import SPECIALISTS

MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,95}$")
TEXT_MODELS = (
    "gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1", "gpt-4o",
    "gpt-5.6-sol", "gpt-6-luna",
)
TRANSCRIPTION_MODELS = ("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1")
SPEECH_MODELS = ("gpt-4o-mini-tts", "tts-1", "tts-1-hd")
VOICES = ("cedar", "marin", "alloy", "ash", "ballad", "coral", "echo", "fable",
          "nova", "onyx", "sage", "shimmer", "verse")
DEFAULTS = {
    "synthesis": os.getenv("FA_LLM_MODEL", "gpt-4.1-mini"),
    "transcription": "gpt-4o-mini-transcribe",
    "speech": "gpt-4o-mini-tts",
    "voice": "cedar",
    "language": "auto",
    "agent_models": {},
    "agent_ai_enabled": [],
}
MAX_AGENT_AI_CALLS = 4
_LOCK = threading.RLock()


def settings_path() -> Path:
    configured = os.getenv("FA_MODEL_SETTINGS_FILE", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".fa_agent" / "model_settings.json"


def _model(value: object, *, choices: tuple[str, ...]) -> str:
    if not isinstance(value, str) or not MODEL_RE.fullmatch(value):
        raise ValueError("Invalid model ID.")
    # Additional model IDs may be entered manually to accommodate API access.
    # The available-model list is indicative; provider access is checked at runtime.
    return value


def _validate(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Model settings must be a JSON object.")
    expected = set(DEFAULTS)
    if set(data) - expected:
        raise ValueError("Unknown model settings field(s).")
    merged = {**DEFAULTS, **data}
    for name, options in (
        ("synthesis", TEXT_MODELS), ("transcription", TRANSCRIPTION_MODELS),
        ("speech", SPEECH_MODELS)
    ):
        merged[name] = _model(merged[name], choices=options)
    if merged["voice"] not in VOICES:
        raise ValueError("Unknown synthesis voice.")
    if merged["language"] not in {"auto", "pt", "en", "es", "fr", "de"}:
        raise ValueError("Unsupported transcription language.")
    models = merged["agent_models"]
    if not isinstance(models, dict) or len(models) > len(SPECIALISTS):
        raise ValueError("Invalid agent model mapping.")
    if set(models) - set(SPECIALISTS):
        raise ValueError("Unknown agent ID in model settings.")
    merged["agent_models"] = {name: _model(value, choices=TEXT_MODELS)
                              for name, value in models.items()}
    enabled = merged["agent_ai_enabled"]
    if not isinstance(enabled, list) or len(enabled) > len(SPECIALISTS):
        raise ValueError("Invalid AI agent selection.")
    if any(not isinstance(name, str) or name not in SPECIALISTS for name in enabled):
        raise ValueError("Unknown AI agent.")
    merged["agent_ai_enabled"] = list(dict.fromkeys(enabled))
    return merged


def load_settings() -> dict:
    with _LOCK:
        path = settings_path()
        if not path.is_file():
            return _validate({})
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return _validate(data)
        except (ValueError, OSError, UnicodeError):
            # Fail closed on invalid persistent state, rather than silently
            # deploying a potentially unexpected model.
            raise ValueError("Model settings file is unreadable or invalid.")


def save_settings(data: dict) -> dict:
    settings = _validate(data)
    with _LOCK:
        path = settings_path()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    prefix=".models_", suffix=".tmp", delete=False) as handle:
                temp = Path(handle.name)
                json.dump(settings, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.chmod(temp, 0o600)
            os.replace(temp, path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    return settings


def metadata() -> dict:
    return {
        "text_models": TEXT_MODELS,
        "transcription_models": TRANSCRIPTION_MODELS,
        "speech_models": SPEECH_MODELS,
        "voices": VOICES,
        "agents": [{"id": identifier, "description": detail}
                   for identifier, detail in SPECIALISTS.items()],
        "max_agent_ai_calls": MAX_AGENT_AI_CALLS,
        "notes": [
            "Available models depend on your OpenAI API account. Listed names do not guarantee access.",
            "Agent models are used only for optional, evidence-limited AI commentary; "
            "deterministic data retrieval and calculations never use an LLM.",
            "Agent AI commentary is opt-in and limited to four specialists per question.",
            "Settings are saved locally outside the Git repository, without API keys.",
        ],
    }
