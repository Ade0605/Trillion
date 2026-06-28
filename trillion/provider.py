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


def send_turn(
    messages: list[dict],
    system: str,
    model: str,
    tools: list[dict] | None = None,
) -> Generator[str | dict, None, None]:
    """
    Stream one conversation turn.

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
            system=system,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

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
