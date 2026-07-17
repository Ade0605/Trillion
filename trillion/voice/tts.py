"""
Text-to-speech seam — ElevenLabs streaming TTS.
Uses soundcard (WASAPI) for playback — no PortAudio dependency.
"""
from __future__ import annotations

import io
import os
import threading
import wave
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.parent
_stop_event = threading.Event()


def _load_config() -> dict:
    with open(_ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def speak(text: str) -> None:
    """Stream text to speech via ElevenLabs and play through default speaker."""
    _stop_event.clear()

    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        print(f"Trillion: {text}")
        return

    try:
        import elevenlabs
    except ImportError:
        print(f"[TTS] elevenlabs not installed. Trillion: {text}")
        return

    cfg = _load_config()
    voice_id = cfg.get("elevenlabs_voice_id", "EXAVITQu4vr4xnSDxMaL")
    model_id = cfg.get("elevenlabs_model", "eleven_turbo_v2_5")

    try:
        import soundcard as sc
        import numpy as np

        client = elevenlabs.ElevenLabs(api_key=key)

        # Collect streamed PCM bytes
        audio_chunks: list[bytes] = []
        for chunk in client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format="pcm_22050",
        ):
            if _stop_event.is_set():
                return
            if chunk:
                audio_chunks.append(chunk)

        if not audio_chunks or _stop_event.is_set():
            return

        raw = b"".join(audio_chunks)
        # PCM int16 → float32 normalised to [-1, 1]
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        speaker = sc.default_speaker()
        with speaker.player(samplerate=22050, channels=1) as p:
            chunk_size = 2205  # ~100ms chunks so stop() is responsive
            for i in range(0, len(samples), chunk_size):
                if _stop_event.is_set():
                    break
                p.play(samples[i:i + chunk_size].reshape(-1, 1))

    except Exception as e:
        print(f"[TTS] Error: {e}")
        print(f"Trillion: {text}")


def stop() -> None:
    """Signal playback to stop at the next chunk boundary."""
    _stop_event.set()
