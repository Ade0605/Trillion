"""
dossier — parse one advisor dossier (markdown) into a Seat, or reject it loudly.

A dossier is a KNOWLEDGE BASE, not a personality: numbered, sourced doctrine
entries the seat reasons FROM. The ids (D1, D2…) are what get cited, so they are
explicit in the file, never derived from ordering — reordering entries must
never silently invalidate citations on meetings already stored.

The parser must never take the board down: a malformed dossier loses its OWN
seat with a logged reason, never raises into the roster, and never vanishes
silently (a quorum that quietly shrinks is worse than a stale one).

File shape:

    ---
    id: hormozi
    name: Alex Hormozi
    seat: Offers & Sales
    domains: [pricing, offers, sales]
    status: active
    ---
    ## Doctrine
    ### D1 — Grand Slam Offer
    source: $100M Offers (2021), ch. 3
    verification: sourced
    <paragraph>
    ### D2 — …
    …
    ## Characteristic objection
    <text>
    ## Blind spots
    <text>
    ## Voice
    <text>
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import yaml

log = logging.getLogger("board_advisors")

VERIFICATION = ("sourced", "user", "retired")  # 'sourced' survived the fact-check;
DEFAULT_VERIFICATION = "user"                # 'retired' keeps its id spoken-for but
#                                              is withheld from meetings (see shown_ids)

_FRONTMATTER = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_ENTRY = re.compile(r"^###\s+(D\d+)\s*(?:[—:-]\s*(.*))?$", re.MULTILINE | re.IGNORECASE)


class DossierError(ValueError):
    """A dossier that cannot be a valid seat. Message is the logged reason."""


@dataclass(frozen=True)
class Doctrine:
    id: str              # "D1" (uppercase)
    title: str
    source: str
    verification: str    # 'sourced' | 'user'
    body: str


@dataclass(frozen=True)
class Seat:
    id: str
    name: str
    seat: str            # seat title (the domain where it has standing)
    domains: tuple[str, ...]
    status: str
    doctrine: tuple[Doctrine, ...]
    objection: str
    blind_spots: str
    voice: str

    @property
    def ids(self) -> set[str]:
        return {d.id for d in self.doctrine}

    def shown_ids(self) -> set[str]:
        """The ids a meeting may cite from this seat — active doctrine only.
        (Tier 6 retirement makes this diverge from `ids`.)"""
        return {d.id for d in self.doctrine if d.verification != "retired"}


def _sections(body: str) -> dict[str, str]:
    """Split the body into {lowercased heading: text} on '## ' headings."""
    out: dict[str, str] = {}
    marks = list(_SECTION.finditer(body))
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        out[m.group(1).strip().lower()] = body[start:end].strip()
    return out


def _parse_doctrine(text: str) -> list[Doctrine]:
    """Parse the '## Doctrine' section into entries, rejecting duplicate ids."""
    entries: list[Doctrine] = []
    seen: set[str] = set()
    marks = list(_ENTRY.finditer(text))
    for i, m in enumerate(marks):
        did = m.group(1).upper()
        if did in seen:
            # Anti-fabrication machinery that fails open is not machinery.
            raise DossierError(f"duplicate doctrine id {did}")
        seen.add(did)
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        block = text[start:end]
        source = _field(block, "source") or ""
        ver = (_field(block, "verification") or DEFAULT_VERIFICATION).strip().lower()
        if ver not in VERIFICATION:
            ver = DEFAULT_VERIFICATION
        body = _strip_fields(block, ("source", "verification")).strip()
        entries.append(Doctrine(id=did, title=(m.group(2) or "").strip(),
                                source=source.strip(), verification=ver, body=body))
    return entries


def _field(block: str, name: str) -> str | None:
    m = re.search(rf"^{name}\s*:\s*(.+?)\s*$", block, re.MULTILINE | re.IGNORECASE)
    return m.group(1) if m else None


def _strip_fields(block: str, names) -> str:
    for n in names:
        block = re.sub(rf"^{n}\s*:.*?$\n?", "", block, flags=re.MULTILINE | re.IGNORECASE)
    return block


def parse_dossier(text: str, *, slug: str = "?") -> Seat:
    """Parse a dossier string into a Seat, or raise DossierError with a reason."""
    text = (text or "").replace("\r\n", "\n")
    fm = _FRONTMATTER.search(text)
    if not fm:
        raise DossierError("no frontmatter block")
    try:
        meta = yaml.safe_load(fm.group(1)) or {}
    except Exception as e:
        raise DossierError(f"frontmatter is not valid YAML: {e}")

    domains = meta.get("domains") or []
    if isinstance(domains, str):
        domains = [d.strip() for d in re.split(r"[,\n]", domains) if d.strip()]
    domains = tuple(str(d).strip().lower() for d in domains if str(d).strip())
    if not domains:
        raise DossierError("no domains — the seat could never be routed to")

    sections = _sections(text[fm.end():])
    doctrine = tuple(_parse_doctrine(sections.get("doctrine", "")))
    if not doctrine:
        raise DossierError("no doctrine — there is nothing to cite")

    return Seat(
        id=str(meta.get("id") or slug).strip().lower(),
        name=str(meta.get("name") or slug).strip(),
        seat=str(meta.get("seat") or "").strip(),
        domains=domains,
        status=str(meta.get("status") or "active").strip().lower(),
        doctrine=doctrine,
        objection=sections.get("characteristic objection", sections.get("objection", "")).strip(),
        blind_spots=sections.get("blind spots", "").strip(),
        voice=sections.get("voice", "").strip(),
    )


def load_seat(text: str, *, slug: str) -> Seat | None:
    """Parse tolerantly: return the Seat, or None with a logged reason (never
    raises, so one bad file can't take out the roster)."""
    try:
        return parse_dossier(text, slug=slug)
    except DossierError as e:
        log.warning("dossier %s dropped: %s", slug, e)
        return None
    except Exception as e:                      # encoding, etc. — degrade, don't explode
        log.warning("dossier %s failed to parse: %s", slug, e)
        return None
