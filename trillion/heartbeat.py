"""
Heartbeat — background loop for proactive behaviour.
Runs checks on schedule, stores notices in data/notices.json.
Quiet hours are respected: non-urgent notices are held.
Kill switch: heartbeat.stop() / heartbeat.start().
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, time
from pathlib import Path
from typing import Callable

import yaml

_ROOT = Path(__file__).parent.parent
_SCHEDULE = _ROOT / "data" / "schedule.json"
_NOTICES = _ROOT / "data" / "notices.json"
_CONFIG = _ROOT / "config.yml"

# Callback to push a notice to the live UI (set by main.py if desired)
_surface_callback: Callable[[str], None] | None = None


def set_surface_callback(fn: Callable[[str], None]) -> None:
    global _surface_callback
    _surface_callback = fn


class Heartbeat:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running_checks: set[str] = set()
        self._lock = threading.Lock()
        _NOTICES.parent.mkdir(parents=True, exist_ok=True)
        if not _NOTICES.exists():
            _NOTICES.write_text("[]", encoding="utf-8")
        if not _SCHEDULE.exists():
            _SCHEDULE.write_text("{}", encoding="utf-8")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="trillion-heartbeat")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_event.is_set())

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self._tick()
            self._stop_event.wait(timeout=30)  # check every 30 seconds

    def _tick(self) -> None:
        # Kill switch halts proactive behavior too.
        try:
            from trillion.security import kill_switch
            if kill_switch.is_active():
                return
        except Exception:
            pass

        cfg = self._load_config()
        hb_cfg = cfg.get("heartbeat", {})
        if not hb_cfg.get("enabled", True):
            return

        checks_cfg = hb_cfg.get("checks", {})
        schedule = self._load_schedule()
        now = datetime.now()

        for check_name, check_cfg in checks_cfg.items():
            if not check_cfg.get("enabled", True):
                continue

            with self._lock:
                if check_name in self._running_checks:
                    continue  # skip — already running, don't stack

            interval = check_cfg.get("interval_seconds", 300)
            trigger_hour = check_cfg.get("trigger_hour")

            # Determine if this check is due
            last_run_str = schedule.get(check_name)
            last_run = datetime.fromisoformat(last_run_str) if last_run_str else None

            if trigger_hour is not None:
                # Once-a-day check at a specific hour
                target = now.replace(hour=int(trigger_hour), minute=0, second=0, microsecond=0)
                if last_run and last_run.date() == now.date():
                    continue  # already ran today
                if now < target:
                    continue  # not time yet today
            else:
                if last_run and (now - last_run).total_seconds() < interval:
                    continue  # not due yet

            # Run in a thread so the loop isn't blocked
            threading.Thread(
                target=self._run_check,
                args=(check_name, check_cfg, now),
                daemon=True,
            ).start()
            schedule[check_name] = now.isoformat()
            self._save_schedule(schedule)

    def _run_check(self, check_name: str, check_cfg: dict, ran_at: datetime) -> None:
        with self._lock:
            self._running_checks.add(check_name)
        try:
            fn = self._import_check(check_name)
            if fn is None:
                return
            notices = fn()
            if not notices:
                return
            priority = check_cfg.get("priority", "low")
            for notice in notices:
                self._store_notice(notice.get("message", ""), notice.get("priority", priority))
        finally:
            with self._lock:
                self._running_checks.discard(check_name)

    def _import_check(self, name: str):
        try:
            import importlib
            mod = importlib.import_module(f"trillion.checks.{name}")
            return mod.run
        except (ImportError, AttributeError):
            return None

    def _store_notice(self, message: str, priority: str) -> None:
        notices = json.loads(_NOTICES.read_text(encoding="utf-8"))
        entry = {
            "id": str(uuid.uuid4())[:8],
            "message": message,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "dismissed": False,
        }
        notices.append(entry)
        _NOTICES.write_text(json.dumps(notices, indent=2), encoding="utf-8")

        # Surface high-priority immediately if not in quiet hours
        if priority == "high" and not self._in_quiet_hours():
            if _surface_callback:
                _surface_callback(f"\n[Trillion] {message}\n")
            else:
                print(f"\n\n[Trillion - notice] {message}\nYou > ", end="", flush=True)

    def _in_quiet_hours(self) -> bool:
        cfg = self._load_config()
        qh = cfg.get("quiet_hours", {})
        if not qh.get("enabled", False):
            return False
        try:
            start = time.fromisoformat(qh["start"])
            end = time.fromisoformat(qh["end"])
            now = datetime.now().time()
            if start <= end:
                return start <= now <= end
            else:  # overnight window e.g. 22:00 – 07:00
                return now >= start or now <= end
        except Exception:
            return False

    def _load_config(self) -> dict:
        with open(_CONFIG) as f:
            return yaml.safe_load(f)

    def _load_schedule(self) -> dict:
        return json.loads(_SCHEDULE.read_text(encoding="utf-8"))

    def _save_schedule(self, schedule: dict) -> None:
        _SCHEDULE.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
