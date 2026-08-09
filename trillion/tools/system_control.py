"""
System / application control tool.

Threat: this is Trillion's first tool that can affect the OS outside its own
data files (previously only the CVE scanner spawned a subprocess, and that
was read-only). Scope is deliberately narrow: a fixed allowlist of known,
named applications — never an arbitrary path or shell command. Closing an
app is destructive (unsaved work can be lost) and always requires
confirmation; opening one is not and does not.

Windows-only for now (os.startfile / taskkill / LockWorkStation have no
cross-platform equivalent here). Calls return a clear message rather than
raising on unsupported platforms or unknown app names.
"""
from __future__ import annotations

import subprocess
import sys

from trillion.security import subprocess_env

# name -> (os.startfile target, taskkill /IM image name or None if not closeable)
# Explorer and Settings are excluded from closing: killing explorer.exe takes
# down the shell, and the Settings UWP process name isn't stable across builds.
_APPS: dict[str, tuple[str, str | None]] = {
    "notepad": ("notepad.exe", "notepad.exe"),
    "paint": ("mspaint.exe", "mspaint.exe"),
    "task manager": ("taskmgr.exe", "Taskmgr.exe"),
    "explorer": ("explorer.exe", None),
    "file explorer": ("explorer.exe", None),
    "settings": ("ms-settings:", None),
}


def _resolve(app: str) -> str | None:
    return (app or "").strip().lower() or None


def open_application(app: str) -> str:
    """Open a known application by name."""
    if sys.platform != "win32":
        return "System control is only supported on Windows right now."
    key = _resolve(app)
    entry = _APPS.get(key)
    if not entry:
        return (
            f"'{app}' isn't in the list of apps I can open. "
            f"I can open: {', '.join(sorted(_APPS))}."
        )
    target, _ = entry
    try:
        import os
        os.startfile(target)  # noqa: S606 - fixed allowlist above, not user-controlled
        return f"Opened {app}."
    except OSError as e:
        return f"Couldn't open {app}: {e}"


def close_application(app: str) -> str:
    """Close a known application by name. Destructive — unsaved work can be lost."""
    if sys.platform != "win32":
        return "System control is only supported on Windows right now."
    key = _resolve(app)
    entry = _APPS.get(key)
    if not entry:
        return (
            f"'{app}' isn't in the list of apps I can close. "
            f"I can close: {', '.join(sorted(k for k, v in _APPS.items() if v[1]))}."
        )
    _, process = entry
    if process is None:
        return f"{app} can't be closed this way (it's a system shell process, not a regular app)."
    try:
        result = subprocess.run(
            ["taskkill", "/IM", process, "/F"],
            env=subprocess_env.shell_minimal(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return f"Closed {app}."
        return f"{app} may not have been running: {result.stderr.strip() or result.stdout.strip()}"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"Couldn't close {app}: {e}"


def lock_screen() -> str:
    """Lock the Windows session immediately."""
    if sys.platform != "win32":
        return "Screen lock is only supported on Windows right now."
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "Screen locked."
    except OSError as e:
        return f"Couldn't lock the screen: {e}"


def register_system_control(registry) -> None:
    registry.register(
        name="open_application",
        description=(
            "Open a known application by name. Allowlisted apps only: "
            + ", ".join(sorted(_APPS)) + "."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Which app to open, e.g. 'notepad'"},
            },
            "required": ["app"],
        },
        fn=open_application,
    )
    registry.register(
        name="close_application",
        description=(
            "Force-close a known application by name. Destructive (unsaved work is lost) — "
            "always asks for confirmation first."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Which app to close, e.g. 'notepad'"},
            },
            "required": ["app"],
        },
        fn=close_application,
        requires_confirmation=True,
    )
    registry.register(
        name="lock_screen",
        description="Lock the computer screen immediately.",
        input_schema={"type": "object", "properties": {}},
        fn=lock_screen,
    )
