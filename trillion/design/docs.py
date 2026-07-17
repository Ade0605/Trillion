"""
docs — the three-document model for the head-of-design agent.

    design_workspace/<slug>/
      design.md                 PUBLIC, STABLE — the design system (+ token block)
      .prism/brief.md           PRIVATE, EVOLVING — strategic memory / standing rules
      .prism/references/<feat>/ reference screenshots
      .prism/preview/           gitignored Next.js app (Tier 2)
      features/<feature>.md     PUBLIC, RAPIDLY EVOLVING — per-feature spec
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
WORKSPACE_ROOT = _ROOT / "design_workspace"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def valid_slug(slug: str) -> bool:
    return bool(slug and SLUG_RE.match(slug))


def resolve_project_root(slug: str) -> Path:
    if not valid_slug(slug):
        raise ValueError(f"invalid project slug: {slug!r} (use kebab-case)")
    return WORKSPACE_ROOT / slug


def assert_within_project(project_root: Path, candidate: Path) -> Path:
    """Resolve candidate and guarantee it stays inside project_root (no traversal)."""
    root = project_root.resolve()
    p = (project_root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if root not in p.parents and p != root:
        raise ValueError(f"path escapes project: {candidate}")
    return p


def read_project_file(slug: str, rel: str) -> str | None:
    p = assert_within_project(resolve_project_root(slug), Path(rel))
    return p.read_text(encoding="utf-8") if p.exists() else None


def list_project_files(slug: str, subdir: str = "") -> list[str]:
    root = resolve_project_root(slug)
    base = assert_within_project(root, Path(subdir)) if subdir else root
    if not base.exists():
        return []
    return sorted(str(p.relative_to(root)) for p in base.rglob("*") if p.is_file())


def _write(slug: str, rel: str, text: str) -> Path:
    p = assert_within_project(resolve_project_root(slug), Path(rel))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def write_design_doc(slug: str, text: str) -> Path:
    return _write(slug, "design.md", text)


def write_brief(slug: str, text: str) -> Path:
    return _write(slug, ".prism/brief.md", text)


def write_feature_doc(slug: str, feature: str, text: str) -> Path:
    if not valid_slug(feature):
        raise ValueError(f"invalid feature slug: {feature!r}")
    return _write(slug, f"features/{feature}.md", text)


# --------------------------------------------------------------------------- #
# Templates — committed to CONCRETE defaults so the first dispatch has a real
# system to compose against (a TODO-shaped design.md yields skeleton mockups).
# --------------------------------------------------------------------------- #

DEFAULT_DESIGN_MD = """# Design System — {name}

Editorial, high-contrast, near-black canvas with a single warm accent. Big
display serif against clean sans body; mono for technical marginalia.

```yaml tokens
fonts:
  display: "Instrument Serif"
  body: "Inter"
  mono: "JetBrains Mono"
colors:
  background: "#0a0a0b"
  foreground: "#ededef"
  primary: "#e5a663"
  muted: "#17171a"
  border: "#26262a"
radius: "0.5rem"
shadcn:
  base_color: "neutral"
  style: "new-york"
```

## Type
- Display: Instrument Serif, 96–140px for heroes, tight tracking, tight leading.
- Body: Inter, 15–18px, generous line-height.
- Mono: JetBrains Mono for labels, readouts, marginalia (14–16px, UPPERCASE).

## Color
- One accent (`primary`, amber `#e5a663`) used precisely — text/hairlines/glow,
  never large decorative fills. The canvas is near-black; contrast carries it.

## Motion
- Multiple continuous animations at all times (drift, breathing, tickers) — a
  hero that looks static after 3 seconds has failed.
"""

DEFAULT_BRIEF_MD = """# Brief — {name}  (PRIVATE)

**Positioning.** A product that feels crafted, technical, and confident.

**Persona.** Discerning users who notice detail; allergic to template SaaS.

**Business goals.** Signal quality and taste at first glance; convert on trust.

**Brand language.** Editorial, high-contrast, restrained palette + one warm
accent, precise mono marginalia. Serious, not corporate.

## Standing design decisions (THE BRIEF IS LAW)
- Near-black canvas + a single warm accent. **Forbidden: violet/cyan "AI" gradients.**
- **Forbidden fonts:** Space Grotesk, Plus Jakarta Sans, Poppins, Montserrat.
- Motion is REQUIRED and continuous — commit to richness, never "subtle/near-invisible".
- Ambient background texture must be VISIBLE (opacity ≥ 0.4), not a whisper.
- Every hero shows a real product surface (waveform / readout / transcript), not
  just marketing copy.

## Ongoing themes
- Voice-first, low-latency, "quietly powerful".

## Bootstrap notes
- Generated with concrete defaults; iterate the tokens + standing decisions here.
"""

DEFAULT_FEATURE_MD = """# Feature — {title}

**What it is.** {title} for {name}.

**Primary screen.** {title} hero / main view.

**Must communicate.** (fill in the one thing this screen must land)

**Visual direction.** Follow design.md + the brief. Layered ambient texture,
massive display wordmark, at least one inline product surface, continuous motion,
mono marginalia in three places, one precise accent.
"""


def bootstrap_project(slug: str, name: str | None = None, scan_repo: str | None = None) -> dict:
    """Create starter design.md + brief.md (concrete defaults) on first dispatch.
    Optionally scans an associated repo for hints. Idempotent-ish: won't clobber
    an existing design.md."""
    root = resolve_project_root(slug)
    name = name or slug.replace("-", " ").title()
    created = []

    hints = []
    if scan_repo:
        rp = Path(scan_repo)
        if rp.exists():
            for probe in ("package.json", "README.md", "readme.md"):
                if (rp / probe).exists():
                    hints.append(probe)

    if not (root / "design.md").exists():
        write_design_doc(slug, DEFAULT_DESIGN_MD.format(name=name))
        created.append("design.md")
    if not (root / ".prism" / "brief.md").exists():
        write_brief(slug, DEFAULT_BRIEF_MD.format(name=name))
        created.append(".prism/brief.md")
    # ensure the private dirs exist
    (root / ".prism" / "references").mkdir(parents=True, exist_ok=True)
    (root / "features").mkdir(parents=True, exist_ok=True)

    return {"project": slug, "name": name, "created": created, "repo_hints": hints}
