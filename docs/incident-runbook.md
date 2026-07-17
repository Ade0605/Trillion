# Trillion — Incident Runbook

The point of this file: during the first 30 minutes of a real incident you should
be taking actions from here, not searching docs.

## Universal first moves

```bash
# 1. Stop Trillion from making any more tool calls (takes effect next dispatch).
#    Set this in the same shell/.env the server reads, then it's live.
export TRILLION_KILL_SWITCH=true          # PowerShell: $env:TRILLION_KILL_SWITCH="true"

# 2. Capture forensic state.
copy logs\audit.log  %TEMP%\trillion-incident.log      # Windows
#   the audit log is already secret-redacted, so it's safe to share.
```

Then restart the server so the kill switch is loaded (or it applies on next tool
call if the env var is visible to the running process). The security shield 🛡 on
`/face` will show **red** while the kill switch is active.

---

## ANTHROPIC_API_KEY leaked

**Blast radius:** attacker can run Claude on your account and bill you; can read
anything you send as a prompt.

1. https://console.anthropic.com/settings/keys → revoke the key.
2. Create a new key; put it in `.env` as `ANTHROPIC_API_KEY=…`.
3. Restart Trillion.
4. Verify: send a chat turn; it should respond.
5. Check usage at the console. Unexpected spend = abuse window.

## DEEPGRAM_API_KEY leaked

**Blast radius:** attacker can transcribe audio on your account and bill you.

1. https://console.deepgram.com/ → API Keys → revoke.
2. New key → `.env` `DEEPGRAM_API_KEY=…`. Restart.
3. Verify: run `main_voice.py`, hold the key, speak — transcript appears.

## ELEVENLABS_API_KEY leaked

**Blast radius:** attacker can synthesize speech and burn your character quota.

1. https://elevenlabs.io → profile → API Keys → revoke.
2. New key (keep the `text_to_speech` permission on) → `.env`. Restart.
3. Verify: open `/face`, send a message, confirm the 🔊 banner is cyan and you hear it.
   (See the ElevenLabs voice notes: free tier = premade voices only.)

## TRILLION_TOKEN leaked (only relevant if you exposed Trillion on 0.0.0.0)

**Blast radius:** attacker on the network can drive Trillion and spend the API keys.

1. Rotate with overlap: copy current value to `TRILLION_TOKEN_PREV`, set a new
   `TRILLION_TOKEN`, restart. Re-pair the browser via `…/face?token=<new>`.
2. Once the browser works, clear `TRILLION_TOKEN_PREV` and restart.
   The old token now returns 401.
3. If you don't need remote access, unset `TRILLION_TOKEN` entirely → Trillion
   rebinds to localhost only.

---

## "Trillion is doing something I didn't ask for"

1. **Kill switch first:** `TRILLION_KILL_SWITCH=true` (see universal first moves).
2. Pause proactive behavior: in the REPL, `/heartbeat stop`.
3. Find the trigger: read the last day of `logs/audit.log` — every tool run,
   confirmation, anomaly block, and kill-switch block is there (secret-redacted).
   Look for an `anomaly_gate_blocked` or an unexpected `tool_run`.
4. If a web page or note injected instructions, the audit log's `tool_run` for
   `web_search` shows what came back; injected content is wrapped `<untrusted_*>`
   and should have been treated as data. If it wasn't, capture the snippet.
5. Resume when clear: `TRILLION_KILL_SWITCH=false`, restart, `/heartbeat start`.
