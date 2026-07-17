"""
Thin seam around the Anthropic SDK.
Everything else calls send_turn(); nothing else imports anthropic directly.
"""
import os
from typing import Generator

import anthropic

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file and restart."
            )
        _client = anthropic.Anthropic(api_key=key)
    return _client


_CACHE = {"type": "ephemeral"}


def _cache_system(system):
    """Ensure the stable system prefix carries a cache breakpoint."""
    if isinstance(system, str):
        return [{"type": "text", "text": system, "cache_control": _CACHE}]
    return system  # agent already marks the stable block


def _cache_tools(tools):
    """Cache the (stable) tool definitions by marking the last one."""
    if not tools:
        return tools
    marked = [dict(t) for t in tools]
    marked[-1] = {**marked[-1], "cache_control": _CACHE}
    return marked


def _cache_messages(messages):
    """Cache the conversation prefix by marking the last block of the last
    message, so each deeper turn reuses everything before it instead of
    re-reading the whole growing history."""
    if not messages:
        return messages
    out = list(messages)
    last = dict(out[-1])
    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [{"type": "text", "text": content, "cache_control": _CACHE}]
    elif isinstance(content, list) and content:
        blocks = [dict(b) if isinstance(b, dict) else b for b in content]
        if isinstance(blocks[-1], dict):
            blocks[-1] = {**blocks[-1], "cache_control": _CACHE}
        last["content"] = blocks
    else:
        return messages
    out[-1] = last
    return out


def send_turn(
    messages: list[dict],
    system,
    model: str,
    tools: list[dict] | None = None,
) -> Generator[str | dict, None, None]:
    """
    Stream one conversation turn.

    ``system`` may be a plain string or a list of content blocks (the agent
    passes blocks so the stable prefix is cached). Prompt caching is applied to
    the system prefix, the tool definitions, and the conversation prefix.

    Yields:
      - str chunks for plain text as they arrive
      - dict with key "tool_use" when the model wants to call a tool:
        {"tool_use": {"id": ..., "name": ..., "input": ...}}

    Never raises — network / API errors are yielded as {"error": "..."}.
    """
    try:
        kwargs: dict = dict(
            model=model,
            max_tokens=4096,
            system=_cache_system(system),
            messages=_cache_messages(messages),
        )
        if tools:
            kwargs["tools"] = _cache_tools(tools)

        with _get_client().messages.stream(**kwargs) as stream:
            current_tool: dict | None = None
            current_tool_json = ""

            for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool = {"id": block.id, "name": block.name}
                        current_tool_json = ""

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield delta.text
                    elif delta.type == "input_json_delta":
                        current_tool_json += delta.partial_json

                elif etype == "content_block_stop":
                    if current_tool is not None:
                        import json
                        try:
                            current_tool["input"] = json.loads(current_tool_json or "{}")
                        except json.JSONDecodeError:
                            current_tool["input"] = {}
                        yield {"tool_use": current_tool}
                        current_tool = None
                        current_tool_json = ""

            # Cache/usage stats — consumers that don't care simply ignore this.
            try:
                u = stream.get_final_message().usage
                yield {"usage": {
                    "input": getattr(u, "input_tokens", 0),
                    "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                    "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                    "output": getattr(u, "output_tokens", 0),
                }}
            except Exception:
                pass

    except anthropic.APIConnectionError:
        yield {"error": "Could not reach Anthropic — check your internet connection."}
    except anthropic.AuthenticationError:
        yield {"error": "Invalid API key. Check ANTHROPIC_API_KEY in your .env file."}
    except anthropic.RateLimitError:
        yield {"error": "Rate limit hit. Wait a moment and try again."}
    except anthropic.APIError as e:
        yield {"error": f"API error: {e}"}
    except Exception as e:
        yield {"error": f"Unexpected error: {e}"}
