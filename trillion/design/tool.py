"""
Registers the `design_screen` tool into Trillion's ToolRegistry.

It's confirmation-gated: every dispatch spawns Claude Code (real cost + minutes),
so it must route through the gate like other consequential actions.
"""
from __future__ import annotations

_INPUT_SCHEMA = {
    "type": "object",
    "required": ["feature_slug", "screen_name", "description"],
    "properties": {
        "feature_slug": {"type": "string", "description": "kebab-case feature id, e.g. 'landing'"},
        "screen_name": {"type": "string", "description": "kebab-case screen id, e.g. 'hero'"},
        "description": {"type": "string", "description": "what the screen is and must communicate"},
        "visual_direction": {"type": "string",
            "description": "SPECIFIC visual instructions (name components/opacities/motion), not adjectives"},
        "quality": {"type": "string", "enum": ["standard", "premium"]},
        "reference_images": {"type": "array", "items": {"type": "string"},
            "description": "image filenames under .prism/references/<feature_slug>/"},
        "components_hint": {"type": "array", "items": {"type": "string"}},
        "project": {"type": "string", "description": "design workspace slug (default 'trillion-voice')"},
    },
}

_DESC = (
    "Compose a single award-quality Next.js + shadcn mockup screen by spawning "
    "Claude Code against a per-project design system. Expensive (~$1-6, takes "
    "minutes). Returns a URL to view the built screen. Give SPECIFIC visual_direction."
)


def register_design_tools(registry) -> None:
    def design_screen(feature_slug, screen_name, description, visual_direction="",
                      quality="standard", reference_images=None, components_hint=None,
                      project="trillion-voice"):
        from .composer import generate_mockup
        res = generate_mockup(
            feature_slug=feature_slug, screen_name=screen_name, description=description,
            visual_direction=visual_direction, quality=quality,
            reference_images=reference_images or [], components_hint=components_hint or [],
            project=project,
        )
        if res.ok:
            w = f" (warnings: {'; '.join(res.warnings)})" if res.warnings else ""
            return (f"Composed {res.feature}/{res.screen}. View at {res.screen_url} "
                    f"— {res.cc_events} build steps, {res.duration_s:.0f}s.{w}")
        return f"Mockup failed for {res.feature}/{res.screen}: {res.error}"

    registry.register("design_screen", _DESC, _INPUT_SCHEMA, design_screen,
                      requires_confirmation=True)
