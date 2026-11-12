"""
Speech-to-text seam — Deepgram REST API (SDK v7+).
"""
from __future__ import annotations

import os

# One Deepgram client for the process, so its HTTP connection pool is reused
# across turns instead of a new TLS handshake every /transcribe.
_client = None


def _dg():
    global _client
    if _client is None:
        from deepgram import DeepgramClient
        _client = DeepgramClient(api_key=os.environ.get("DEEPGRAM_API_KEY", ""))
    return _client


def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """
    Transcribe audio bytes to text using Deepgram nova-2.
    Returns the transcript string, or an error message prefixed with '[STT error]'.
    """
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        return "[STT error] DEEPGRAM_API_KEY is not set in .env"

    try:
        client = _dg()
        # deepgram-sdk v7: client.listen.v1.media.transcribe_file(request=<bytes>, ...).
        # (The old v3/v4 `client.listen.rest.v("1")` path was removed and 502'd.)
        response = client.listen.v1.media.transcribe_file(
            request=audio_bytes, model="nova-2", smart_format=True, punctuate=True)
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript.strip()

    except ImportError:
        return "[STT error] deepgram-sdk is not installed. Run: pip install deepgram-sdk"
    except Exception as e:
        return f"[STT error] Transcription failed: {e}"
