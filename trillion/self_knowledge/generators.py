"""
Introspecting generators for the AUTO blocks.

Each generator is a pure function: given a snapshot of the live objects (the tool
registry, the parsed config), it returns a markdown string. It reads from the
same registry the runtime uses — never a parallel hand-maintained list — so the
doc can't drift from reality.

If a generator can't reach its source (import error, missing file), it returns a
clearly-marked placeholder rather than raising, so a refresh never crashes.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.parent
_CONFIG_PATH = _ROOT / "config.yml"

_UNAVAILABLE = "_unavailable — source could not be read; regenerate manually_"


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

def load_config() -> dict:
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def live_registry():
    """Build the tool registry exactly as web_server / main do at runtime.

    The hosts finish with factory.tool.wire_live(); this mirrors only its
    load_active_agents half, so approved sub-agents show up as their
    `dispatch_to_<slug>` tools. wire_live() itself must NOT be called here: it
    also does live.set_registry(), which would repoint the live registry at this
    throwaway one, and a later approval would then hot-register its dispatch tool
    into a dead registry instead of the host's.
    """
    from trillion.tools.registry import build_registry
    from trillion.memory import MemoryStore, register_memory_tools

    registry = build_registry()
    register_memory_tools(registry, MemoryStore())
    try:
        from trillion.factory.runtime import load_active_agents
        load_active_agents(registry)
    except Exception:
        pass  # factory optional; never break the doc over it
    return registry


def _first_sentence(text: str) -> str:
    text = " ".join(text.split())
    for end in (". ", "! ", "? "):
        if end in text:
            return text[: text.index(end) + 1].strip()
    return text.strip()


# --------------------------------------------------------------------------- #
# Generators (pure: registry / config in, markdown out)
# --------------------------------------------------------------------------- #

def render_capabilities(registry) -> str:
    """A table of the tools currently registered, read from the live registry."""
    try:
        tools = list(registry._tools.values())
    except Exception:
        return _UNAVAILABLE
    if not tools:
        return "_No tools are registered._"

    rows = ["| Tool | What it does | Asks first |", "| --- | --- | --- |"]
    for t in sorted(tools, key=lambda t: t.name):
        desc = _first_sentence(t.description).replace("|", "\\|")
        gate = "yes" if getattr(t, "requires_confirmation", False) else "no"
        rows.append(f"| `{t.name}` | {desc} | {gate} |")
    rows.append("")
    rows.append(f"_{len(tools)} tools registered._")
    return "\n".join(rows)


def _key_present(env_key: str) -> bool:
    """True if the key is set in the environment or defined in the .env file.

    Local-only (reads a file); never makes a network call. This makes the doc
    accurate whether refreshed from the running server or the standalone CLI.
    """
    if os.environ.get(env_key):
        return True
    try:
        from dotenv import dotenv_values
        val = dotenv_values(_ROOT / ".env").get(env_key)
        return bool(val and val.strip())
    except Exception:
        return False


def render_integrations(config: dict) -> str:
    """External services Trillion talks to, with live 'configured?' status."""
    try:
        model = config.get("model", "unknown")
        voice_id = config.get("elevenlabs_voice_id", "unknown")
        voice_model = config.get("elevenlabs_model", "unknown")
    except Exception:
        return _UNAVAILABLE

    def configured(env_key: str) -> str:
        return "key present" if _key_present(env_key) else "no key"

    rows = [
        "| Service | Role | Configured |",
        "| --- | --- | --- |",
        f"| Anthropic (Claude) | The brain — model `{model}` | {configured('ANTHROPIC_API_KEY')} |",
        f"| Deepgram | Speech-to-text (native voice REPL) | {configured('DEEPGRAM_API_KEY')} |",
        f"| ElevenLabs | Text-to-speech — voice `{voice_id}`, model `{voice_model}` | {configured('ELEVENLABS_API_KEY')} |",
        f"| Yahoo Calendar | Read-only calendar over CalDAV | {configured('YAHOO_CALDAV_APP_PASSWORD')} |",
        "",
        "_Keys live in `.env`; the browser interface falls back to the browser's "
        "own speech synthesis when ElevenLabs is unavailable._",
    ]
    return "\n".join(rows)


def render_voice(config: dict) -> str:
    """Describe the real-time voice paths, derived from config + files present."""
    try:
        voice_id = config.get("elevenlabs_voice_id", "unknown")
        voice_dir = _ROOT / "trillion" / "voice"
        has_ptt = (voice_dir / "push_to_talk.py").exists()
    except Exception:
        return _UNAVAILABLE

    lines = [
        "Trillion has two voice paths, both sharing the one brain:",
        "",
        "- **Browser** (`localhost:7777`): microphone → Web Speech API (speech-to-"
        "text in the browser) → `Agent.run_turn` → replies streamed sentence-by-"
        f"sentence to ElevenLabs (voice `{voice_id}`) via the `/speak` route, with "
        "the browser's own speech synthesis as fallback.",
    ]
    if has_ptt:
        lines.append(
            "- **Native push-to-talk** (`main_voice.py`): hold a key → mic captured "
            "with `soundcard` → Deepgram speech-to-text → `Agent.run_turn` → "
            "ElevenLabs audio played through the speaker; a new key-press barges in."
        )
    lines.append("")
    lines.append(
        "_Trillion speaks by default. If asked whether it can talk, the answer is "
        "yes — the browser voice banner and the user's ears are the live source of "
        "truth, not Trillion's own guess._"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Block name -> zero-arg callable, closing over freshly-loaded live sources.
# --------------------------------------------------------------------------- #

def render_recent(days: int = 14, limit: int = 15) -> str:
    """Recent commit activity from `git log` — local, fast, no network."""
    import subprocess
    try:
        from trillion.security.subprocess_env import shell_minimal
        env = shell_minimal()
    except Exception:
        env = None
    try:
        out = subprocess.run(
            ["git", "-C", str(_ROOT), "log", f"--since={days}.days",
             "--date=short", "--pretty=format:%h|%ad|%s"],
            capture_output=True, text=True, timeout=5, env=env,
        )
        lines = [l for l in (out.stdout or "").strip().splitlines() if l][:limit]
    except Exception:
        return _UNAVAILABLE
    if not lines:
        return f"_No commits in the last {days} days._"
    rows = ["| Date | Commit | Change |", "| --- | --- | --- |"]
    for l in lines:
        parts = l.split("|", 2)
        if len(parts) == 3:
            h, d, s = parts
            rows.append(f"| {d} | `{h}` | {s.replace('|', chr(92) + '|')} |")
    return "\n".join(rows)


def default_generators() -> dict:
    """Map AUTO block names to generators bound to the current live sources."""
    generators: dict = {}

    def cap() -> str:
        try:
            reg = live_registry()
        except Exception:
            return _UNAVAILABLE
        return render_capabilities(reg)

    def integ() -> str:
        try:
            cfg = load_config()
        except Exception:
            return _UNAVAILABLE
        return render_integrations(cfg)

    def voice() -> str:
        try:
            cfg = load_config()
        except Exception:
            return _UNAVAILABLE
        return render_voice(cfg)

    generators["capabilities"] = cap
    generators["integrations"] = integ
    generators["voice"] = voice
    generators["recent"] = lambda: render_recent()
    return generators
