"""
Speech-to-text seam — Deepgram prerecorded API.
Swap this file to change transcription providers without touching anything else.
"""
from __future__ import annotations

import os


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """
    Transcribe audio bytes to text using Deepgram.
    Returns the transcript string, or an error message prefixed with '[STT error]'.
    """
    try:
        from deepgram import DeepgramClient, PrerecordedOptions
    except ImportError:
        return "[STT error] deepgram-sdk is not installed. Run: pip install deepgram-sdk"

    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        return "[STT error] DEEPGRAM_API_KEY is not set in .env"

    try:
        dg = DeepgramClient(key)
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            punctuate=True,
        )
        payload = {"buffer": audio_bytes, "mimetype": mime_type}
        response = dg.listen.prerecorded.v("1").transcribe_file(payload, options)
        transcript = (
            response.results.channels[0].alternatives[0].transcript
        )
        return transcript.strip()
    except Exception as e:
        return f"[STT error] Deepgram transcription failed: {e}"
