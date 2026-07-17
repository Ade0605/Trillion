# Head-of-Design Agent (`design_screen`)

Trillion can compose award-quality Next.js + shadcn mockups by spawning Claude
Code against a per-project design system. It's a confirmation-gated tool (every
run costs ~$1–6 and takes minutes).

## How it works

```
design_workspace/<project>/
  design.md                 design system + ```yaml tokens (fonts/colors/shadcn)
  .prism/brief.md           standing decisions (THE BRIEF IS LAW)
  .prism/references/<feat>/  reference screenshots you drop in
  .prism/preview/            Next.js app (the substrate; gitignored build)
  features/<feature>.md      per-feature spec
```

A dispatch: validate → parse tokens → bootstrap docs (first time) → scaffold the
Next.js app (idempotent) → build a ~5KB Claude Code prompt (brief + required
visual elements + palette + references) → `spawn_claude_code` in the preview dir
→ CC installs components, writes `app/<feature>/<screen>/page.tsx`, runs
`npm run build` → we verify `out/<feature>/<screen>/index.html` exists.

## Using it

Ask Trillion (it will confirm before spending):
> "Design a landing hero for the voice assistant — grid-pattern at 0.5 opacity
> with drifting amber particles, a live voice waveform, and a breathing status
> pulse."

Or call the tool directly with `feature_slug`, `screen_name`, `description`, and
a **specific** `visual_direction` (name components/opacities/motion, not adjectives).

View the result at:
```
http://localhost:7777/design/<project>/preview/<feature>/<screen>/
```

## What's built (pragmatic core)

- Tier 1 doc model + `design_tokens` (validation, forbidden fonts, tailwind/CSS render)
- Tier 2 idempotent 13-file Next.js scaffold (`output: export`, `trailingSlash`, `basePath`)
- Tier 3 Claude Code subprocess driver (sanitized env: only `ANTHROPIC_API_KEY`)
- Tier 4 curated component catalog (shadcn + MagicUI + Framer; no copy-paste-only libs)
- Tier 6 brief-is-law + required visual elements in the CC prompt
- Tier 7 file-based reference images (path-traversal safe)

## Not built (deferred)

- **Tier 5 AI image generation** — needs a `GEMINI_API_KEY` with billing (image
  models aren't in the free tier). Add the key and ask to wire `generate_image`.
- Tier 7.5 URL → screenshot reference capture (Playwright).

## Prereqs (verified present)

Node 24 + npm 11, Claude Code CLI. First dispatch runs `npm install` (slow); later
screens reuse it.
