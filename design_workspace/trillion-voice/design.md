# Design System — Trillion Voice

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
