"""
Parser for AUTO blocks in the self-knowledge doc.

An AUTO block looks like this::

    <!-- AUTO-START: capabilities -->
    ...generated markdown...
    <!-- AUTO-END: capabilities -->

The parser splits a document into an ordered list of segments — literal text
(hand-written, never touched) and AUTO blocks (owned by a named generator).
Round-trip is exact: ``serialize(parse(text)) == text`` byte for byte, including
mixed CRLF / LF line endings, because splitting happens only on the marker
comments and every other character is preserved verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Matches a full AUTO block. DOTALL so the body may span lines. The end marker's
# name is back-referenced so START/END must agree. Non-greedy body so adjacent
# blocks don't merge.
_BLOCK_RE = re.compile(
    r"<!-- AUTO-START: (?P<name>[\w-]+) -->"
    r"(?P<body>.*?)"
    r"<!-- AUTO-END: (?P=name) -->",
    re.DOTALL,
)


@dataclass
class Literal:
    text: str


@dataclass
class AutoBlock:
    name: str
    body: str  # raw text between the markers, including surrounding newlines


Segment = "Literal | AutoBlock"


def parse(text: str) -> list:
    """Split ``text`` into an ordered list of Literal and AutoBlock segments."""
    segments: list = []
    last = 0
    for m in _BLOCK_RE.finditer(text):
        if m.start() > last:
            segments.append(Literal(text[last:m.start()]))
        segments.append(AutoBlock(name=m.group("name"), body=m.group("body")))
        last = m.end()
    if last < len(text):
        segments.append(Literal(text[last:]))
    return segments


def serialize(segments: list) -> str:
    """Reconstruct the document text from segments (exact inverse of parse)."""
    out: list[str] = []
    for seg in segments:
        if isinstance(seg, Literal):
            out.append(seg.text)
        elif isinstance(seg, AutoBlock):
            out.append(f"<!-- AUTO-START: {seg.name} -->")
            out.append(seg.body)
            out.append(f"<!-- AUTO-END: {seg.name} -->")
    return "".join(out)


def block_names(text: str) -> list[str]:
    """Names of AUTO blocks present in the document, in order."""
    return [s.name for s in parse(text) if isinstance(s, AutoBlock)]


def _canonical_body(generated: str, newline: str) -> str:
    """Frame generated content as a block body: one blank line each side."""
    core = generated.strip("\r\n")
    return f"{newline}{core}{newline}"


def render(text: str, generators: dict) -> str:
    """
    Return ``text`` with each AUTO block's body replaced by its generator's
    output. Hand-written literal segments are preserved exactly. A block whose
    name has no generator is left untouched. Idempotent: rendering twice with the
    same deterministic generators yields identical output.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    segments = parse(text)
    for seg in segments:
        if isinstance(seg, AutoBlock) and seg.name in generators:
            generated = generators[seg.name]()
            seg.body = _canonical_body(generated, newline)
    return serialize(segments)
