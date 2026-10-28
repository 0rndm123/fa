"""Optional voice-to-text transcription for the local FA_Agent workbench.

Audio is forwarded only after an explicit user recording action. No audio is
stored by FA_Agent and no model is permitted to execute a trading operation.
"""
from __future__ import annotations

import os

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_SPEECH_CHARS = 2200
MAX_SPEECH_BYTES = 5 * 1024 * 1024
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
        from .model_settings import load_settings
        settings = load_settings()
        language = (os.getenv("FA_VOICE_LANGUAGE") or settings["language"]).strip().lower()
        options = {"model": settings["transcription"], "file": (entry[0], data, entry[1])}
        if language and language != "auto":
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


def synthesize_speech(text: str) -> bytes:
    """Generate a short spoken answer on demand. Never persist generated audio."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A non-empty spoken answer is required.")
    if len(text) > MAX_SPEECH_CHARS:
        raise ValueError("Spoken answer exceeds the 2200-character limit.")
    try:
        from .llm import resolve_api_key
        from openai import OpenAI
        api_key = resolve_api_key()
    except (ValueError, ImportError) as exc:
        raise VoiceTranscriptionError("Spoken replies require the OpenAI API key and [ai] extra.") from exc
    try:
        from .model_settings import load_settings
        settings = load_settings()
        voice = (os.getenv("FA_VOICE_NAME") or settings["voice"]).strip().lower()
        from .model_settings import VOICES
        if voice not in VOICES:
            raise ValueError("FA_VOICE_NAME must be a supported speech voice.")
        options = {"model": settings["speech"], "voice": voice,
                   "input": text, "response_format": "mp3"}
        if settings["speech"] == "gpt-4o-mini-tts":
            options["instructions"] = (
                "Speak in European Portuguese when the text is Portuguese, and British English "
                "when it is English. Use a measured, professional tone; pronounce numbers "
                "and asset tickers clearly. Do not add or change any words."
            )
        response = OpenAI(api_key=api_key, timeout=45.0, max_retries=0).audio.speech.create(
            **options
        )
        # Only accept a bounded binary response. The audio never reaches disk.
        audio = response.content
        if not isinstance(audio, bytes) or not audio or len(audio) > MAX_SPEECH_BYTES:
            raise VoiceTranscriptionError("Spoken reply audio was empty or too large.")
        return audio
    except VoiceTranscriptionError:
        raise
    except ValueError as exc:
        if str(exc).startswith("FA_VOICE_NAME"):
            raise
        raise VoiceTranscriptionError("Invalid model configuration or speech provider request.") from exc
    except Exception as exc:
        # API exceptions can contain sensitive request details.
        raise VoiceTranscriptionError("Spoken reply provider unavailable. Try again.") from exc
