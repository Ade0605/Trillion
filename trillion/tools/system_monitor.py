"""
System monitoring / screenshot tool.

Read-only reporting (CPU/memory/disk/uptime) needs no confirmation.
Screenshots capture whatever is currently on screen — potentially sensitive
content — so that one is gated behind confirmation like other tools that
touch things outside the agent's own data files.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

_SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "data" / "screenshots"


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def system_status() -> str:
    """Report CPU, memory, disk, and uptime."""
    try:
        import psutil
    except ImportError:
        return "System status requires the 'psutil' package (pip install psutil)."

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage(str(Path.home().anchor))
    uptime = timedelta(seconds=int(time.time() - psutil.boot_time()))

    return (
        f"CPU: {cpu:.0f}%\n"
        f"Memory: {_fmt_bytes(mem.used)} / {_fmt_bytes(mem.total)} ({mem.percent:.0f}%)\n"
        f"Disk ({Path.home().anchor}): {_fmt_bytes(disk.used)} / {_fmt_bytes(disk.total)} ({disk.percent:.0f}%)\n"
        f"Uptime: {uptime}"
    )


def take_screenshot() -> str:
    """Capture the full screen and save it. Returns the saved file path."""
    if sys.platform != "win32":
        return "Screenshot capture is only supported on Windows right now."
    try:
        from PIL import ImageGrab
    except ImportError:
        return "Screenshot capture requires the 'pillow' package (pip install pillow)."

    try:
        img = ImageGrab.grab()
    except OSError as e:
        return f"Couldn't capture the screen: {e}"

    _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = _SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    img.save(path)
    return f"Screenshot saved: {path}"


def register_system_monitor(registry) -> None:
    registry.register(
        name="system_status",
        description="Report current CPU, memory, disk usage, and system uptime.",
        input_schema={"type": "object", "properties": {}},
        fn=system_status,
    )
    registry.register(
        name="take_screenshot",
        description="Capture the current screen and save it to disk. Captures whatever is visible — asks for confirmation first.",
        input_schema={"type": "object", "properties": {}},
        fn=take_screenshot,
        requires_confirmation=True,
    )
