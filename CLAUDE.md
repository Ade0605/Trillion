# Code Intelligence — jcode

This repository is indexed with **jcode** (feature-graph code intelligence).
The `.jcode/` directory contains a content-addressable node store and an
SQLite graph of every function, class, method, and module, with typed edges
(CALLS, IMPORTS, CONTAINS, INHERITS) plus plugin-defined types like "depends".

## Workflow — follow this order every time

1. **Orient** — call `jcode_feature_map()` first.
   It shows the folder/feature layout in one call. Use it to pick the right
   `scope` before searching.

2. **Search** — call `jcode_search(query, scope=<folder>)`.
   This uses semantic vector search (or FTS5 fallback). Never run grep to
   find a function — use this instead.

3. **Get context** — call `jcode_context(node_id, scope=<folder>)`.
   DFS-forward from the entry point. Nodes outside the scope are flagged as
   `external_deps` — follow them only if needed.

4. **Check blast radius** — call `jcode_blast_radius(node_id)` **before**
   editing any function. A confidence score < 0.8 means callers outside the
   current scope will break — warn the user first.

5. **Read with line numbers** — jcode search results include the exact file
   path and line range. Always use `offset` and `limit` when reading:

   ```
   # jcode told you: file=partners/mmb/client.py  lines=18-66
   Read(file_path="partners/mmb/client.py", offset=18, limit=48)
   ```

   **Never do a full file read.** A targeted read costs ~50 tokens; a full
   file read can cost 2000+. jcode gives you the line numbers — use them.

## After making code changes

**Always re-index after editing files** so the graph stays in sync:

```
jcode index .
```

Run this after any edit session — new functions, renamed symbols, deleted
files, or refactors will not be visible to `jcode_search` or
`jcode_context` until the index is refreshed. The index is incremental, so
it only re-processes files that changed.

## Rules

- NEVER use grep/ripgrep to locate a function, class, or feature. Use `jcode_search`.
- NEVER read a file just to understand its structure. Use `jcode_context`.
- NEVER do a full file read — always use `offset` + `limit` with the line range jcode provides.
- ALWAYS call `jcode_blast_radius` before editing a function.
- ALWAYS run `jcode index .` after making code changes to keep the graph current.
- Pass `scope=<folder>` when the user's request clearly names a feature area
  (e.g. "in the comments module", "fix the auth flow").
- If scoped search returns nothing, jcode automatically falls back to the
  full graph — you do not need to retry manually.

## When grep IS the right tool

Use grep (or ripgrep `rg`) directly — without going through jcode — when you
are looking for an **exact string literal** that does not correspond to a
code symbol. jcode indexes identifiers and call graphs; it does not index
arbitrary string values inside code.

Good grep targets (jcode will NOT find these reliably):
- A URL or base URL string:  `rg "mymoneybazaar.com"`
- A hard-coded API key name: `rg "X-Api-Key"`
- A Django URL pattern:      `rg "path.*login"`
- A specific error message:  `rg "Invalid OTP"`
- A config value or secret:  `rg "REDIS_HOST"`

Use jcode for everything else — structure, behaviour, and relationships.

## Tool reference

| Tool | When to call |
|------|-------------|
| `jcode_feature_map()` | Start of every task — orient yourself |
| `jcode_search(query, scope?)` | Find the entry-point node |
| `jcode_context(node_id, scope?)` | Understand what a node calls and is called by |
| `jcode_blast_radius(node_id)` | Before any edit — see who breaks |
| `jcode_index(repo_path)` | After large refactors — refresh the graph |
