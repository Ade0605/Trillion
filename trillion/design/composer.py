"""
composer — the generate_mockup execute logic and the Claude Code prompt.

Validates inputs, parses design.md tokens (bails loudly if the system is half-
shaped), scaffolds if first dispatch, builds a heavily-opinionated ~5KB CC
prompt (brief-is-law + required visual elements + component palette + references)
and spawns Claude Code to compose one screen, then verifies the build produced
the expected static-export HTML.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import docs
from .design_tokens import parse_tokens, TokenError
from .scaffold import prepare_scaffold
from .component_catalog import render_for_prompt
from .claude_code_runner import spawn_claude_code, ClaudeCodeResult

_IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class MockupResult:
    ok: bool
    project: str
    feature: str
    screen: str
    screen_url: str | None = None
    out_html: str | None = None
    error: str | None = None
    cc_events: int = 0
    duration_s: float = 0.0
    warnings: list = field(default_factory=list)


def _validate_references(project_root: Path, feature: str, refs: list[str]) -> list[str]:
    """Return path-safe reference image paths that exist. Reject traversal."""
    ok = []
    ref_dir = project_root / ".prism" / "references" / feature
    for r in refs or []:
        if ".." in r or r.startswith("/") or r.startswith("\\"):
            continue
        if Path(r).suffix.lower() not in _IMG_EXT:
            continue
        p = (ref_dir / Path(r).name).resolve()
        if ref_dir.resolve() in p.parents and p.exists():
            ok.append(p.as_posix())
    return ok


# --------------------------------------------------------------------------- #
# THE CLAUDE CODE PROMPT
# --------------------------------------------------------------------------- #

def build_cc_prompt(*, project_root: Path, feature: str, screen: str,
                    description: str, visual_direction: str, quality: str,
                    first_dispatch: bool, reference_paths: list[str],
                    components_hint: list[str]) -> str:
    pr = project_root
    design_md = (pr / "design.md").as_posix()
    brief_md = (pr / ".prism" / "brief.md").as_posix()
    feature_md = (pr / "features" / f"{feature}.md").as_posix()
    out_html = (pr / ".prism" / "preview" / "out" / feature / screen / "index.html").as_posix()
    page_tsx = f"app/{feature}/{screen}/page.tsx"

    scaffold_steps = (
        "This is the FIRST dispatch for this project:\n"
        "  1. Run `npm install`.\n"
        "  2. Install the shadcn/MagicUI components you'll use (see palette).\n"
        if first_dispatch else
        "The scaffold already exists — SKIP `npm install`. Only `npx shadcn@latest add`"
        " / `npx magicui-cli add` the specific components this screen needs.\n"
    )

    refs_block = ""
    if reference_paths:
        listed = "\n".join(f"  - {p}" for p in reference_paths)
        refs_block = (
            "\n## Reference images — READ THESE FIRST with the Read tool\n"
            "You have vision; you will actually SEE them. Anchor every visual "
            "decision to these — they override category defaults.\n" + listed + "\n"
        )

    hint = f"\nComponents the planner suggests: {', '.join(components_hint)}\n" if components_hint else ""

    return f"""You are the head-of-design composer. Build ONE screen as a Next.js page in the
preview app at this directory (your cwd). Output must be award-quality — NOT
generic SaaS dark mode.

## Read first (use the Read tool)
- {design_md}   (the design system + ```yaml tokens block — obey the fonts/colors)
- {brief_md}    (standing decisions — see BRIEF IS LAW below)
- {feature_md}  (this feature's spec, if present)
{refs_block}
## THE BRIEF IS LAW
The brief encodes standing decisions incl. explicit forbidden moves. If this
task's wording conflicts with the brief, THE BRIEF WINS — do not silently
override it. Obey the forbidden colors/fonts/moves absolutely.

## Scaffold
{scaffold_steps}
## Component palette (only these have working CLIs)
{render_for_prompt()}{hint}
## Build this screen
Feature: {feature}   Screen: {screen}   Quality: {quality}
What it is: {description}

Visual direction (make ALL of this literally present, not paraphrased):
{visual_direction or "(follow the brief; layered ambient texture + product surface + continuous motion)"}

## Required visual elements (a screen missing ANY of these is incomplete)
1. Ambient background texture, VISIBLE (opacity >= 0.4) — grid-pattern / dot-pattern / particles (layering two is good).
2. An inline PRODUCT SURFACE composed in TSX (voice waveform / transcript with animated typing / status readout / command palette). A hero without one is incomplete.
3. Continuous motion — at least TWO things moving at all times (drift, breathing pulse, number ticker, oscillating waveform, blinking caret), not just on load.
4. Hover states on at least THREE elements (not only the CTA).
5. Three+ mono marginalia annotations, sized 14–16px (not 11px), UPPERCASE.
6. A massive display wordmark (96–140px) with tuned tracking/leading. One accent color used precisely — no decorative fills.

Rule of thumb: if someone looking for 3 seconds can't tell anything is animated, the page FAILED.

## Output + build (REQUIRED)
- Write the page at: {page_tsx}
- Then run `npm run build`. It must succeed (fix errors and rebuild until it does).
- Success = this file exists: {out_html}

Do not stop until the build succeeds and that file exists.
"""


def generate_mockup(
    *, feature_slug: str, screen_name: str, description: str,
    visual_direction: str = "", quality: str = "standard",
    reference_images: list[str] | None = None,
    components_hint: list[str] | None = None,
    project: str = "trillion-voice",
    model: str = "claude-sonnet-4-6",
    on_event: Callable[[dict], None] | None = None,
    _runner=spawn_claude_code,
) -> MockupResult:
    """Compose a single screen. `_runner` is injectable for tests."""
    if not docs.valid_slug(feature_slug):
        return MockupResult(False, project, feature_slug, screen_name, error="invalid feature slug")
    if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", screen_name):
        return MockupResult(False, project, feature_slug, screen_name, error="invalid screen name")
    if quality not in ("standard", "premium"):
        quality = "standard"

    project_root = docs.resolve_project_root(project)
    warnings: list[str] = []

    # first dispatch? bootstrap the docs
    first = not (project_root / ".prism" / "preview" / "package.json").exists()
    if not (project_root / "design.md").exists():
        docs.bootstrap_project(project)

    # parse tokens — bail loudly on a half-shaped system
    try:
        tokens = parse_tokens(docs.read_project_file(project, "design.md") or "")
        warnings.extend(tokens.warnings)
    except TokenError as e:
        return MockupResult(False, project, feature_slug, screen_name,
                            error=f"design.md tokens invalid: {e}")

    scaffold_info = prepare_scaffold(project_root, tokens, project)
    refs = _validate_references(project_root, feature_slug, reference_images or [])

    prompt = build_cc_prompt(
        project_root=project_root, feature=feature_slug, screen=screen_name,
        description=description, visual_direction=visual_direction, quality=quality,
        first_dispatch=first, reference_paths=refs, components_hint=components_hint or [],
    )

    preview = project_root / ".prism" / "preview"
    result: ClaudeCodeResult = _runner(prompt, cwd=preview, model=model, on_event=on_event)

    out_html = preview / "out" / feature_slug / screen_name / "index.html"
    built = out_html.exists()
    base = scaffold_info["base_path"]
    screen_url = f"{base}/{feature_slug}/{screen_name}/" if built else None

    ok = result.ok and built
    err = None if ok else (result.error or ("build produced no output HTML" if not built else "unknown"))
    return MockupResult(
        ok=ok, project=project, feature=feature_slug, screen=screen_name,
        screen_url=screen_url, out_html=out_html.as_posix() if built else None,
        error=err, cc_events=len(result.events), duration_s=result.duration_s,
        warnings=warnings,
    )
