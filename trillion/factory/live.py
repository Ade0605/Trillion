"""Holds a reference to the host's live ToolRegistry so approval can hot-register
a new dispatch tool without a restart."""
from __future__ import annotations

_registry = None


def set_registry(reg) -> None:
    global _registry
    _registry = reg


def get_registry():
    return _registry
