"""
Spoken OmniRoute status report — health, tokens used, last model routed.

Run by the "Trillion OmniRoute Report" scheduled task at 18:00. The same content
is folded into the 09:00 morning brief, so this covers the evening half of the
"9am and 6pm" request.

User task, not the service: Session 0 cannot play audio to the desktop.

    python scripts/omniroute_report.py            # speak it
    python scripts/omniroute_report.py --dry-run  # print only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")


def build_report() -> str:
    try:
        from trillion.omniroute import status, summarise
        return summarise(status(), speakable=True)
    except Exception as e:
        return f"I couldn't read OmniRoute's status ({type(e).__name__})."


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(prog="omniroute_report")
    ap.add_argument("--dry-run", action="store_true", help="print, do not speak")
    args = ap.parse_args()

    text = build_report()
    print(text)
    if args.dry_run:
        return 0

    try:
        from trillion.voice.tts import speak
        speak(text)
    except Exception as e:
        print(f"[speak failed: {type(e).__name__}] {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
