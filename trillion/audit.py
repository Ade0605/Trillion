"""
Audit log — append-only JSONL.
Records every tool run, confirmation, heartbeat surface, and error.
Also tracks running token cost so a runaway loop is immediately visible.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_LOG = Path(__file__).parent.parent / "logs" / "audit.log"

# Rough cost per token (update if you switch models)
_COST_PER_INPUT_TOKEN = 3.00 / 1_000_000   # $3 / M input tokens (Sonnet 4)
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000  # $15 / M output tokens (Sonnet 4)

_session_input_tokens = 0
_session_output_tokens = 0


def log(event_type: str, **kwargs) -> None:
    """Append one entry to the audit log, with secret shapes masked."""
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "event": event_type,
        **kwargs,
    }
    line = json.dumps(entry)
    # Mask any secret / high-precision shapes (keys, tokens, emails, cards, DSNs)
    # anywhere in the serialized entry before it touches disk.
    try:
        from trillion.security.log_redact import mask
        line = mask(line)
    except Exception:
        pass
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_tool(name: str, inputs: dict, result_summary: str, confirmed: bool | None = None) -> None:
    log("tool_run", tool=name, inputs=inputs, result=result_summary[:200], confirmed=confirmed)


def log_confirmation(tool_name: str, approved: bool) -> None:
    log("confirmation", tool=tool_name, approved=approved)


def log_tokens(input_tokens: int, output_tokens: int) -> None:
    global _session_input_tokens, _session_output_tokens
    _session_input_tokens += input_tokens
    _session_output_tokens += output_tokens
    cost = (
        _session_input_tokens * _COST_PER_INPUT_TOKEN
        + _session_output_tokens * _COST_PER_OUTPUT_TOKEN
    )
    log("tokens", input=input_tokens, output=output_tokens,
        session_total_input=_session_input_tokens,
        session_total_output=_session_output_tokens,
        session_cost_usd=round(cost, 6))


def log_notice(message: str, priority: str) -> None:
    log("heartbeat_notice", message=message, priority=priority)


def log_error(context: str, error: str) -> None:
    log("error", context=context, error=error)


def session_cost_summary() -> str:
    cost = (
        _session_input_tokens * _COST_PER_INPUT_TOKEN
        + _session_output_tokens * _COST_PER_OUTPUT_TOKEN
    )
    return (
        f"Session: {_session_input_tokens:,} input + {_session_output_tokens:,} output tokens "
        f"~${cost:.4f}"
    )
