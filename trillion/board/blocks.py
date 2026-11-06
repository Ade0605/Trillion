"""
blocks — the closed set of things the board page can draw, and a strict
validator for each. The page draws these and NOTHING else: every string is
drawn as text, so a block can never carry markup or code to the page.

Contract:
- `validate_block(raw)` returns a NEW, clean dict (never mutates the input) or
  raises `BlockError` with a message naming exactly what to fix.
- Length is forgiving (clip, never reject); structure is strict (a block whose
  meaning isn't plain is refused).
- Colour is never carried here — only tone WORDS. Links are kept only when http
  or https; anything else is dropped so the page can't be made to draw a
  dangerous href.

Block types: value, chart, table, rows, meter, timeline, person, chips, text,
quote, facts.
"""
from __future__ import annotations

from . import caps

BLOCK_TYPES = (
    "value", "chart", "table", "rows", "meter", "timeline",
    "person", "chips", "text", "quote", "facts",
)
CHART_KINDS = ("line", "bar", "area", "donut")
METER_KINDS = ("bar", "ring")


class BlockError(ValueError):
    """A block whose structure can't be drawn. Message names the fix."""


# ── small shared coercions ────────────────────────────────────────────────────
def _num(value: object, *, where: str) -> float:
    """Coerce int/float/numeric-string to float, or raise naming `where`."""
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        raise BlockError(f"{where}: expected a number, got a boolean")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            pass
    raise BlockError(f"{where}: expected a number, got {value!r}")


def _list(value: object, *, where: str) -> list:
    if not isinstance(value, list):
        raise BlockError(f"{where}: expected a list")
    return value


def _safe_link(value: object) -> str | None:
    """Keep a link only if it is http(s); otherwise drop it entirely."""
    s = str(value or "").strip()
    return s if s[:7].lower() in ("http://", "https:/") else None


# ── per-block validators ──────────────────────────────────────────────────────
def _value(b: dict) -> dict:
    if "value" not in b:
        raise BlockError("value: 'value' is required")
    out = {
        "block": "value",
        "label": caps.clip(b.get("label", ""), caps.LABEL),
        "value": caps.clip(b.get("value"), caps.VALUE),
    }
    if b.get("change") not in (None, ""):
        out["change"] = caps.clip(b.get("change"), caps.VALUE)
        out["changeTone"] = caps.tone_or_default(b.get("changeTone"))
    if b.get("hint") not in (None, ""):
        out["hint"] = caps.clip(b.get("hint"), caps.LABEL)
    return out


def _chart(b: dict) -> dict:
    kind = str(b.get("kind", "line")).strip().lower()
    if kind not in CHART_KINDS:
        raise BlockError(f"chart: kind must be one of {', '.join(CHART_KINDS)}")
    raw_series = _list(b.get("series"), where="chart: series")
    if not raw_series:
        raise BlockError("chart: series is required and cannot be empty")
    series = []
    for i, s in enumerate(raw_series[: caps.MAX_SERIES]):
        if not isinstance(s, dict):
            raise BlockError(f"chart: series[{i}] must be an object with points")
        points = _list(s.get("points"), where=f"chart: series[{i}].points")
        nums = [_num(p, where=f"chart: series[{i}].points[{j}]")
                for j, p in enumerate(points[: caps.MAX_POINTS])]
        if not nums:
            raise BlockError(f"chart: series[{i}].points cannot be empty")
        series.append({"name": caps.clip(s.get("name", ""), caps.LABEL), "points": nums})
    out = {"block": "chart", "kind": kind, "series": series}
    if b.get("labels"):
        labels = _list(b.get("labels"), where="chart: labels")
        out["labels"] = [caps.clip(x, caps.LABEL) for x in labels[: caps.MAX_POINTS]]
    return out


def _table(b: dict) -> dict:
    cols = _list(b.get("columns"), where="table: columns")
    if not cols:
        raise BlockError("table: columns is required")
    columns = [caps.clip(c, caps.LABEL) for c in cols]
    rows = []
    for r in _list(b.get("rows", []), where="table: rows")[: caps.MAX_ROWS]:
        cells = _list(r, where="table: each row")
        rows.append([caps.clip(c, caps.VALUE) for c in cells[: len(columns)]])
    return {"block": "table", "columns": columns, "rows": rows}


def _rows(b: dict) -> dict:
    items = []
    for r in _list(b.get("items", []), where="rows: items")[: caps.MAX_ROWS]:
        if not isinstance(r, dict):
            raise BlockError("rows: each item must be an object with a title")
        item = {"title": caps.clip(r.get("title", ""), caps.TITLE)}
        if r.get("detail") not in (None, ""):
            item["detail"] = caps.clip(r.get("detail"), caps.TEXT)
        if r.get("meta") not in (None, ""):
            item["meta"] = caps.clip(r.get("meta"), caps.LABEL)
        if r.get("tone"):
            item["tone"] = caps.tone_or_default(r.get("tone"))
        items.append(item)
    return {"block": "rows", "items": items}


def _meter(b: dict) -> dict:
    kind = str(b.get("kind", "bar")).strip().lower()
    if kind not in METER_KINDS:
        raise BlockError(f"meter: kind must be one of {', '.join(METER_KINDS)}")
    value = _num(b.get("value"), where="meter: value")
    value = max(0.0, min(100.0, value))        # a meter is a percentage
    out = {"block": "meter", "kind": kind, "value": value,
           "tone": caps.tone_or_default(b.get("tone"))}
    if b.get("label") not in (None, ""):
        out["label"] = caps.clip(b.get("label"), caps.LABEL)
    if b.get("caption") not in (None, ""):
        out["caption"] = caps.clip(b.get("caption"), caps.LABEL)
    return out


def _timeline(b: dict) -> dict:
    items = []
    for r in _list(b.get("items", []), where="timeline: items")[: caps.MAX_ROWS]:
        if not isinstance(r, dict):
            raise BlockError("timeline: each item needs a title")
        item = {
            "time": caps.clip(r.get("time", ""), caps.LABEL),
            "title": caps.clip(r.get("title", ""), caps.TITLE),
        }
        if r.get("detail") not in (None, ""):
            item["detail"] = caps.clip(r.get("detail"), caps.TEXT)
        if r.get("tone"):
            item["tone"] = caps.tone_or_default(r.get("tone"))
        items.append(item)
    return {"block": "timeline", "items": items}


def _person(b: dict) -> dict:
    name = caps.clip(b.get("name", ""), caps.LABEL)
    if not name:
        raise BlockError("person: name is required")
    out = {"block": "person", "name": name}
    if b.get("role") not in (None, ""):
        out["role"] = caps.clip(b.get("role"), caps.LABEL)
    if b.get("detail") not in (None, ""):
        out["detail"] = caps.clip(b.get("detail"), caps.TEXT)
    return out


def _chips(b: dict) -> dict:
    chips = []
    for c in _list(b.get("items", []), where="chips: items")[: caps.MAX_ROWS]:
        if isinstance(c, dict):
            text = caps.clip(c.get("text", ""), caps.LABEL)
            tone = caps.tone_or_default(c.get("tone"))
        else:
            text, tone = caps.clip(c, caps.LABEL), caps.DEFAULT_TONE
        if text:
            chips.append({"text": text, "tone": tone})
    return {"block": "chips", "items": chips}


def _text(b: dict) -> dict:
    s = caps.clip(b.get("text", ""), caps.TEXT)
    if not s:
        raise BlockError("text: text is required")
    out = {"block": "text", "text": s}
    link = _safe_link(b.get("link"))
    if link:
        out["link"] = link
    return out


def _quote(b: dict) -> dict:
    s = caps.clip(b.get("text", ""), caps.TEXT)
    if not s:
        raise BlockError("quote: text is required")
    out = {"block": "quote", "text": s}
    if b.get("cite") not in (None, ""):
        out["cite"] = caps.clip(b.get("cite"), caps.LABEL)
    return out


def _facts(b: dict) -> dict:
    items = []
    for r in _list(b.get("items", []), where="facts: items")[: caps.MAX_ROWS]:
        if not isinstance(r, dict) or "label" not in r:
            raise BlockError("facts: each item needs a label and a value")
        items.append({
            "label": caps.clip(r.get("label"), caps.LABEL),
            "value": caps.clip(r.get("value", ""), caps.VALUE),
        })
    return {"block": "facts", "items": items}


_VALIDATORS = {
    "value": _value, "chart": _chart, "table": _table, "rows": _rows,
    "meter": _meter, "timeline": _timeline, "person": _person, "chips": _chips,
    "text": _text, "quote": _quote, "facts": _facts,
}


def validate_block(raw: object) -> dict:
    """Validate one block and return a clean copy. Raises BlockError otherwise."""
    if not isinstance(raw, dict):
        raise BlockError("a block must be an object with a 'block' field")
    kind = str(raw.get("block", "")).strip().lower()
    if kind not in _VALIDATORS:
        raise BlockError(
            f"unknown block '{raw.get('block')}' — must be one of {', '.join(BLOCK_TYPES)}")
    return _VALIDATORS[kind](raw)


def validate_blocks(raw_blocks: object) -> list[dict]:
    """Validate a list of blocks (used by the 'custom' widget later)."""
    blocks = _list(raw_blocks, where="blocks")
    return [validate_block(b) for b in blocks]
