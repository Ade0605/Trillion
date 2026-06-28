"""
Text-to-speech seam — ElevenLabs streaming TTS.
Swap this file to change voice providers without touching anything else.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.parent
_stop_event = threading.Event()


def _load_config() -> dict:
    with open(_ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def speak(text: str) -> None:
    """
    Stream text to speech via ElevenLabs and play it.
    Respects stop() calls — stops playback mid-stream if signalled.
    """
    _stop_event.clear()

    try:
        import elevenlabs
        import sounddevice as sd
        import numpy as np
    except ImportError as e:
        print(f"[TTS] Missing dependency: {e}. Install: pip install elevenlabs sounddevice numpy")
        return

    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        print("[TTS] ELEVENLABS_API_KEY not set in .env — speaking to console only.")
        print(f"Trillion: {text}")
        return

    cfg = _load_config()
    voice_id = cfg.get("elevenlabs_voice_id", "EXAVITQu4vr4xnSDxMaL")
    model_id = cfg.get("elevenlabs_model", "eleven_turbo_v2_5")

    try:
        client = elevenlabs.ElevenLabs(api_key=key)
        audio_stream = client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="pcm_22050",
        )

        sample_rate = 22050
        chunk_size = 4096

        with sd.RawOutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        ) as stream:
            for chunk in audio_stream:
                if _stop_event.is_set():
                    break
                if chunk:
                    stream.write(chunk)

    except Exception as e:
        print(f"[TTS] ElevenLabs error: {e}")
        print(f"Trillion: {text}")


def stop() -> None:
    """Signal playback to stop at the next chunk boundary."""
    _stop_event.set()
