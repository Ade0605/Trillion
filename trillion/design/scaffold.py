"""
scaffold — the per-project Next.js + Tailwind + shadcn preview app.

The output target IS the design ceiling: vanilla HTML caps quality below
"award-winning", so mockups get composed on a real component framework. The
three load-bearing next.config settings (output export, trailingSlash, basePath
+ assetPrefix) make the static export predictable for Trillion's serving route.

Idempotent: if package.json exists, the scaffold is reused.
"""
from __future__ import annotations

from pathlib import Path

from .design_tokens import DesignTokens, render_globals_css, render_tailwind_config
from .component_catalog import render_full_catalog_markdown


def _font_import(family: str) -> str:
    return family.replace(" ", "_").replace("-", "_")


def _fonts_ts(t: DesignTokens) -> str:
    d, b, m = t.fonts["display"], t.fonts["body"], t.fonts["mono"]
    return f"""import {{ {_font_import(d)}, {_font_import(b)}, {_font_import(m)} }} from "next/font/google";

export const fontDisplay = {_font_import(d)}({{ subsets: ["latin"], weight: ["400"], variable: "--font-display", display: "swap" }});
export const fontBody = {_font_import(b)}({{ subsets: ["latin"], variable: "--font-body", display: "swap" }});
export const fontMono = {_font_import(m)}({{ subsets: ["latin"], variable: "--font-mono", display: "swap" }});
"""


def _next_config(base_path: str) -> str:
    return f"""/** @type {{import('next').NextConfig}} */
const nextConfig = {{
  output: 'export',
  trailingSlash: true,
  basePath: '{base_path}',
  assetPrefix: '{base_path}',
  images: {{ unoptimized: true }},
  eslint: {{ ignoreDuringBuilds: true }},
  typescript: {{ ignoreBuildErrors: true }},
}};
export default nextConfig;
"""


_PACKAGE_JSON = """{
  "name": "prism-preview",
  "private": true,
  "scripts": { "dev": "next dev", "build": "next build", "start": "next start" },
  "dependencies": {
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "framer-motion": "^11.15.0",
    "lucide-react": "^0.468.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.6.0",
    "tailwindcss-animate": "^1.0.7"
  },
  "devDependencies": {
    "typescript": "^5.7.0",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "tailwindcss": "^3.4.17",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20"
  }
}
"""

_POSTCSS = "export default { plugins: { tailwindcss: {}, autoprefixer: {} } };\n"

_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2020", "lib": ["dom", "dom.iterable", "esnext"], "allowJs": true,
    "skipLibCheck": true, "strict": false, "noEmit": true, "esModuleInterop": true,
    "module": "esnext", "moduleResolution": "bundler", "resolveJsonModule": true,
    "isolatedModules": true, "jsx": "preserve", "incremental": true,
    "plugins": [{ "name": "next" }], "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

_UTILS_TS = """import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
"""


def _components_json(t: DesignTokens) -> str:
    return f"""{{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "{t.shadcn_style}",
  "rsc": true,
  "tsx": true,
  "tailwind": {{
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "{t.shadcn_base_color}",
    "cssVariables": true
  }},
  "aliases": {{ "components": "@/components", "utils": "@/lib/utils" }}
}}
"""


def _layout_tsx() -> str:
    return """import type { Metadata } from "next";
import { fontDisplay, fontBody, fontMono } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = { title: "Prism Preview", description: "Design mockups" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fontDisplay.variable} ${fontBody.variable} ${fontMono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
"""


def _page_tsx() -> str:
    return """export default function Home() {
  return (
    <main className="min-h-screen flex items-center justify-center p-10">
      <div className="text-center">
        <h1 className="font-display text-6xl mb-4">Prism</h1>
        <p className="font-mono text-sm text-muted-foreground uppercase tracking-widest">
          mockups render at /&lt;feature&gt;/&lt;screen&gt;/
        </p>
      </div>
    </main>
  );
}
"""

_GITIGNORE = "node_modules/\n.next/\nout/\n*.tsbuildinfo\nnext-env.d.ts\n"


def prepare_scaffold(project_root: Path, tokens: DesignTokens, slug: str,
                     base_path: str | None = None) -> dict:
    """Write the preview app (idempotent). Returns {skipped, files, base_path}."""
    base_path = base_path or f"/design/{slug}/preview"
    preview = project_root / ".prism" / "preview"

    if (preview / "package.json").exists():
        return {"skipped": True, "files": [], "base_path": base_path, "preview": str(preview)}

    files: dict[str, str] = {
        "package.json": _PACKAGE_JSON,
        "next.config.mjs": _next_config(base_path),
        "postcss.config.mjs": _POSTCSS,
        "tsconfig.json": _TSCONFIG,
        "tailwind.config.ts": render_tailwind_config(tokens),
        "components.json": _components_json(tokens),
        "lib/fonts.ts": _fonts_ts(tokens),
        "lib/utils.ts": _UTILS_TS,
        "app/layout.tsx": _layout_tsx(),
        "app/globals.css": render_globals_css(tokens),
        "app/page.tsx": _page_tsx(),
        "prism/component_catalog.md": render_full_catalog_markdown(),
        ".gitignore": _GITIGNORE,
    }
    written = []
    for rel, content in files.items():
        p = preview / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(rel)
    return {"skipped": False, "files": written, "base_path": base_path, "preview": str(preview)}
