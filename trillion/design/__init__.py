"""
Head-of-design sub-agent for Trillion.

Exposes a `design_screen` tool (registered into the ToolRegistry) that composes
award-quality Next.js + shadcn mockups by spawning Claude Code as a subprocess
against a per-project design system. See docs/design-agent.md.
"""
