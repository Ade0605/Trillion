"""
Push-to-talk capture loop.
Hold the configured key to record, release to transcribe and respond.
If a new keypress arrives while TTS is playing, playback stops immediately.
"""
from __future__ import annotations

import io
import threading
import wave
from pathlib import Path
from typing import Callable

import yaml

_ROOT = Path(__file__).parent.parent.parent


def _load_config() -> dict:
    with open(_ROOT / "config.yml") as f:
        return yaml.safe_load(f)


def run_push_to_talk(
    on_transcript: Callable[[str], None],
    sample_rate: int = 16000,
    channels: int = 1,
) -> None:
    """
    Block and run the push-to-talk loop.

    on_transcript(text) is called with the transcribed text after each recording.
    The caller is responsible for running agent.run_turn and tts.speak.
    """
    try:
        import sounddevice as sd
        from pynput import keyboard as kb
    except ImportError as e:
        print(f"[PTT] Missing dependency: {e}")
        print("Install: pip install sounddevice pynput numpy")
        return

    from . import stt, tts

    cfg = _load_config()
    ptt_key = cfg.get("push_to_talk_key", "space")
    key_obj = kb.Key.space if ptt_key == "space" else kb.KeyCode.from_char(ptt_key)

    recording = threading.Event()
    audio_buffer: list[bytes] = []
    lock = threading.Lock()

    def audio_callback(indata, frames, time_info, status):
        if recording.is_set():
            with lock:
                audio_buffer.append(bytes(indata))

    print(f"\n[Trillion Voice] Hold [{ptt_key.upper()}] to speak. Ctrl-C to quit.\n")

    with sd.RawInputStream(
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        callback=audio_callback,
    ):
        def on_press(key):
            if key == key_obj:
                tts.stop()  # interrupt any ongoing playback
                with lock:
                    audio_buffer.clear()
                recording.set()
                print("[listening...]", end=" ", flush=True)

        def on_release(key):
            if key == key_obj:
                recording.clear()
                with lock:
                    captured = b"".join(audio_buffer)
                    audio_buffer.clear()

                if not captured:
                    return

                wav_bytes = _to_wav(captured, sample_rate, channels)
                print("[transcribing...]", flush=True)
                transcript = stt.transcribe(wav_bytes)

                if transcript.startswith("[STT error]"):
                    print(transcript)
                    return

                print(f"[heard]: {transcript}")
                on_transcript(transcript)

        listener = kb.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        try:
            listener.join()
        except KeyboardInterrupt:
            listener.stop()


def _to_wav(pcm_bytes: bytes, sample_rate: int, channels: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
