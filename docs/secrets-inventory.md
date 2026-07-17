# Trillion — Secrets Inventory

Every credential Trillion holds, its minimum required scope, and where it lives.
All live in `.env` (git-ignored). Reference by name, never by value.

| Secret | Purpose | Minimum scope | Rotate via |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | The brain (Claude) | Standard API key; no admin scopes needed | console.anthropic.com → API keys |
| `DEEPGRAM_API_KEY` | Speech-to-text (native voice REPL) | Usage/member key; not owner/admin | console.deepgram.com → API keys |
| `ELEVENLABS_API_KEY` | Text-to-speech | Key with **only** `text_to_speech` enabled | elevenlabs.io → profile → API keys |
| `TRILLION_TOKEN` | Bearer token for the web surface (only when exposed on 0.0.0.0) | n/a (self-generated random ≥24 chars) | edit `.env`, rotate with `TRILLION_TOKEN_PREV` overlap |
| `TRILLION_TOKEN_PREV` | Prior bearer token during a rotation window | n/a | clear once clients re-paired |

Notes:
- These are **service API keys**, not broadly-scoped platform tokens (no GitHub PAT,
  no cloud IAM, no payment keys), so the "fine-grained scope" pass in the hardening
  playbook mostly doesn't apply. Keep each key to the narrowest role its console offers.
- `TRILLION_KILL_SWITCH` is a control flag, not a secret.
- Revocation steps for a leak are in `docs/incident-runbook.md`.
