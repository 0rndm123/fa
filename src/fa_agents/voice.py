"""Optional voice-to-text transcription for the local FA_Agent workbench.

Audio is forwarded only after an explicit user recording action. No audio is
stored by FA_Agent and no model is permitted to execute a trading operation.
"""
from __future__ import annotations

import os

MAX_AUDIO_BYTES = 10 * 1024 * 1024
SUPPORTED_MIME = {
    "audio/webm": ("recording.webm", "audio/webm"),
    "audio/ogg": ("recording.ogg", "audio/ogg"),
    "audio/mp4": ("recording.mp4", "audio/mp4"),
    "audio/mpeg": ("recording.mp3", "audio/mpeg"),
    "audio/wav": ("recording.wav", "audio/wav"),
    "audio/x-wav": ("recording.wav", "audio/wav"),
    "audio/x-m4a": ("recording.m4a", "audio/mp4"),
    "audio/aac": ("recording.aac", "audio/aac"),
    "audio/flac": ("recording.flac", "audio/flac"),
}


class VoiceTranscriptionError(Exception):
    """Safe, user-displayable voice transcription failure."""


def transcription_configured() -> bool:
    from .llm import resolve_api_key
    try:
        resolve_api_key()
        import openai  # noqa: F401 - optional dependency under [ai]
        return True
    except (ValueError, ImportError):
        return False


def transcribe_audio(data: bytes, content_type: str | None) -> str:
    """Return plain transcript; caller must request user review before analysis."""
    if not data:
        raise ValueError("Empty voice recording.")
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Voice recording exceeds the 10 MB limit.")
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    entry = SUPPORTED_MIME.get(mime)
    if entry is None:
        raise ValueError("Unsupported voice format. Use a browser with MediaRecorder support.")
    try:
        from .llm import resolve_api_key
        from openai import OpenAI
        api_key = resolve_api_key()
    except (ValueError, ImportError) as exc:
        raise VoiceTranscriptionError("Voice transcription requires the OpenAI API key and the [ai] extra.") from exc
    try:
        language = (os.getenv("FA_VOICE_LANGUAGE", "pt") or "").strip().lower()
        options = {"model": "gpt-4o-mini-transcribe", "file": (entry[0], data, entry[1])}
        if language:
            options["language"] = language
        response = OpenAI(api_key=api_key, timeout=40.0, max_retries=0).audio.transcriptions.create(**options)
        text = str(response.text or "").strip()
        if not text:
            raise VoiceTranscriptionError("No speech was detected. Record again.")
        return text[:6000]
    except VoiceTranscriptionError:
        raise
    except Exception as exc:
        # Do not disclose API credentials or provider response details in the browser.
        raise VoiceTranscriptionError("Voice transcription provider unavailable. Try again.") from exc
