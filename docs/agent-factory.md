# Agent Factory (`spawn_agent`)

A meta-agent that mints other sub-agents on demand. Ask Trillion to *"spawn a
sub-agent that does X"* → it researches the role, drafts a system prompt + tool
allowlist, and stages it for your approval at `/factory`. On approval it becomes
a live `dispatch_to_<slug>` tool — **no restart**.

## Flow

```
spawn_agent (gated tool)  ──▶  pipeline (background thread)
                                 PENDING → RESEARCHING → DRAFTING_SPEC
                                 → WRITING_PROMPT → AWAITING_APPROVAL
                                                          │
                        you review at /factory ──────────┤
                                 approve → spawned_agents row + dispatch_to_<slug> (live)
                                 reject+feedback → regenerate prompt (cap 3) → back to review
                                 reject (no feedback) → REJECTED
```

Spawned agents are **pure config** — one `ConfigDrivenAgent` runtime reads the
row (system_prompt + model + tool_allowlist) and runs a vanilla tool-use loop.
No bespoke class per agent.

## Using it

Ask Trillion (it confirms first — research costs tokens):
> "Spawn a sub-agent that summarizes my notes into bullet points."

Then open **`/factory`** (or `…ts.net/factory?token=…` on your phone), review the
proposed system prompt + granted tools + wishlist, and **Approve** or **Reject**
(with optional feedback for a revision). Approved agents are immediately
dispatchable — Trillion gains a `dispatch_to_<slug>` tool with no restart.

## Storage (JSON, no DB)

- `data/factory_tasks.json` — in-flight spawn tasks (with state machine)
- `data/factory_agents.json` — registered agents
- `data/factory_reports.json` — cached research reports (24h dedup)
- `agent-specs/<slug>.md` — human-readable spec per agent

## Safety

- **Read-only allowlist:** spawned agents only get ungated read tools
  (`list_reminders`, `search_notes`, `read_note`, `list_notes`, `list_memories`).
  Anything else surfaces as a wishlist, never auto-granted.
- **Reserved slugs:** `trillion`, `scheduler`, `librarian`, `scribe`, `scout`, etc.
- **Daily cap:** 5 spawns/day, enforced at task creation.
- **Prompt-injection:** the `role_description` is sanitized (control chars,
  "ignore previous instructions", `system:` patterns rejected) and the prompt
  generator paraphrases — never quotes user input verbatim.
- **Approval gate is mandatory** — nothing goes live without your click.

Tests: `python -m unittest trillion.factory.tests_factory` (13).
Not built: avatar image gen, Postgres LISTEN/NOTIFY (in-process hot-reload used instead).
