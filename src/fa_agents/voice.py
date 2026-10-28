"""Opt-in audio I/O for the local FA research workbench.

Audio travels from the local browser to the local FastAPI backend and to the
configured OpenAI audio service. Nothing is recorded on disk or sent to SysTrd.
"""
from __future__ import annotations

from io import BytesIO

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_SPEECH_CHARS = 2200
CONTENT_TYPES = {
    "audio/webm": "voice.webm",
    "audio/mp4": "voice.mp4",
    "audio/mpeg": "voice.mp3",
    "audio/wav": "voice.wav",
    "audio/x-wav": "voice.wav",
}


class VoiceError(RuntimeError):
    """Safe-to-display audio service failure."""


def _client():
    from .llm import resolve_api_key
    try:
        key = resolve_api_key()
    except ValueError as exc:
        raise VoiceError("OpenAI API key required for audio transcription and voice replies.") from exc
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise VoiceError('Install optional AI packages: pip install -e ".[ai]"') from exc
    return OpenAI(api_key=key, timeout=45.0, max_retries=1)


def transcribe_audio(audio: bytes, mime: str) -> str:
    """Recognize a bounded recording; retain no audio or transcript server-side."""
    if not audio or len(audio) > MAX_AUDIO_BYTES:
        raise VoiceError("Invalid audio length.")
    filename = CONTENT_TYPES.get(mime)
    if not filename:
        raise VoiceError("Unsupported audio format; use WebM, MP4, MP3 or WAV.")
    stream = BytesIO(audio)
    stream.name = filename
    try:
        result = _client().audio.transcriptions.create(
            model="gpt-transcribe",
            file=stream,
            prompt=("A Portuguese financial research conversation about "
                    "backtests, BTCUSDT, NVIDIA, RSI, EMA, COT, Profit Factor, "
                    "drawdown, fundamentals, valuation and technical analysis."),
        )
    except Exception as exc:
        raise VoiceError("Audio transcription failed. Verify API credentials and connectivity.") from exc
    text = str(getattr(result, "text", "") or "").strip()
    if not text:
        raise VoiceError("No intelligible speech was detected.")
    return text[:6000]


def synthesize_speech(text: str) -> bytes:
    """Create a single spoken reply; text is clipped to protect latency and cost."""
    if not text.strip():
        raise VoiceError("No text available for voice playback.")
    # This is the same text the user can read in the UI; no ungrounded LLM audio.
    try:
        response = _client().audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="cedar",
            input=text[:MAX_SPEECH_CHARS],
            instructions=("Speak naturally in European Portuguese when the text is Portuguese. "
                          "Keep a measured, professional tone and articulate financial "
                          "figures and instrument symbols clearly."),
            response_format="mp3",
        )
        audio = response.read()
    except Exception as exc:
        raise VoiceError("Voice synthesis failed. Verify API credentials and connectivity.") from exc
    if not audio or len(audio) > 5_000_000:
        raise VoiceError("Invalid synthesized audio.")
    return audio
