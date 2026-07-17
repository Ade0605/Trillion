"""
component_catalog — the curated palette Claude Code composes from.

Only libraries with working CLIs are cataloged (shadcn, MagicUI) plus Framer
Motion via npm. Aceternity/Reactbits are copy-paste-only and are deliberately
omitted: cataloging them without pre-bundling a snapshot makes CC try to install
them and fail.
"""
from __future__ import annotations

from dataclasses import dataclass

from .fonts import DISPLAY_FONTS, BODY_FONTS, MONO_FONTS, FORBIDDEN_FAMILIES


@dataclass
class CatalogEntry:
    name: str
    use_for: str
    install: str
    docs: str = ""


SHADCN_COMPONENTS = [
    CatalogEntry("button", "primary/secondary/ghost actions", "npx shadcn@latest add button"),
    CatalogEntry("card", "content containers, product panels", "npx shadcn@latest add card"),
    CatalogEntry("dialog", "modals", "npx shadcn@latest add dialog"),
    CatalogEntry("sheet", "side panels / drawers", "npx shadcn@latest add sheet"),
    CatalogEntry("tabs", "segmented views", "npx shadcn@latest add tabs"),
    CatalogEntry("input", "text fields", "npx shadcn@latest add input"),
    CatalogEntry("badge", "status pills, tags", "npx shadcn@latest add badge"),
    CatalogEntry("tooltip", "hover-reveal marginalia", "npx shadcn@latest add tooltip"),
    CatalogEntry("separator", "hairline dividers", "npx shadcn@latest add separator"),
    CatalogEntry("scroll-area", "scrollable readouts/transcripts", "npx shadcn@latest add scroll-area"),
    CatalogEntry("avatar", "identity chips", "npx shadcn@latest add avatar"),
]

MAGICUI_COMPONENTS = [
    CatalogEntry("grid-pattern", "ambient background grid (opacity >= 0.4)", "npx magicui-cli add grid-pattern"),
    CatalogEntry("dot-pattern", "ambient background dots", "npx magicui-cli add dot-pattern"),
    CatalogEntry("particles", "drifting particle field", "npx magicui-cli add particles"),
    CatalogEntry("border-beam", "animated beam around CTA/cards on hover", "npx magicui-cli add border-beam"),
    CatalogEntry("blur-fade", "staggered entrance for wordmark/blocks", "npx magicui-cli add blur-fade"),
    CatalogEntry("text-reveal", "scroll/enter text reveal", "npx magicui-cli add text-reveal"),
    CatalogEntry("number-ticker", "re-rolling numeric readouts", "npx magicui-cli add number-ticker"),
    CatalogEntry("marquee", "scrolling logo/label strips", "npx magicui-cli add marquee"),
    CatalogEntry("bento-grid", "feature bento layouts", "npx magicui-cli add bento-grid"),
    CatalogEntry("animated-list", "streaming list of events/messages", "npx magicui-cli add animated-list"),
    CatalogEntry("orbiting-circles", "orbiting nodes / constellation", "npx magicui-cli add orbiting-circles"),
    CatalogEntry("shimmer-button", "premium CTA", "npx magicui-cli add shimmer-button"),
]

FRAMER = CatalogEntry("framer-motion", "custom motion when libraries don't cover it", "npm install framer-motion")


def render_for_prompt() -> str:
    """Compact palette for the system/CC prompt."""
    def rows(entries):
        return "\n".join(f"  - {e.name} — {e.use_for}  [{e.install}]" for e in entries)
    return (
        "shadcn/ui (primitives):\n" + rows(SHADCN_COMPONENTS) + "\n\n" +
        "MagicUI (motion/ambient):\n" + rows(MAGICUI_COMPONENTS) + "\n\n" +
        f"Framer Motion: {FRAMER.install} — {FRAMER.use_for}\n"
    )


def render_full_catalog_markdown() -> str:
    """Verbose reference dropped into the preview app for CC to read on demand."""
    def table(title, entries):
        out = [f"## {title}", "", "| Component | Use for | Install |", "| --- | --- | --- |"]
        for e in entries:
            out.append(f"| `{e.name}` | {e.use_for} | `{e.install}` |")
        return "\n".join(out)
    fonts = (
        "## Fonts (curated Google Fonts)\n\n"
        f"- Display: {', '.join(DISPLAY_FONTS)}\n"
        f"- Body: {', '.join(BODY_FONTS)}\n"
        f"- Mono: {', '.join(MONO_FONTS)}\n\n"
        f"**FORBIDDEN (template-grade):** {', '.join(sorted(FORBIDDEN_FAMILIES))}\n"
    )
    return "\n\n".join([
        "# Component Catalog",
        "Compose from these. Only libraries listed here have working CLIs — do not "
        "reach for Aceternity/Reactbits (no CLI, not bundled).",
        table("shadcn/ui", SHADCN_COMPONENTS),
        table("MagicUI", MAGICUI_COMPONENTS),
        f"## Framer Motion\n\n`{FRAMER.install}` — {FRAMER.use_for}",
        fonts,
    ]) + "\n"
