"""
design_tokens — parse and validate the structured token block in design.md, and
render the Tailwind config + globals.css that the preview app compiles against.

The token block is a fenced ```yaml tokens code block inside design.md, so the
same file is both machine-parseable and human-readable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

from .fonts import ALL_FONTS, FORBIDDEN_FAMILIES

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_SHADCN_BASE = {"neutral", "gray", "zinc", "stone", "slate"}
_SHADCN_STYLE = {"new-york", "default"}
_TOKENS_BLOCK = re.compile(r"```yaml\s+tokens\s*\n(.*?)\n```", re.DOTALL)

# CSS variable name -> which token color feeds it (shadcn light/dark share here).
_COLOR_VARS = ["background", "foreground", "primary", "muted", "border"]


class TokenError(ValueError):
    """Raised when design.md's token block is missing or invalid."""


@dataclass
class DesignTokens:
    fonts: dict          # {display, body, mono}
    colors: dict         # {background, foreground, primary, muted, border}
    radius: str
    shadcn_base_color: str
    shadcn_style: str
    warnings: list = field(default_factory=list)


def parse_tokens(design_md_text: str) -> DesignTokens:
    """Extract and validate the ```yaml tokens block. Raises TokenError loudly if
    it's missing or malformed — never compose against a half-shaped system."""
    m = _TOKENS_BLOCK.search(design_md_text or "")
    if not m:
        raise TokenError("design.md has no ```yaml tokens block.")
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise TokenError(f"tokens block is not valid YAML: {e}")

    fonts = data.get("fonts") or {}
    colors = data.get("colors") or {}
    shadcn = data.get("shadcn") or {}
    warnings: list[str] = []

    for role in ("display", "body", "mono"):
        fam = (fonts.get(role) or "").strip()
        if not fam:
            raise TokenError(f"fonts.{role} is required.")
        if fam in FORBIDDEN_FAMILIES:
            raise TokenError(f"fonts.{role} = '{fam}' is a forbidden (template-grade) family.")
        if fam not in ALL_FONTS:
            warnings.append(f"fonts.{role} = '{fam}' is not in the curated catalog.")

    for key in _COLOR_VARS:
        val = (colors.get(key) or "").strip()
        if not val:
            raise TokenError(f"colors.{key} is required.")
        if not _HEX.match(val):
            raise TokenError(f"colors.{key} = '{val}' is not a #rrggbb hex color.")

    base = (shadcn.get("base_color") or "neutral").strip()
    style = (shadcn.get("style") or "new-york").strip()
    if base not in _SHADCN_BASE:
        raise TokenError(f"shadcn.base_color '{base}' not in {sorted(_SHADCN_BASE)}.")
    if style not in _SHADCN_STYLE:
        raise TokenError(f"shadcn.style '{style}' not in {sorted(_SHADCN_STYLE)}.")

    return DesignTokens(
        fonts={k: fonts[k].strip() for k in ("display", "body", "mono")},
        colors={k: colors[k].strip() for k in _COLOR_VARS},
        radius=(data.get("radius") or "0.5rem"),
        shadcn_base_color=base, shadcn_style=style, warnings=warnings,
    )


def _hex_to_hsl(hexstr: str) -> str:
    """'#rrggbb' -> 'H S% L%' string for a shadcn CSS variable."""
    r = int(hexstr[1:3], 16) / 255
    g = int(hexstr[3:5], 16) / 255
    b = int(hexstr[5:7], 16) / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        h = s = 0.0
    else:
        d = mx - mn
        s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif mx == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6
    return f"{round(h*360)} {round(s*100)}% {round(l*100)}%"


def render_globals_css(t: DesignTokens) -> str:
    c = t.colors
    hsl = {k: _hex_to_hsl(v) for k, v in c.items()}
    return f"""@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {{
  :root {{
    --background: {hsl['background']};
    --foreground: {hsl['foreground']};
    --primary: {hsl['primary']};
    --primary-foreground: {hsl['background']};
    --muted: {hsl['muted']};
    --muted-foreground: {hsl['foreground']};
    --border: {hsl['border']};
    --input: {hsl['border']};
    --ring: {hsl['primary']};
    --radius: {t.radius};
  }}
  * {{ border-color: hsl(var(--border)); }}
  body {{ background: hsl(var(--background)); color: hsl(var(--foreground)); }}
}}
"""


def render_tailwind_config(t: DesignTokens) -> str:
    return f"""import type {{ Config }} from "tailwindcss";

const config: Config = {{
  darkMode: ["class"],
  content: ["./app/**/*.{{ts,tsx}}", "./components/**/*.{{ts,tsx}}"],
  theme: {{
    extend: {{
      fontFamily: {{
        display: ["var(--font-display)"],
        sans: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
      }},
      colors: {{
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {{ DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" }},
        muted: {{ DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" }},
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
      }},
      borderRadius: {{ lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" }},
    }},
  }},
  plugins: [require("tailwindcss-animate")],
}};
export default config;
"""
