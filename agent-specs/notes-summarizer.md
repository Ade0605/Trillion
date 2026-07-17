# Agent Spec — Notes Summarizer  (`notes-summarizer`)

**Role.** Summarizes the users local notes into concise bullet-point digests, pulling key facts and action items from long notes.

**Special requirements.** (none)

## Competencies
- Note Discovery & Ingestion: Enumerate and read all local notes (by list, folder, or tag), handling varied lengths, formats, and encodings to build a complete corpus for summarization.
- Key Fact Extraction: Identify and surface the most informative sentences, named entities, dates, figures, and definitions from each note using extractive or hybrid NLP techniques.
- Action Item Detection: Recognize task-oriented language (e.g., 'TODO', 'follow up', 'need to', imperative verbs) and extract discrete action items with owner and due-date context when present.
- Concise Bullet-Point Synthesis: Compress long-form prose into short, scannable bullet points using abstractive summarization, preserving the original meaning without redundancy or hallucination.
- Cross-Note Deduplication & Grouping: Detect when multiple notes share the same topic or project and consolidate their bullets into a unified digest rather than producing duplicate points.
- Prioritization & Ranking: Score and reorder bullets by importance signals (recency, frequency of mention, explicit markers like 'urgent' or 'critical') so the most actionable content appears first.
- Structured Digest Formatting: Emit output in a consistent schema — e.g., sections for 'Key Facts', 'Action Items', and 'Decisions Made' — that is human-readable and optionally machine-parseable (Markdown, JSON).
- Incremental / Delta Summarization: Track which notes have already been digested and process only new or modified notes on subsequent runs, avoiding redundant re-summarization of unchanged content.

## Granted tools
list_notes, read_note, search_notes, list_memories, list_reminders

## Tool wishlist (build next)
- `summarize_text` — Send a block of note text to an LLM or dedicated summarization API and receive a structured bullet-point digest in return, reducing the need to manage raw prompt engineering inside the agent. (needs OpenAI Chat Completions API / Anthropic Claude API / open-source model via Ollama)
- `extract_action_items` — Run a specialized NLP classifier over text to detect task-oriented sentences and return structured action items with owner, verb, object, and optional deadline fields. (needs Hugging Face Inference API (e.g., fine-tuned BERT/T5 for action-item detection) or LLM function-calling endpoint)
- `create_note` — Write the finished bullet-point digest back into the user's note store as a new note or append it to an existing summary note, closing the read-summarize-write loop. (needs Native note store write API (e.g., Obsidian Local REST API, Notion API, Apple Notes AppleScript))
- `update_note` — Update an existing summary/digest note in-place with incremental changes when only a subset of notes have changed since the last run. (needs Native note store write API (Obsidian, Notion, Joplin, etc.))
- `watch_notes` — Subscribe to file-system or app-level change events so the agent can trigger re-summarization automatically when a note is created or edited, rather than polling on a schedule. (needs File system watcher (chokidar / inotify) or note-app webhook (Notion, Roam))
- `create_reminder` — Persist extracted action items as calendar reminders or task entries, so they surface in the user's task manager rather than being buried in a digest note. (needs Reminders / Tasks API (Apple Reminders, Google Tasks, Todoist API))

## Design patterns
- Map-then-Reduce Summarization: Each note is first independently summarized (map step), then all per-note bullet points are aggregated and de-duplicated into a single cohesive digest (reduce step). This mirrors the MapReduce paradigm used in large-scale text summarization pipelines and prevents any single long note from overwhelming the context window.
- Retrieval-Augmented Digest (RAG-style): Instead of blindly reading every note, the agent uses search_notes to retrieve only the notes most relevant to a user's query or topic tag before summarizing, keeping token usage bounded and the digest focused.
- Incremental / Delta Processing with Memory: The agent stores metadata (note ID + last-modified timestamp) in list_memories between runs. On each invocation it compares current note timestamps against stored ones, summarizing only changed notes and merging their bullets into the running digest — avoiding full reprocessing.
- Structured Output via Constrained Prompting: The LLM is instructed with a strict output schema (e.g., JSON with keys 'key_facts', 'action_items', 'decisions') rather than free prose, making the digest reliably parseable downstream by other tools or UI components.
- Confidence-Gated Action Item Promotion: Extracted action items pass through a rule-based or classifier filter before being promoted to reminders or task lists. Only items meeting a confidence threshold (explicit imperative verb + named subject or due date) are elevated, reducing false positives.

## Sources
- (none)
