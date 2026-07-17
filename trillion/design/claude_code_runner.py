"""
claude_code_runner — spawn Claude Code as a subprocess for the composition step.

The planning agent (Trillion) stays cheap; the actual building shells out to the
`claude` CLI running in the project, with narrow Bash permissions and a sanitized
env (only ANTHROPIC_API_KEY + OS baseline — no other secrets leak into the child).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..security.subprocess_env import with_keys

# Narrow-but-functional tool allowlist for the composer.
DEFAULT_ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep",
    "Bash(npm install:*)", "Bash(npm run:*)",
    "Bash(npx shadcn:*)", "Bash(npx shadcn@latest:*)",
    "Bash(npx magicui-cli:*)",
    "Bash(ls:*)", "Bash(mkdir:*)", "Bash(cat:*)",
]


@dataclass
class ClaudeCodeResult:
    ok: bool
    return_code: int
    events: list = field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0


def _find_claude() -> str | None:
    for name in ("claude", "claude.cmd", "claude.exe"):
        p = shutil.which(name)
        if p:
            return p
    return None


def spawn_claude_code(
    prompt: str,
    cwd: str | Path,
    model: str = "claude-sonnet-4-6",
    max_turns: int = 40,
    allowed_tools: list[str] | None = None,
    on_event: Callable[[dict], None] | None = None,
    timeout_s: int = 900,
) -> ClaudeCodeResult:
    """Run `claude -p <prompt> --output-format stream-json ...`, drain NDJSON,
    forward each event via on_event, and return a structured result."""
    claude = _find_claude()
    if not claude:
        return ClaudeCodeResult(False, -1, error="claude CLI not found in PATH")

    cmd = [
        claude, "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--model", model, "--max-turns", str(max_turns),
        "--allowedTools", ",".join(allowed_tools or DEFAULT_ALLOWED_TOOLS),
    ]
    env = with_keys("ANTHROPIC_API_KEY")
    events: list[dict] = []
    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd), env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception as e:
        return ClaudeCodeResult(False, -1, error=f"failed to launch claude: {e}")

    try:
        for line in proc.stdout:           # NDJSON, one event per line
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(evt)
            if on_event:
                try:
                    on_event(evt)
                except Exception:
                    pass
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        return ClaudeCodeResult(False, -1, events=events,
                                error=f"claude timed out after {timeout_s}s",
                                duration_s=time.monotonic() - t0)
    except Exception as e:
        return ClaudeCodeResult(False, -1, events=events, error=str(e),
                                duration_s=time.monotonic() - t0)

    rc = proc.returncode or 0
    return ClaudeCodeResult(ok=(rc == 0), return_code=rc, events=events,
                            error=None if rc == 0 else f"claude exited {rc}",
                            duration_s=time.monotonic() - t0)
