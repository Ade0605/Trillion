"""
tools — the three tools the model uses to drive the board: board_show,
board_update, board_remove. Schemas are deliberately FLAT (a list of widgets,
each just {type} plus the union of fields, no oneOf/anyOf/enum) because models
handle flat schemas far more reliably; the real checking is the validator. The
tool description stays under a character budget (test enforces it).
"""
from __future__ import annotations

from .widgets import FIELD_HINTS, WIDGET_TYPES, WidgetError
from .state import BoardStore

DESC_BUDGET = 12_000

# Union of every widget's data fields — loose on purpose; the recipe validates.
_WIDGET_ITEM = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "description": "widget type (see description)"},
        "title": {"type": "string"},
        "source": {"type": "string", "description": "app the data came from, e.g. Stripe"},
        "label": {"type": "string"}, "value": {}, "delta": {"type": "string"},
        "hint": {"type": "string"}, "tone": {"type": "string"},
        "text": {"type": "string"}, "points": {"type": "array"},
        "events": {"type": "array"}, "items": {"type": "array"},
        "deals": {"type": "array"}, "sector": {"type": "string"},
        "note": {"type": "string"}, "caption": {"type": "string"},
    },
    "required": ["type"],
}


def _types_doc() -> str:
    return "\n".join(f"- {t}: {FIELD_HINTS.get(t, '')}" for t in WIDGET_TYPES)


SHOW_DESCRIPTION = (
    "Show widgets on the visual board beside the conversation. Use when an answer "
    "is better seen than heard: a set of numbers, figures to compare, a plan, or "
    "more than three items. Then say ONE short line about it out loud — never "
    "read the board's contents aloud. Call a widget by what it shows, never by "
    "id. Never fill a card with invented data; if a source isn't connected, say "
    "so. Pass a list of widgets; each has a 'type' and that type's fields:\n"
    + _types_doc()
    + "\nAny widget may also carry title and source. Set replace=false to add to "
    "what's already shown instead of replacing it."
)


def register_board_tools(registry, store: BoardStore) -> None:
    def board_show(widgets, replace=True):
        try:
            shown = store.show(widgets, replace=bool(replace))
        except WidgetError as e:
            return f"Couldn't show that — {e}. Fix that field and try again."
        if not shown:
            return "Nothing to show."
        titles = ", ".join(w["title"] for w in shown)
        return f"On the board now: {titles}."

    def board_update(id, **fields):
        widget = fields.pop("widget", None) or fields
        try:
            res = store.update(id, widget)
        except WidgetError as e:
            return f"Couldn't update that — {e}."
        return f"Updated: {res['title']}." if res else f"No widget with id {id}."

    def board_remove(ids=None, id=None):
        target = ids if ids is not None else id
        removed = store.remove(target)
        return f"Removed {len(removed)} widget(s)." if removed else "Nothing matched."

    registry.register(name="board_show", description=SHOW_DESCRIPTION,
                      input_schema={"type": "object", "properties": {
                          "widgets": {"type": "array", "items": _WIDGET_ITEM},
                          "replace": {"type": "boolean"}},
                          "required": ["widgets"]},
                      fn=board_show)
    registry.register(name="board_update",
                      description="Change one widget on the board by its id. Pass the id and the widget's new fields.",
                      input_schema={"type": "object", "properties": dict(
                          {"id": {"type": "string"}}, **_WIDGET_ITEM["properties"]),
                          "required": ["id"]},
                      fn=board_update)
    registry.register(name="board_remove",
                      description="Remove one or more widgets from the board by id.",
                      input_schema={"type": "object", "properties": {
                          "ids": {"type": "array", "items": {"type": "string"}},
                          "id": {"type": "string"}}},
                      fn=board_remove)
