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
        language = (os.getenv("FA_VOICE_LANGUAGE", "") or "").strip().lower()
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
    # Keep a known supported voice by default, with a small allowlist.
    voice = (os.getenv("FA_VOICE_NAME", "cedar") or "cedar").strip().lower()
    if voice not in {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova",
                     "onyx", "sage", "shimmer", "verse", "marin", "cedar"}:
        raise ValueError("FA_VOICE_NAME must be a supported OpenAI speech voice.")
    try:
        response = OpenAI(api_key=api_key, timeout=45.0, max_retries=0).audio.speech.create(
            model="gpt-4o-mini-tts", voice=voice, input=text, response_format="mp3",
            instructions=(
                "Use a natural, composed adult conversational delivery. "
                "Speak with clear articulation, warm but restrained expression, "
                "natural intonation and a moderately paced rhythm. "
                "For Portuguese text, use European Portuguese pronunciation and "
                "vocabulary, not Brazilian Portuguese. For English text, use "
                "natural British English pronunciation. "
                "Pronounce financial figures, percentages, dates, ticker symbols "
                "and company names carefully. Avoid dramatic narration, exaggerated "
                "enthusiasm, robotic cadence or artificial pauses. "
                "Read only the supplied answer; do not add or change facts."
            ),
        )
        # Only accept a bounded binary response. The audio never reaches disk.
        audio = response.content
        if not isinstance(audio, bytes) or not audio or len(audio) > MAX_SPEECH_BYTES:
            raise VoiceTranscriptionError("Spoken reply audio was empty or too large.")
        return audio
    except VoiceTranscriptionError:
        raise
    except Exception as exc:
        # API exceptions can contain sensitive request details.
        raise VoiceTranscriptionError("Spoken reply provider unavailable. Try again.") from exc
