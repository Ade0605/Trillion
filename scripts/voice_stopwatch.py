"""
voice_stopwatch — an honest stopwatch for Trillion's spoken reply latency.

It plays a recorded question into the agent the way a microphone would (same
format, uploaded as one clip, which is how Trillion's record-then-transcribe
loop receives it) and times from the END of that audio to the FIRST byte of
spoken reply. It makes no sound and stores only numbers, never text.

    python scripts/voice_stopwatch.py            # 10 turns + 1 warm-up
    python scripts/voice_stopwatch.py --turns 5

Stages reported, all measured from "audio uploaded" (t0):
    stt     transcript final (Deepgram batch)
    model   first word from Claude
    seg     first speak_segment (first phrase handed to the voice)
    audio   first TTS byte (what you'd actually hear)

The client-side end-of-turn wait (phone VAD ~800ms) happens BEFORE upload and is
reported separately — it is not part of the server chain this times.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import time
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://127.0.0.1:7777"
QUESTION = "What is the tallest mountain in the world?"


def _load_env():
    for line in (ROOT / ".env").read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _config() -> dict:
    import yaml
    return yaml.safe_load((ROOT / "config.yml").read_text())


def make_question_wav(cfg: dict) -> bytes:
    """Synthesize the question once (ElevenLabs PCM) and wrap it as a 16kHz WAV
    Deepgram will accept. The clip is the microphone stand-in; it is never played."""
    from elevenlabs.client import ElevenLabs
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    pcm = b"".join(client.text_to_speech.convert(
        text=QUESTION,
        voice_id=cfg.get("elevenlabs_voice_id", "cgSgspJ2msm6clMCkdW9"),
        model_id=cfg.get("elevenlabs_model", "eleven_turbo_v2_5"),
        output_format="pcm_22050",
    ))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(pcm)
    return buf.getvalue()


def _post(path: str, data: bytes, ctype: str) -> tuple[int, bytes]:
    tok = os.environ.get("TRILLION_TOKEN", "")
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"Content-Type": ctype, "X-Auth-Token": tok,
                                          "Origin": BASE})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def _turn(wav: bytes) -> dict:
    """One timed turn. Returns stage times in ms from t0 (audio uploaded)."""
    tok = os.environ.get("TRILLION_TOKEN", "")
    t0 = time.perf_counter()
    # a/b: STT (batch) — the clip is uploaded; clock starts at upload (= end of speech)
    _, body = _post("/transcribe", wav, "audio/wav")
    text = (json.loads(body).get("text") or "").strip()
    t_stt = time.perf_counter() - t0
    # c/d: model first word + first speak_segment
    req = urllib.request.Request(BASE + "/chat",
                                 data=json.dumps({"message": text or QUESTION}).encode(),
                                 method="POST",
                                 headers={"Content-Type": "application/json",
                                          "X-Auth-Token": tok, "Origin": BASE})
    t_model = t_seg = None
    seg_turn = None
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw in resp:
            l = raw.decode("utf-8", "ignore").strip()
            if not l.startswith("data: "):
                continue
            p = l[6:]
            if p == "[DONE]":
                break
            try:
                o = json.loads(p)
            except Exception:
                continue
            now = time.perf_counter() - t0
            if "chunk" in o and t_model is None:
                t_model = now                 # first model word, measured from t0
            if o.get("type") == "speak_segment" and t_seg is None:
                t_seg = now
                seg_turn = o["turn_id"]
                break
    # e: first TTS byte
    t_audio = None
    if seg_turn:
        ta = time.perf_counter()
        areq = urllib.request.Request(
            BASE + f"/api/tts/{seg_turn}?token={tok}")
        with urllib.request.urlopen(areq, timeout=60) as ar:
            ar.read(1)
        t_audio = (t_seg or 0) + (time.perf_counter() - ta)
    return {"stt": t_stt * 1000,
            "model": (t_model or 0) * 1000,
            "seg": (t_seg or 0) * 1000,
            "audio": (t_audio or 0) * 1000}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=10)
    ap.add_argument("--gap", type=float, default=8.0)
    args = ap.parse_args()

    _load_env()
    cfg = _config()
    print("synthesizing question clip (once)…")
    wav = make_question_wav(cfg)

    print(f"model={cfg.get('model')}  tts={cfg.get('elevenlabs_model')}  "
          f"stt=deepgram nova-2  turns={args.turns} gap={args.gap}s\n")
    print("warm-up…")
    _turn(wav)

    rows = []
    for i in range(args.turns):
        time.sleep(args.gap)        # idle gap: lets connections go cold, like real pauses
        r = _turn(wav)
        rows.append(r)
        print(f"turn {i+1:2}: stt {r['stt']:5.0f}  model {r['model']:5.0f}  "
              f"seg {r['seg']:5.0f}  audio {r['audio']:5.0f} ms")

    def stat(key):
        xs = sorted(x[key] for x in rows)
        return statistics.median(xs), xs[int(len(xs) * 0.9)]

    print("\n--- from end of speech (upload) to first spoken byte ---")
    for key, label in [("stt", "transcript final"), ("model", "first model word"),
                       ("seg", "first phrase to voice"), ("audio", "first TTS byte (HEARD)")]:
        med, p90 = stat(key)
        print(f"  {label:24} median {med:5.0f} ms   p90 {p90:5.0f} ms")
    print("\n(client VAD end-of-turn wait ~800ms happens before upload — not counted here)")


if __name__ == "__main__":
    main()
