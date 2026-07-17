# Trillion — Phone PWA Deploy

The voice-first PWA lives at **`/phone`**. It reuses Trillion's brain, tools,
Deepgram STT, and ElevenLabs TTS. It needs **HTTPS** (for `getUserMedia` + PWA
install) and a **bearer token** (because it's exposed beyond localhost).

## 1. Expose Trillion with a token

Set a long random token in `.env`, which flips the server from localhost-only to
`0.0.0.0` with the token required on every API call:

```
TRILLION_TOKEN=<paste a 32+ char random string>
```

Generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

Start Trillion: `python web_server.py` (it prints "auth: bearer token required").

## 2. Put HTTPS in front (pick one)

Trillion serves plain HTTP on :7777. A tunnel/proxy adds the TLS the phone needs.

### Cloudflare Tunnel (free, public URL)
```
cloudflared tunnel --url http://localhost:7777
```
Gives `https://<random>.trycloudflare.com`. Open on the phone:
`https://<random>.trycloudflare.com/phone?token=<TRILLION_TOKEN>`
(The `?token=` is consumed once and stored; the URL bar cleans itself up.)

### ngrok (free, needs an account authtoken)
```
ngrok http 7777
```
Then `https://<random>.ngrok-free.app/phone?token=<TRILLION_TOKEN>`.

### Tailscale (private, no public URL)
```
tailscale serve --bg http://localhost:7777
```
Reach it from any device on your tailnet at your machine's Tailscale HTTPS name,
`/phone?token=<TRILLION_TOKEN>`. Most private option.

## 3. Install on iOS

1. Open the `…/phone?token=…` URL in **Safari** (not Chrome — only Safari can install PWAs on iOS).
2. Tap the **Share** button → **Add to Home Screen**.
3. Launch from the home-screen icon. It opens full-screen (no browser chrome).
4. First tap of the orb triggers the mic-permission prompt — allow it.

## 4. Environment variables

| Var | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | the brain |
| `DEEPGRAM_API_KEY` | `/transcribe` speech-to-text |
| `ELEVENLABS_API_KEY` | `/api/tts/{turn_id}` speech |
| `TRILLION_TOKEN` | bearer token for the exposed surface |
| `TRILLION_TOKEN_PREV` | optional prior token during a rotation window |
| `TRILLION_KILL_SWITCH` | `true` halts all tools mid-incident |

## 5. How the loop works (and the iOS quirks it handles)

tap orb → record (MediaRecorder, `audio/mp4` on iOS) → client silence detection →
`POST /transcribe` (Deepgram) → `POST /chat` (SSE: text + tool chips + `turn_id`) →
`<audio src="/api/tts/{turn_id}?token=…">` plays the MP3.

Baked-in iOS Safari workarounds:
- **MP3 over the wire**, decoded natively by `<audio>` (no fragile WebAudio PCM).
- **Dual-path audio**: `<audio>` is audible; a *clone* of the bytes is decoded into
  a buffer source feeding the analyser (iOS `MediaElementSource`+analyser returns zeros).
- **Silent-switch**: audible audio goes through `<audio>`, which ignores the ringer switch.
- **play() priming**: a 46-byte silent WAV is `play()`ed synchronously in the tap
  handler, granting the element permanent activation so post-`await` `play()` works.
- **Non-evicting TTS**: `/api/tts/{turn_id}` is TTL-pruned, never evicted on read, so
  iOS's two GETs both succeed.
- **Token via `?token=`**: the only path `<audio>`/WS can authenticate.
- **`no-store` shell + pass-through service worker**: deploys are picked up on next open.
- **`100dvh` + `viewport-fit=cover`** and `renderer.setSize(w,h,false)` so the orb
  fills the screen under the home indicator without CSS fights.
- **`AudioContext.resume()`** on every tap (iOS suspends it on backgrounding).

## 6. Divergences from the reference architecture

- **HTTP/SSE, not WebSocket.** Trillion is Flask + SSE, so STT is one-shot
  (`/transcribe`) rather than streamed mic frames over `/ws`. Simpler, no new
  dependency, works on iOS. Trade-off: transcription starts after you stop talking.
- **Confirmation** reuses Trillion's existing gate: a `confirm` chip shows; you say
  "yes"/"no" in the next turn, or tap the orb to cancel. (No separate
  `await_confirmation` signal tool was needed.)
- **Persistence** is the shared in-memory conversation (same process as desktop);
  facts persist to `data/memory.json`. No DB.
