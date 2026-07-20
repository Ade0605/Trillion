"""
Keep the Trillion web server alive.

Task Scheduler's minimum repetition is 1 minute, so a poll-only watchdog leaves
Trillion down for up to a minute. This supervisor owns the process instead and
relaunches within seconds of an exit, with a short backoff so a server that
cannot start (bad port, syntax error) doesn't spin the CPU.

Run by the "Trillion Server" scheduled task at logon; the task's 1-minute
repetition remains only as a backstop in case the supervisor itself dies.

    pythonw.exe scripts/serve_supervisor.py
"""
from __future__ import annotations

import datetime as _dt
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "logs" / "supervisor.log"
PORT = 7777

MIN_BACKOFF = 2.0     # seconds after a crash before relaunching
MAX_BACKOFF = 15.0    # cap: worst-case downtime for a genuine crash loop
HEALTHY_AFTER = 20.0  # a run lasting this long counts as healthy and resets the
                      # backoff — kept low so ordinary restarts stay ~2s rather
                      # than inheriting a doubled delay from an earlier blip


def log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{_dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")
    except Exception:
        pass


def port_busy(port: int = PORT) -> bool:
    """True when something already listens — another supervisor or a manual run."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> int:
    if port_busy():
        log("port already in use; another instance owns it — exiting")
        return 0

    python = Path(sys.executable)
    # pythonw has no console; use it so no window flashes on each relaunch.
    pyw = python.with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else python)

    backoff = MIN_BACKOFF
    log(f"supervisor start (exe={exe})")

    while True:
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                [exe, "web_server.py"],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            log(f"launch failed: {type(e).__name__}: {e}")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue

        code = proc.wait()
        ran = time.monotonic() - started
        log(f"server exited code={code} after {ran:.0f}s")

        if ran >= HEALTHY_AFTER:
            backoff = MIN_BACKOFF          # it was healthy; recover fast next time
        time.sleep(backoff)
        if ran < HEALTHY_AFTER:
            backoff = min(backoff * 2, MAX_BACKOFF)


if __name__ == "__main__":
    raise SystemExit(main())
