"""
Speech-to-text seam — Deepgram REST API (SDK v7+).
"""
from __future__ import annotations

import os


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """
    Transcribe audio bytes to text using Deepgram nova-2.
    Returns the transcript string, or an error message prefixed with '[STT error]'.
    """
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        return "[STT error] DEEPGRAM_API_KEY is not set in .env"

    try:
        from deepgram import DeepgramClient

        client = DeepgramClient(api_key=key)
        payload = {"buffer": audio_bytes, "mimetype": mime_type}
        options = {"model": "nova-2", "smart_format": True, "punctuate": True}

        response = client.listen.rest.v("1").transcribe_file(payload, options)
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript.strip()

    except ImportError:
        return "[STT error] deepgram-sdk is not installed. Run: pip install deepgram-sdk"
    except Exception as e:
        return f"[STT error] Transcription failed: {e}"
