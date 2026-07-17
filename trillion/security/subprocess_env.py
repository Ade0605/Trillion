"""
Subprocess environment presets.

Threat: local FS / secret exfiltration and key compromise. A spawned process
inherits the full environment by default — including every API key. These
presets hand a subprocess only the OS baseline (or an explicit allowlist) so a
compromised or misbehaving child can't read ANTHROPIC_API_KEY et al.

Trillion has no spawn sites in its core loop; the only subprocess is the CVE
scanner (security/cve_scan), which uses shell_minimal().
"""
from __future__ import annotations

import os

# OS baseline keys a normal tool needs — never secrets.
_BASELINE = (
    "HOME", "PATH", "USER", "USERNAME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP",
    "SHELL", "PWD", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "PATHEXT", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "DISPLAY",
    # Windows home resolution (Path.home() needs these)
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
)


def shell_minimal() -> dict:
    """Only the OS baseline. No secrets. For git, ffmpeg, scanners, etc."""
    return {k: os.environ[k] for k in _BASELINE if k in os.environ}


def with_keys(*keys: str) -> dict:
    """shell_minimal() plus the named keys — for children that legitimately need
    a specific credential (e.g. spawning an LLM CLI)."""
    env = shell_minimal()
    for k in keys:
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def full(reason: str) -> dict:
    """Full inherited env. Requires a written justification at the callsite."""
    if not reason:
        raise ValueError("full() requires a reason justifying full env inheritance")
    return dict(os.environ)
