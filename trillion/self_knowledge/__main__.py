"""
CLI for the self-knowledge doc.

    python -m trillion.self_knowledge --render    # print refreshed doc, write nothing
    python -m trillion.self_knowledge --refresh   # write refreshed doc to disk
    python -m trillion.self_knowledge --summary    # print the slim system-prompt summary
"""
from __future__ import annotations

import argparse
import sys

from .render import DOC_PATH, build_summary, refresh_text, write_refreshed


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252; keep output robust for any content.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(prog="trillion.self_knowledge")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--render", action="store_true",
                       help="print the refreshed doc without writing it")
    group.add_argument("--refresh", action="store_true",
                       help="regenerate the AUTO blocks and write to disk")
    group.add_argument("--summary", action="store_true",
                       help="print the slim summary injected into the system prompt")
    group.add_argument("--check", action="store_true",
                       help="scan hand-written sections for stale references (drift)")
    ap.add_argument("--strict", action="store_true",
                    help="with --check: exit non-zero if any drift is found (for CI)")
    args = ap.parse_args(argv)

    if args.render:
        sys.stdout.write(refresh_text())
        return 0

    if args.refresh:
        changed = write_refreshed()
        print(f"{'updated' if changed else 'no change'}: {DOC_PATH}")
        return 0

    if args.summary:
        print(build_summary())
        return 0

    if args.check:
        from .drift import check
        findings = check()
        if not findings:
            print("self-knowledge: no drift.")
            return 0
        print(f"self-knowledge: {len(findings)} drift finding(s):")
        for f in findings:
            print("  - " + str(f))
        return 1 if args.strict else 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
