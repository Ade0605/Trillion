"""
Wake-word capture loop — always-on listening, no key press required.
Uses openwakeword (local, no API key) for detection and soundcard (WASAPI)
for mic capture — same audio backend as push_to_talk, no pyaudio needed.

Says the wake word ("hey jarvis" by default) → records until a short pause
→ transcribes → hands off to on_transcript, exactly like push-to-talk does.
"""
from __future__ import annotations

import io
import threading
import time
import warnings
import wave
from pathlib import Path
from typing import Callable

import yaml

warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")

_ROOT = Path(__file__).parent.parent.parent
_CHUNK_SAMPLES = 1280  # openwakeword's recommended prediction chunk (80ms @ 16kHz)
_SILENCE_RMS = 300  # quiet room is well under this on int16 samples


def _load_config() -> dict:
    with open(_ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def rms(pcm_i16) -> float:
    """Root-mean-square of an int16 PCM sample array — a cheap loudness proxy."""
    import numpy as np
    if len(pcm_i16) == 0:
        return 0.0
    return float(np.sqrt(np.mean(pcm_i16.astype("float64") ** 2)))


def is_silent(pcm_i16, threshold: float = _SILENCE_RMS) -> bool:
    return rms(pcm_i16) < threshold


def run_wake_word(
    on_transcript: Callable[[str], None],
    sample_rate: int = 16000,
) -> None:
    """Block and run the always-on wake-word loop."""
    try:
        import soundcard as sc
        import numpy as np
        from openwakeword.model import Model
        from openwakeword.utils import download_models
    except ImportError as e:
        print(f"[WakeWord] Missing dependency: {e}")
        print("Install: pip install soundcard numpy openwakeword onnxruntime")
        return

    from . import stt, tts

    cfg = _load_config()
    ww_cfg = cfg.get("wake_word", {}) or {}
    model_name = ww_cfg.get("model", "hey_jarvis")
    threshold = float(ww_cfg.get("threshold", 0.5))
    silence_seconds = float(ww_cfg.get("silence_seconds", 1.0))
    max_utterance_seconds = float(ww_cfg.get("max_utterance_seconds", 15.0))
    cooldown_seconds = float(ww_cfg.get("cooldown_seconds", 1.5))

    try:
        download_models([model_name])
    except Exception as e:
        print(f"[WakeWord] Could not verify/download model '{model_name}': {e}")

    model = Model(wakeword_models=[model_name], inference_framework="onnx")
    mic = sc.default_microphone()

    print(f"\n[Trillion Voice] Listening for \"{model_name.replace('_', ' ')}\"… Ctrl-C to quit.\n")

    def capture_utterance(rec) -> bytes:
        """After a wake word fires, record until a pause or the max duration."""
        frames: list = []
        silence_chunks = 0
        needed_silence_chunks = max(1, int(silence_seconds / 0.08))
        max_chunks = max(1, int(max_utterance_seconds / 0.08))
        for _ in range(max_chunks):
            data = rec.record(numframes=_CHUNK_SAMPLES)
            pcm = (data[:, 0] * 32767).astype("int16")
            frames.append(pcm.tobytes())
            if is_silent(pcm):
                silence_chunks += 1
                if silence_chunks >= needed_silence_chunks and frames:
                    break
            else:
                silence_chunks = 0
        return b"".join(frames)

    stop = threading.Event()

    def listen_loop() -> None:
        with mic.recorder(samplerate=sample_rate, channels=1, blocksize=_CHUNK_SAMPLES) as rec:
            last_trigger = 0.0
            while not stop.is_set():
                data = rec.record(numframes=_CHUNK_SAMPLES)
                pcm = (data[:, 0] * 32767).astype("int16")
                prediction = model.predict(pcm)
                score = prediction.get(model_name, 0.0)

                now = time.monotonic()
                if score >= threshold and (now - last_trigger) >= cooldown_seconds:
                    last_trigger = now
                    tts.stop()
                    print("[wake word heard — listening...]", end=" ", flush=True)
                    model.reset()  # avoid re-triggering on the response we're about to speak
                    captured = capture_utterance(rec)
                    if not captured:
                        continue
                    wav_bytes = _to_wav(captured, sample_rate)
                    print("[transcribing...]", flush=True)
                    transcript = stt.transcribe(wav_bytes)
                    if transcript.startswith("[STT error]"):
                        print(transcript)
                        continue
                    if not transcript.strip():
                        print("[heard nothing — try again]")
                        continue
                    print(f"[heard]: {transcript}")
                    on_transcript(transcript)

    try:
        listen_loop()
    except KeyboardInterrupt:
        stop.set()


def _to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
