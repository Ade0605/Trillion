"""
widgets — what the MODEL writes: a type, an optional title, and that type's data
fields. The server validates it, forgives near-misses, and expands it into the
blocks the page draws, via a small recipe per type. The page only ever sees
blocks, so a widget's look can change here without touching the model's prompt.

Forgiving about near-misses with one obvious meaning (kpi → stat, a stat with a
title but no label uses the title as its label, a number sent as text is still a
number). Strict about anything whose meaning isn't plain: refuse with a message
naming exactly which field of which widget to fix.

The server, not the model, stamps WHEN: the model names the source app, the
server writes the time. Emoji are stripped from model text (data symbols like
arrows and check marks are kept).
"""
from __future__ import annotations

from . import caps
from .blocks import validate_block, validate_blocks, BlockError

# model type  ->  canonical widget type (near-miss forgiveness)
_ALIASES = {
    "kpi": "stat", "metric": "stat", "number": "stat", "figure": "stat",
    "schedule": "next-up", "calendar": "next-up", "agenda": "next-up",
    "nextup": "next-up", "next_up": "next-up", "upcoming": "next-up",
    "email": "inbox", "emails": "inbox", "mail": "inbox", "messages": "inbox",
    "task": "tasks", "todo": "tasks", "todos": "tasks", "to-do": "tasks",
    "opportunity": "opportunities", "opps": "opportunities", "opp": "opportunities",
    "deals": "pipeline", "deal": "pipeline", "pipe": "pipeline",
    "goal": "goal", "target": "goal", "objective": "goal",
    "risk": "risk-meter", "riskmeter": "risk-meter", "risk_meter": "risk-meter",
    "sectors": "sector",
    "competitive": "brief", "competition": "brief", "summary": "brief",
}

WIDGET_TYPES = (
    "stat", "brief", "next-up", "inbox", "tasks", "opportunities",
    "sector", "risk-meter", "pipeline", "goal", "custom",
)


class WidgetError(ValueError):
    """A widget whose meaning isn't plain. Message names the field to fix."""


# ── emoji stripping (keep data symbols) ───────────────────────────────────────
_KEEP_SYMBOLS = set("↑↓→←↗↘↕↔★☆✓✔✗✘☑☒•")


def strip_emoji(text: object) -> str:
    """Drop emoji from model text; keep arrows, stars and check marks."""
    out = []
    for ch in str(text or ""):
        if ch in _KEEP_SYMBOLS:
            out.append(ch)
            continue
        cp = ord(ch)
        if (0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF
                or 0x1F000 <= cp <= 0x1FAFF or cp in (0xFE0F, 0x200D)):
            continue
        out.append(ch)
    return "".join(out)


def _clean(text: object, limit: int) -> str:
    return caps.clip(strip_emoji(text), limit)


def _items(data: dict, where: str) -> list:
    for key in ("items", "events", "deals", "points"):
        if isinstance(data.get(key), list):
            return data[key]
    raise WidgetError(f"{where}: an items list is required")


# ── recipes: widget data -> list of raw blocks (validated after) ─────────────
def _r_stat(w: dict) -> list[dict]:
    d = w["data"]
    label = d.get("label") or w.get("title") or ""      # title falls back to label
    if d.get("value") in (None, ""):
        raise WidgetError("stat: value is required")
    blk = {"block": "value", "label": _clean(label, caps.LABEL),
           "value": _clean(d.get("value"), caps.VALUE)}
    if d.get("delta") not in (None, "") or d.get("change") not in (None, ""):
        blk["change"] = _clean(d.get("delta") or d.get("change"), caps.VALUE)
        blk["changeTone"] = d.get("tone") or d.get("deltaTone")
    if d.get("hint"):
        blk["hint"] = _clean(d.get("hint"), caps.LABEL)
    return [blk]


def _r_brief(w: dict) -> list[dict]:
    d = w["data"]
    blocks = []
    body = d.get("text") or d.get("summary") or d.get("insight")
    if body:
        blocks.append({"block": "text", "text": _clean(body, caps.TEXT)})
    pts = d.get("points") or d.get("items")
    if isinstance(pts, list) and pts:
        blocks.append({"block": "chips",
                       "items": [{"text": _clean(p, caps.LABEL)} for p in pts]})
    if not blocks:
        raise WidgetError("brief: text or points is required")
    return blocks


def _r_next_up(w: dict) -> list[dict]:
    items = _items(w["data"], "next-up")
    out = []
    for e in items:
        if not isinstance(e, dict):
            raise WidgetError("next-up: each event needs a title")
        out.append({"time": _clean(e.get("time") or e.get("when"), caps.LABEL),
                    "title": _clean(e.get("title") or e.get("name"), caps.TITLE),
                    "detail": _clean(e.get("detail") or e.get("where"), caps.TEXT) or None,
                    "tone": e.get("tone")})
    return [{"block": "timeline", "items": out}]


def _r_rows(w: dict, *, title_key, detail_key, meta_key) -> list[dict]:
    items = _items(w["data"], w["type"])
    out = []
    for it in items:
        if not isinstance(it, dict):
            raise WidgetError(f"{w['type']}: each item needs a {title_key}")
        title = it.get(title_key) or it.get("title") or it.get("name") or ""
        out.append({
            "title": _clean(title, caps.TITLE),
            "detail": _clean(it.get(detail_key) or it.get("detail"), caps.TEXT) or None,
            "meta": _clean(it.get(meta_key) or it.get("meta") or it.get("due"), caps.LABEL) or None,
            "tone": it.get("tone") or ("attention" if it.get("urgent") else None),
        })
    return [{"block": "rows", "items": out}]


def _r_inbox(w):  return _r_rows(w, title_key="subject", detail_key="from", meta_key="when")
def _r_tasks(w):  return _r_rows(w, title_key="title",   detail_key="detail", meta_key="due")
def _r_opps(w):   return _r_rows(w, title_key="title",   detail_key="detail", meta_key="meta")


def _r_sector(w: dict) -> list[dict]:
    d = w["data"]
    name = d.get("sector") or d.get("name") or w.get("title")
    if not name:
        raise WidgetError("sector: sector (name) is required")
    blocks = [{"block": "value", "label": "Sector", "value": _clean(name, caps.VALUE)}]
    if d.get("note") or d.get("text"):
        blocks.append({"block": "text", "text": _clean(d.get("note") or d.get("text"), caps.TEXT)})
    return blocks


def _r_meter(w: dict) -> list[dict]:
    d = w["data"]
    if d.get("value") in (None, ""):
        raise WidgetError(f"{w['type']}: value (0-100) is required")
    kind = "ring" if w["type"] == "goal" else "bar"
    return [{"block": "meter", "kind": d.get("kind", kind), "value": d.get("value"),
             "label": _clean(d.get("label") or w.get("title"), caps.LABEL) or None,
             "caption": _clean(d.get("caption"), caps.LABEL) or None,
             "tone": d.get("tone")}]


def _r_pipeline(w: dict) -> list[dict]:
    deals = _items(w["data"], "pipeline")
    rows = []
    for dd in deals:
        if not isinstance(dd, dict):
            raise WidgetError("pipeline: each deal needs a name, stage and value")
        rows.append([_clean(dd.get("name") or dd.get("title"), caps.VALUE),
                     _clean(dd.get("stage"), caps.VALUE),
                     _clean(dd.get("value") or dd.get("amount"), caps.VALUE)])
    return [{"block": "table", "columns": ["Deal", "Stage", "Value"], "rows": rows}]


def _r_custom(w: dict) -> list[dict]:
    """A custom card: the model supplies the blocks directly (used only when no
    ready widget fits). Validated by build_widget like any other blocks, so a
    custom card can't look or behave differently from the rest."""
    blocks = w["data"].get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise WidgetError("custom: blocks (a list of blocks) is required")
    return blocks


_RECIPES = {
    "stat": _r_stat, "brief": _r_brief, "next-up": _r_next_up, "inbox": _r_inbox,
    "tasks": _r_tasks, "opportunities": _r_opps, "sector": _r_sector,
    "risk-meter": _r_meter, "goal": _r_meter, "pipeline": _r_pipeline,
    "custom": _r_custom,
}

# one-line field hints for the tool description (Layer 3 reads these)
FIELD_HINTS = {
    "stat": "label, value, delta?, hint?, tone?",
    "brief": "text, points?[]",
    "next-up": "events[]: {time, title, detail?}",
    "inbox": "items[]: {subject, from?, when?}",
    "tasks": "items[]: {title, due?, done?, urgent?}",
    "opportunities": "items[]: {title, detail?, meta?}",
    "sector": "sector, note?",
    "risk-meter": "value(0-100), label?, caption?, tone?",
    "goal": "value(0-100), label?, caption?",
    "pipeline": "deals[]: {name, stage, value}",
    "custom": "blocks[]: a list of blocks — use ONLY when no widget above fits",
}


def _normalize_type(raw_type: object) -> str:
    t = str(raw_type or "").strip().lower().replace(" ", "")
    t = _ALIASES.get(t, t)
    # a chart kind given as the type means a chart stat-less card isn't ours yet;
    # keep the mapping table the single source of truth.
    if t not in WIDGET_TYPES:
        raise WidgetError(
            f"unknown widget type '{raw_type}' — must be one of {', '.join(WIDGET_TYPES)}")
    return t


def build_widget(raw: object, *, now: str = "just now") -> dict:
    """Validate one widget and expand it into blocks.

    Returns {type, title?, source?, updated, blocks:[...]}. The server stamps
    `updated`; the model only names `source`. Raises WidgetError / BlockError
    with a message naming the field to fix.
    """
    if not isinstance(raw, dict):
        raise WidgetError("a widget must be an object with a 'type'")
    wtype = _normalize_type(raw.get("type"))
    # data may be nested under "data" or flat alongside type/title — accept both.
    data = raw.get("data")
    if not isinstance(data, dict):
        data = {k: v for k, v in raw.items() if k not in ("type", "title", "source", "id", "asks")}
    widget = {"type": wtype, "data": data, "title": raw.get("title")}

    raw_blocks = _RECIPES[wtype](widget)
    raw_blocks = [b for b in raw_blocks if b is not None]
    try:
        blocks = validate_blocks(raw_blocks)
    except BlockError as e:
        raise WidgetError(f"{wtype}: {e}") from e

    out = {"type": wtype, "blocks": blocks, "updated": now}
    if raw.get("title"):
        out["title"] = _clean(raw.get("title"), caps.TITLE)
    if raw.get("source"):
        out["source"] = _clean(raw.get("source"), caps.LABEL)
    return out


def build_board(raw_widgets: object, *, now: str = "just now") -> list[dict]:
    """Validate + expand a list of widgets, capped at MAX_WIDGETS."""
    if not isinstance(raw_widgets, list):
        raise WidgetError("widgets must be a list")
    return [build_widget(w, now=now) for w in raw_widgets[: caps.MAX_WIDGETS]]
