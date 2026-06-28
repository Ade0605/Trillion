"""Web search tool — uses DuckDuckGo Instant Answer API (no key required)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


def web_search(query: str) -> str:
    """Search the web for a query and return a concise summary of results."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Trillion-AI/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return f"Web search failed: {e}"

    parts: list[str] = []

    abstract = data.get("AbstractText", "").strip()
    if abstract:
        source = data.get("AbstractSource", "")
        parts.append(f"{abstract}" + (f" (Source: {source})" if source else ""))

    answer = data.get("Answer", "").strip()
    if answer and answer != abstract:
        parts.append(f"Quick answer: {answer}")

    related = data.get("RelatedTopics", [])
    snippets: list[str] = []
    for item in related[:5]:
        if isinstance(item, dict) and item.get("Text"):
            snippets.append(f"- {item['Text'][:200]}")
    if snippets:
        parts.append("Related:\n" + "\n".join(snippets))

    if not parts:
        return (
            f"No instant answer found for '{query}'. "
            "Try rephrasing or ask me to search for something more specific."
        )

    return "\n\n".join(parts)


def register_web_search(registry) -> None:
    registry.register(
        name="web_search",
        description=(
            "Search the web for current information, facts, definitions, or news. "
            "Use when the question requires up-to-date or external knowledge."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
            },
            "required": ["query"],
        },
        fn=web_search,
    )
