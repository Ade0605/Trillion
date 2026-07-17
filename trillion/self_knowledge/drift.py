"""
Drift checker for the self-knowledge doc.

Scans the HAND-WRITTEN sections (never the AUTO blocks — those are generated and
can't drift) for two kinds of rot:

1. **Stale references** — file paths (e.g. `trillion/agent.py`, `config.yml`) and
   qualified symbols (e.g. `Agent.run_turn`) that no longer resolve, verified with
   AST parsing and static file reads (not grep — too noisy).
2. **Contradictions** — hand-written claims that the live code flatly disproves:
   a negative-existence claim ("no sub-agents exist", "is a single agent") made
   while the registry says otherwise, or a hard count ("three front doors") that
   disagrees with the live enumeration.

Both run in a pre-commit hook and in CI with --strict, so the bar is a *provable*
contradiction, never a stylistic quibble. Three rules keep the false-positive rate
near zero:

- If a live fact can't be read, no finding is raised — silence beats a bogus flag.
- Claims are matched per sentence, and a sentence carrying a reversal marker
  ("no longer a single agent") is a correction, not a claim.
- Counts are only checked for subjects with an unambiguous live enumeration.

References the author knows are fine (future tense, third-party examples) go in
the allowlist file, as does any matched claim phrase to silence deliberately.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import parser
from .render import DOC_PATH

_ROOT = Path(__file__).parent.parent.parent
_ALLOWLIST = _ROOT / "context" / "self" / ".trillion-allowlist.txt"
_WEB_SERVER = _ROOT / "web_server.py"

_BACKTICK = re.compile(r"`([^`]+)`")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$")
_FILE_EXT = re.compile(r"\.(py|md|ya?ml|json|txt|js|html|css|toml|cfg|ini|sh|env)$", re.I)
_SYMBOL = re.compile(r"^[A-Z][A-Za-z0-9]*(\.[A-Za-z_][A-Za-z0-9_]*)+$")
_BARE_CLASS = re.compile(r"^[A-Z][A-Za-z0-9]{2,}$")


@dataclass
class DriftFinding:
    kind: str            # "file" | "symbol" | "contradiction" | "count"
    reference: str
    location_in_doc: str  # section heading
    reason: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.reference!r} in “{self.location_in_doc}” — {self.reason}"


def load_allowlist() -> set[str]:
    if not _ALLOWLIST.exists():
        return set()
    out = set()
    for line in _ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.add(line)
    return out


def _symbol_index() -> tuple[set[str], dict[str, set[str]]]:
    """AST-walk the codebase: class names and their method names."""
    classes: set[str] = set()
    methods: dict[str, set[str]] = {}
    for py in _ROOT.rglob("*.py"):
        if "__pycache__" in py.parts or ".git" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
                m = methods.setdefault(node.name, set())
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m.add(child.name)
    return classes, methods


def _file_exists(token: str) -> bool:
    p = _ROOT / token
    if p.exists():
        return True
    # fall back to basename match anywhere in the tree
    base = Path(token).name
    for _ in _ROOT.rglob(base):
        return True
    return False


# --------------------------------------------------------------------------- #
# Live facts — the ground truth a hand-written claim can contradict.
#
# Every field is Optional, and None means "couldn't read it". Contradiction
# checks treat None as "stay quiet": a checker that can't see the truth must not
# accuse the prose of lying.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LiveFacts:
    tools: frozenset[str] | None = None            # live registry: authority for counts
    declared_tools: frozenset[str] | None = None   # names the source registers (static)
    page_routes: tuple[str, ...] | None = None     # HTML-serving GET routes
    factory_agents: tuple[str, ...] | None = None  # active spawned-agent slugs

    @classmethod
    def gather(cls) -> "LiveFacts":
        return cls(
            tools=_live_tool_names(),
            declared_tools=_declared_tool_names(),
            page_routes=_page_routes(),
            factory_agents=_active_factory_agents(),
        )


def _live_tool_names() -> frozenset[str] | None:
    """Names in the live registry — the same one the runtime builds."""
    try:
        from .generators import live_registry
        return frozenset(live_registry()._tools)
    except Exception:
        return None


def _declared_tool_names() -> frozenset[str] | None:
    """
    Tool names the source registers, found by AST — no imports required.

    ``build_registry`` assembles optional tools behind ``try/except: pass``, so a
    tool whose import fails is missing from the live registry with no error —
    the registry looks readable and is quietly short. That is precisely the
    "confidently blind" failure this checker exists to catch, so existence checks
    corroborate against what the code *says* it registers. Matches both call
    shapes in use: ``register("spawn_agent", ...)`` and ``register(name="x", ...)``.
    """
    names: set[str] = set()
    for py in _ROOT.rglob("*.py"):
        if "__pycache__" in py.parts or ".git" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute) and func.attr == "register"):
                continue
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str):
                names.add(node.args[0].value)
            for kw in node.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    names.add(kw.value.value)
    return frozenset(names) or None


def _active_factory_agents(path: Path | None = None) -> tuple[str, ...] | None:
    """
    Slugs of approved sub-agents, straight from the factory's own store.

    The doc itself says to verify the roster against this file rather than trust
    the prose, so the checker takes the same advice. Each active row is hot-
    registered at runtime as a `dispatch_to_<slug>` tool.
    """
    store = path or (_ROOT / "data" / "factory_agents.json")
    try:
        rows = json.loads(store.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(rows, list):
        return None
    return tuple(sorted(
        r["slug"] for r in rows
        if isinstance(r, dict) and r.get("status") == "active" and r.get("slug")
    ))


def _route_paths(decorator: ast.expr) -> list[str]:
    """Literal paths from an `@app.get(...)` / `@app.route(..., methods=[GET])`."""
    if not isinstance(decorator, ast.Call):
        return []
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr not in ("get", "route"):
        return []
    if not isinstance(func.value, ast.Name):
        return []
    if func.attr == "route":
        # Flask defaults to GET; an explicit methods= list must include it.
        for kw in decorator.keywords:
            if kw.arg == "methods":
                if not isinstance(kw.value, (ast.List, ast.Tuple)):
                    return []
                verbs = {e.value.upper() for e in kw.value.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                if "GET" not in verbs:
                    return []
    return [a.value for a in decorator.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)]


def _serves_html(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True if the handler body mentions an HTML content type."""
    return any(
        isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and n.value.lower().startswith("text/html")
        for n in ast.walk(func)
    )


def _page_routes(path: Path | None = None) -> tuple[str, ...] | None:
    """
    The app's "front doors": GET routes that serve HTML.

    Deliberately narrow — a front door is a page a human can open. JSON APIs
    (`/cosmos/agents`), static assets (`/sw.js`), and parameterised routes
    (`/design/<project>/preview/`) are not front doors, so the count matches what
    the prose means by the word. Returns None if the server can't be parsed.
    """
    src = path or _WEB_SERVER
    try:
        tree = ast.parse(src.read_text(encoding="utf-8"))
    except Exception:
        return None
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        paths = [p for dec in node.decorator_list for p in _route_paths(dec)]
        if not paths or not _serves_html(node):
            continue
        # A parameterised path is a family of URLs, not a door.
        found.update(p for p in paths if "<" not in p)
    return tuple(sorted(found))


# --------------------------------------------------------------------------- #
# Prose extraction: hand-written sentences, with their section heading.
# --------------------------------------------------------------------------- #

_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _prose_blocks(doc_text: str) -> list[tuple[str, str]]:
    """
    (section, paragraph) pairs from hand-written text only.

    The doc is hard-wrapped, so a claim routinely spans lines — lines are joined
    back into paragraphs before matching. Bullets are kept apart so one item's
    wording can't leak into its neighbour's. AUTO blocks and fenced code are
    dropped entirely.
    """
    blocks: list[tuple[str, str]] = []
    section = "(intro)"
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        if buf:
            blocks.append((section, " ".join(buf)))
            buf.clear()

    for seg in parser.parse(doc_text):
        if not isinstance(seg, parser.Literal):
            flush()  # a generated block interrupts the prose run
            continue
        for raw in seg.text.splitlines():
            line = raw.strip()
            if line.startswith("```"):
                flush()
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            heading = _HEADING.match(line)
            if heading:
                flush()
                section = heading.group(1).strip()
                continue
            if not line:
                flush()
                continue
            if _LIST_ITEM.match(raw):
                flush()
            buf.append(line)
        flush()
    return blocks


def _sentences(doc_text: str) -> list[tuple[str, str]]:
    """(section, sentence) pairs for every hand-written sentence."""
    out: list[tuple[str, str]] = []
    for section, block in _prose_blocks(doc_text):
        for sentence in _SENTENCE_SPLIT.split(block):
            sentence = sentence.strip()
            if sentence:
                out.append((section, sentence))
    return out


# --------------------------------------------------------------------------- #
# Claim patterns
# --------------------------------------------------------------------------- #

# A sentence that reverses itself is a correction, not a claim: "Trillion is no
# longer a single agent" asserts the opposite of "is a single agent". Without
# this guard, fixing the drift would trip the checker that caught it.
_REVERSAL = re.compile(
    r"\b(?:no\s+longer|not\s+anymore|used\s+to|previously|formerly"
    r"|once\s+(?:was|were)|historically|until\s+recently)\b",
    re.I,
)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_NUM = r"(?:\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"


def _to_int(token: str) -> int | None:
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBER_WORDS.get(token)


def _subagent_evidence(facts: LiveFacts) -> str | None:
    """
    Proof that specialists exist, or None if there is none.

    Corroborates three independent sources so a single unreadable one can't make
    the check quietly pass: the live registry, the registrations the source
    declares, and the factory's own store of approved agents.
    """
    proof = []
    registered = (facts.tools or frozenset()) | (facts.declared_tools or frozenset())
    if "spawn_agent" in registered:
        proof.append("`spawn_agent` is registered")
    dispatch = sorted(t for t in (facts.tools or ()) if t.startswith("dispatch_to_"))
    if dispatch:
        listed = ", ".join(f"`{d}`" for d in dispatch)
        proof.append(f"{len(dispatch)} dispatch tool(s) live: {listed}")
    if facts.factory_agents:
        listed = ", ".join(f"`{s}`" for s in facts.factory_agents)
        proof.append(f"{len(facts.factory_agents)} approved in the factory store: {listed}")
    return "; ".join(proof) or None


def _tools_exist_evidence(facts: LiveFacts) -> str | None:
    registered = (facts.tools or frozenset()) | (facts.declared_tools or frozenset())
    if not registered:
        return None
    return f"{len(registered)} tools are registered"


# (pattern, evidence) — a finding needs BOTH a match and live evidence against it.
_NEGATIVE_CLAIMS: list[tuple[re.Pattern, object]] = [
    (re.compile(r"\bno\s+(?:sub-?agents?|specialist\s+personas?|specialists?)\b", re.I),
     _subagent_evidence),
    (re.compile(r"\b(?:is|remains|stays|being)\s+a\s+single[-\s]agent\b", re.I),
     _subagent_evidence),
    (re.compile(r"\bcannot\s+(?:spawn|mint|create|register)\s+(?:new\s+)?"
                r"(?:sub-?agents?|specialists?|agents?|personas?)\b", re.I),
     _subagent_evidence),
    (re.compile(r"\bno\s+tools?\s+(?:are\s+)?(?:registered|available|wired)\b", re.I),
     _tools_exist_evidence),
]


def _front_door_count(facts: LiveFacts) -> tuple[int, str] | None:
    if facts.page_routes is None:
        return None
    listed = ", ".join(facts.page_routes)
    return len(facts.page_routes), f"web_server.py serves {len(facts.page_routes)}: {listed}"


def _tool_count(facts: LiveFacts) -> tuple[int, str] | None:
    if facts.tools is None:
        return None
    # A registry missing a tool its own source registers was assembled with a
    # failed optional import; it is short through no fault of the prose. Counting
    # against it would flag correct prose as drift, so it forfeits the authority.
    if facts.declared_tools and not facts.declared_tools <= facts.tools:
        return None
    return len(facts.tools), f"the registry holds {len(facts.tools)}"


# (pattern capturing the number, subject label, live counter). Only subjects with
# an unambiguous live enumeration belong here — a count the code can't settle is
# not drift, it's an opinion.
_COUNT_CLAIMS: list[tuple[re.Pattern, str, object]] = [
    (re.compile(rf"\b({_NUM})\s+(?:\w+[-\s]){{0,2}}front\s+doors?\b", re.I),
     "front doors", _front_door_count),
    (re.compile(rf"\b({_NUM})\s+(?:\w+[-\s]){{0,2}}entry\s+points?\b", re.I),
     "entry points", _front_door_count),
    # "N tools" alone is usually a subset ("the two tools that ask first"), so a
    # totality marker is required before the count is treated as a claim.
    (re.compile(rf"\b({_NUM})\s+tools?\s+(?:are\s+)?"
                rf"(?:registered|available|wired|in\s+the\s+registry|total)\b", re.I),
     "tools", _tool_count),
    (re.compile(rf"\b(?:has|have|carries|exposes)\s+({_NUM})\s+tools?\b", re.I),
     "tools", _tool_count),
]


def _contradictions(doc_text: str, facts: LiveFacts, allow: set[str]) -> list[DriftFinding]:
    """Hand-written claims the live code disproves."""
    findings: list[DriftFinding] = []
    allow_lower = {a.lower() for a in allow}
    seen: set[tuple] = set()

    def add(kind: str, ref: str, section: str, reason: str) -> None:
        key = (kind, ref.lower(), section)
        if ref.lower() in allow_lower or key in seen:
            return
        seen.add(key)
        findings.append(DriftFinding(kind, ref, section, reason))

    for section, sentence in _sentences(doc_text):
        if _REVERSAL.search(sentence):
            continue

        for pattern, evidence in _NEGATIVE_CLAIMS:
            match = pattern.search(sentence)
            if not match:
                continue
            proof = evidence(facts)
            if proof:
                add("contradiction", match.group(0), section,
                    f"prose denies this, but {proof}")

        for pattern, subject, counter in _COUNT_CLAIMS:
            for match in pattern.finditer(sentence):
                claimed = _to_int(match.group(1))
                live = counter(facts)
                if claimed is None or live is None:
                    continue
                actual, detail = live
                if claimed != actual:
                    add("count", match.group(0), section,
                        f"prose says {claimed} {subject}, but {detail}")
    return findings


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def check(doc_text: str | None = None, facts: LiveFacts | None = None) -> list[DriftFinding]:
    """
    Return drift findings for the hand-written sections.

    Covers stale references (paths/symbols that no longer resolve) and
    contradictions against ``facts`` — the live registry and route table, gathered
    from the running code unless injected for testing.
    """
    if doc_text is None:
        doc_text = DOC_PATH.read_text(encoding="utf-8")
    if facts is None:
        facts = LiveFacts.gather()
    allow = load_allowlist()
    classes, methods = _symbol_index()
    findings: list[DriftFinding] = []
    section = "(intro)"

    for seg in parser.parse(doc_text):
        if not isinstance(seg, parser.Literal):
            continue  # skip AUTO blocks — generated, can't drift
        for line in seg.text.splitlines():
            h = _HEADING.match(line.strip())
            if h:
                section = h.group(1).strip()
                continue
            for token in _BACKTICK.findall(line):
                token = token.strip()
                if not token or token in allow:
                    continue
                if _FILE_EXT.search(token) or ("/" in token and "." in token.rsplit("/", 1)[-1]):
                    if not _file_exists(token):
                        findings.append(DriftFinding("file", token, section, "path not found"))
                elif _SYMBOL.match(token):
                    cls, _, meth = token.partition(".")
                    if cls not in classes:
                        findings.append(DriftFinding("symbol", token, section, f"class '{cls}' not found"))
                    elif meth and meth not in methods.get(cls, set()):
                        findings.append(DriftFinding("symbol", token, section, f"'{cls}' has no '{meth}'"))

    findings.extend(_contradictions(doc_text, facts, allow))
    return findings
