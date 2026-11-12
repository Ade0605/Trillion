"""
packs — group widgets so a pack's widgets are only described to the model when
one of its apps is connected. A pack adds no drawing code: its widgets still
expand into the same blocks. Recomputing the active set when apps connect or
disconnect is just calling active_widget_types again and re-registering the
tool (no restart).
"""
from __future__ import annotations

from .widgets import WIDGET_TYPES

# Widgets always available — the user can dictate these without any integration.
CORE = ("stat", "brief", "next-up", "tasks", "goal", "sector", "risk-meter",
        "opportunities", "custom")

# pack name -> {widgets it adds, apps that switch it on}
PACKS = {
    "comms": {"widgets": ("inbox",),
              "apps": ("mail", "email", "gmail", "calendar", "outlook")},
    "crm":   {"widgets": ("pipeline",),
              "apps": ("crm", "stripe", "hubspot", "salesforce", "deals")},
}


def active_widget_types(connected) -> list[str]:
    """Core widgets plus any pack whose app is in `connected`, in canonical order.
    `connected` is a set/list of connected source or app names."""
    have = {str(s).strip().lower() for s in (connected or [])}
    active = set(CORE)
    for pack in PACKS.values():
        if have & {a.lower() for a in pack["apps"]}:
            active.update(pack["widgets"])
    return [t for t in WIDGET_TYPES if t in active]
