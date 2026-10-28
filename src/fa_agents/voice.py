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


MAX_SPEECH_CHARS = 2200


def synthesize_speech(text: str) -> bytes:
    """Synthesize a bounded spoken research answer using the configured voice."""
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_SPEECH_CHARS:
        raise ValueError("Speech text must contain 1 to 2200 characters.")
    from .model_settings import load_settings
    try:
        from .llm import resolve_api_key
        from openai import OpenAI
        settings = load_settings()
        options = {
            "model": settings["speech"],
            "voice": settings["voice"],
            "input": text,
            "response_format": "mp3",
        }
        if settings["speech"] == "gpt-4o-mini-tts":
            options["instructions"] = (
                "Use a natural, composed adult conversational delivery with clear "
                "articulation, restrained expression, natural intonation and moderately "
                "paced rhythm. Use European Portuguese for Portuguese text and British "
                "English for English text. Pronounce financial figures, percentages, "
                "dates, ticker symbols and company names carefully. Avoid theatrical "
                "intonation and robotic pacing. Only read the supplied answer."
            )
        response = OpenAI(api_key=resolve_api_key(), timeout=40.0, max_retries=0).audio.speech.create(
            **options
        )
        audio = response.read()
        if not audio or len(audio) > 6_000_000:
            raise VoiceTranscriptionError("Invalid generated speech response.")
        return audio
    except (ValueError, ImportError) as exc:
        raise VoiceTranscriptionError("Voice synthesis needs a valid API key and the [ai] extra.") from exc
    except VoiceTranscriptionError:
        raise
    except Exception as exc:
        raise VoiceTranscriptionError("Speech provider unavailable. Try again.") from exc
