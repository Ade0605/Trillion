"""
OmniRoute status — read-only.

OmniRoute is an LLM router installed globally via npm; its runtime state lives
in ~/.omniroute/storage.sqlite:

    version_manager   managed sub-tools (9router / mux / bifrost)
    usage_history     per-request token counts
    call_logs         per-request model, provider, HTTP status

The database is opened read-only (`mode=ro`) so a report can never disturb the
live router. WAL mode means reads succeed while OmniRoute is writing.

Nothing here needs OmniRoute's HTTP port: liveness comes from the process list,
which is what the user actually means by "is it up".
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

def _user_home() -> Path:
    """The human user's profile.

    Path.home() is wrong under the Windows service (LocalSystem resolves to
    C:\\Windows\\System32\\config\\systemprofile), which made OmniRoute look
    uninstalled: "the database is missing". Prefer the real profile, then the
    newest C:/Users/<name> that actually has a .omniroute directory.
    """
    for var in ("USERPROFILE", "HOME"):
        v = os.environ.get(var, "").strip()
        if v and (Path(v) / ".omniroute").exists():
            return Path(v)

    home = Path.home()
    if (home / ".omniroute").exists():
        return home

    users = Path(os.environ.get("SystemDrive", "C:") + "\\Users")
    if users.exists():
        found = []
        for d in users.iterdir():
            p = d / ".omniroute"
            try:
                if p.is_dir():
                    found.append((p.stat().st_mtime, d))
            except OSError:
                continue
        found.sort(reverse=True)
        if found:
            return found[0][1]
    return home


_env_home = os.environ.get("OMNIROUTE_HOME", "").strip()
OMNIROUTE_HOME = Path(_env_home) if _env_home else _user_home() / ".omniroute"
DB_PATH = OMNIROUTE_HOME / "storage.sqlite"
PKG_JSON = OMNIROUTE_HOME.parent / "AppData" / "Roaming" / "npm" / "node_modules" / "omniroute" / "package.json"


@dataclass
class Status:
    running: bool = False
    version: str = ""
    processes: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cache_read: int = 0
    requests: int = 0
    today_in: int = 0
    today_out: int = 0
    today_requests: int = 0
    last_model: str = ""
    last_provider: str = ""
    last_used: _dt.datetime | None = None
    failures: int = 0
    tools: list = field(default_factory=list)
    error: str = ""

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out

    def last_ago(self, now: _dt.datetime | None = None) -> str:
        if not self.last_used:
            return "never"
        now = now or _dt.datetime.now(_dt.timezone.utc)
        secs = max((now - self.last_used).total_seconds(), 0)
        if secs < 3600:
            m = int(secs // 60)
            return "just now" if m < 1 else f"{m} minute{'s' if m != 1 else ''} ago"
        if secs < 86400:
            h = int(secs // 3600)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        d = int(secs // 86400)
        return "yesterday" if d == 1 else f"{d} days ago"


def _is_running() -> tuple[bool, int]:
    """Count live OmniRoute node processes via PowerShell (psutil isn't installed)."""
    ps = (
        "(Get-CimInstance Win32_Process -Filter \"Name='node.exe'\" -ErrorAction SilentlyContinue "
        "| Where-Object { $_.CommandLine -match 'omniroute' } | Measure-Object).Count"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        n = int((out.stdout or "0").strip() or 0)
        return n > 0, n
    except Exception:
        return False, 0


def _version() -> str:
    try:
        return str(json.loads(PKG_JSON.read_text(encoding="utf-8")).get("version", "")).strip()
    except Exception:
        return ""


def _parse_ts(raw) -> _dt.datetime | None:
    if not raw:
        return None
    try:
        s = str(raw).replace("Z", "+00:00")
        d = _dt.datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    except Exception:
        return None


def status() -> Status:
    st = Status()
    st.running, st.processes = _is_running()
    st.version = _version()

    if not DB_PATH.exists():
        st.error = "OmniRoute database not found."
        return st

    try:
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        c = con.cursor()

        row = c.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(tokens_input),0) tin, "
            "COALESCE(SUM(tokens_output),0) tout, COALESCE(SUM(tokens_cache_read),0) tcr, "
            "COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) fails FROM usage_history"
        ).fetchone()
        st.requests, st.tokens_in, st.tokens_out = row["n"], row["tin"], row["tout"]
        st.tokens_cache_read, st.failures = row["tcr"], row["fails"]

        today = _dt.datetime.now().astimezone().strftime("%Y-%m-%d")
        row = c.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(tokens_input),0) tin, COALESCE(SUM(tokens_output),0) tout "
            "FROM usage_history WHERE substr(timestamp,1,10)=?", (today,)
        ).fetchone()
        st.today_requests, st.today_in, st.today_out = row["n"], row["tin"], row["tout"]

        row = c.execute(
            "SELECT timestamp, model, provider FROM call_logs ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            st.last_model = row["model"] or ""
            st.last_provider = row["provider"] or ""
            st.last_used = _parse_ts(row["timestamp"])

        st.tools = [
            {"tool": r["tool"], "status": r["status"], "health": r["health_status"]}
            for r in c.execute("SELECT tool,status,health_status FROM version_manager")
        ]
        con.close()
    except Exception as e:
        st.error = f"Couldn't read OmniRoute data ({type(e).__name__})."
    return st


def summarise(st: Status, speakable: bool = False) -> str:
    if st.error and not st.running:
        return f"OmniRoute: {st.error}"

    up = "running" if st.running else "not running"
    ver = f" v{st.version}" if st.version else ""

    if speakable:
        parts = [f"OmniRoute is {up}{ver}."]
        if st.last_model:
            who = f"{st.last_model} via {st.last_provider}" if st.last_provider else st.last_model
            parts.append(f"Last model used was {who}, {st.last_ago()}.")
        else:
            parts.append("No model calls recorded yet.")
        if st.today_requests:
            parts.append(
                f"Today: {st.today_requests} request{'s' if st.today_requests != 1 else ''}, "
                f"{st.today_in + st.today_out} tokens."
            )
        else:
            parts.append("No requests through it today.")
        parts.append(
            f"All time: {st.tokens_total} tokens across {st.requests} "
            f"request{'s' if st.requests != 1 else ''}."
        )
        return " ".join(parts)

    lines = [
        f"OmniRoute — {up}{ver}" + (f" ({st.processes} process(es))" if st.running else ""),
        f"  last model : {st.last_model or '(none)'}"
        + (f" via {st.last_provider}" if st.last_provider else "")
        + (f" · {st.last_ago()}" if st.last_used else ""),
        f"  today      : {st.today_requests} requests · {st.today_in + st.today_out} tokens "
        f"(in {st.today_in} / out {st.today_out})",
        f"  all time   : {st.requests} requests · {st.tokens_total} tokens "
        f"(in {st.tokens_in} / out {st.tokens_out} / cache-read {st.tokens_cache_read})",
    ]
    if st.failures:
        lines.append(f"  failures   : {st.failures}")
    if st.tools:
        bits = ", ".join(f"{t['tool']}={t['status']}" for t in st.tools)
        lines.append(f"  sub-tools  : {bits}")
    if st.error:
        lines.append(f"  note       : {st.error}")
    return "\n".join(lines)
