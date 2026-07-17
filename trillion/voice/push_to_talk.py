"""
Push-to-talk capture loop.
Uses soundcard (WASAPI) for mic recording — no PortAudio dependency.
Hold the configured key to record, release to transcribe and respond.
"""
from __future__ import annotations

import io
import threading
import warnings
import wave
from pathlib import Path
from typing import Callable

import yaml

warnings.filterwarnings("ignore", category=RuntimeWarning, module="soundcard")

_ROOT = Path(__file__).parent.parent.parent


def _load_config() -> dict:
    with open(_ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def run_push_to_talk(
    on_transcript: Callable[[str], None],
    sample_rate: int = 16000,
) -> None:
    """
    Block and run the push-to-talk loop.
    on_transcript(text) is called after each recording is transcribed.
    """
    try:
        import soundcard as sc
        import numpy as np
        from pynput import keyboard as kb
    except ImportError as e:
        print(f"[PTT] Missing dependency: {e}")
        print("Install: pip install soundcard pynput numpy")
        return

    from . import stt, tts

    cfg = _load_config()
    ptt_key = cfg.get("push_to_talk_key", "space")
    key_obj = kb.Key.space if ptt_key == "space" else kb.KeyCode.from_char(ptt_key)

    recording = threading.Event()
    audio_frames: list[bytes] = []
    lock = threading.Lock()
    mic = sc.default_microphone()

    print(f"\n[Trillion Voice] Hold [{ptt_key.upper()}] to speak. Ctrl-C to quit.\n")

    def record_loop() -> None:
        """Continuously capture mic; only keep frames while recording flag is set."""
        blocksize = int(sample_rate * 0.05)  # 50ms blocks
        with mic.recorder(samplerate=sample_rate, channels=1, blocksize=blocksize) as rec:
            while True:
                data = rec.record(numframes=blocksize)
                if recording.is_set():
                    # Convert float32 → int16 PCM bytes
                    pcm = (data[:, 0] * 32767).astype("int16").tobytes()
                    with lock:
                        audio_frames.append(pcm)

    recorder_thread = threading.Thread(target=record_loop, daemon=True)
    recorder_thread.start()

    def on_press(key) -> None:
        if key == key_obj:
            tts.stop()
            with lock:
                audio_frames.clear()
            recording.set()
            print("[listening...]", end=" ", flush=True)

    def on_release(key) -> None:
        if key == key_obj:
            recording.clear()
            with lock:
                captured = b"".join(audio_frames)
                audio_frames.clear()

            if not captured:
                return

            wav_bytes = _to_wav(captured, sample_rate)
            print("[transcribing...]", flush=True)
            transcript = stt.transcribe(wav_bytes)

            if transcript.startswith("[STT error]"):
                print(transcript)
                return

            if not transcript.strip():
                print("[heard nothing — try again]")
                return

            print(f"[heard]: {transcript}")
            on_transcript(transcript)

    listener = kb.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    try:
        listener.join()
    except KeyboardInterrupt:
        listener.stop()


def _to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
