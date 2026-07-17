"""
Curated Google Fonts catalog — distinctive families first, across three roles.

Blocking the "generic AI SaaS" fonts at validation time is a deliberate quality
lever: those families instantly read as template-grade, so a design system that
picks one has already lost the award-quality bar.
"""
from __future__ import annotations

# Most distinctive first. All are real Google Font family names.
DISPLAY_FONTS = [
    "Instrument Serif", "Fraunces", "Bricolage Grotesque", "Unbounded",
    "Playfair Display", "DM Serif Display", "Syne", "Archivo Black",
]
BODY_FONTS = [
    "Inter", "Instrument Sans", "IBM Plex Sans", "Sora", "Manrope",
    "Work Sans", "Figtree", "Newsreader",
]
MONO_FONTS = [
    "JetBrains Mono", "IBM Plex Mono", "Space Mono", "Fira Code",
    "Martian Mono", "DM Mono",
]

ALL_FONTS = set(DISPLAY_FONTS) | set(BODY_FONTS) | set(MONO_FONTS)

# Fonts that signal template-grade AI SaaS. Rejected at validation.
FORBIDDEN_FAMILIES = {
    "Space Grotesk", "Plus Jakarta Sans", "Poppins", "Montserrat",
    "Nunito", "Raleway", "Lato", "Roboto", "Open Sans",
}


def is_forbidden(family: str) -> bool:
    return family.strip() in FORBIDDEN_FAMILIES


def is_known(family: str) -> bool:
    return family.strip() in ALL_FONTS
