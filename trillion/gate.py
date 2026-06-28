"""
Confirmation gate.
Sits between the model choosing a tool and the tool running.
Per-action — one confirmation never pre-authorizes the next.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_CONFIG = Path(__file__).parent.parent / "config.yml"


def requires_confirmation(tool_name: str) -> bool:
    with open(_CONFIG) as f:
        cfg = yaml.safe_load(f)
    gate_list = cfg.get("confirmation_required_tools", [])
    return tool_name in gate_list


def confirm(tool_name: str, inputs: dict) -> bool:
    """
    Print intent and wait for explicit y/n.
    Returns True only on 'y' — everything else is a no.
    """
    print(f"\n[Trillion] About to run '{tool_name}'")
    if inputs:
        for k, v in inputs.items():
            print(f"  {k}: {v}")
    resp = input("  Proceed? (y/n) > ").strip().lower()
    return resp == "y"
