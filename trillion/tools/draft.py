"""Draft tool — prepare messages for the user to review. Never sends automatically."""
from __future__ import annotations


def draft_message(to: str, subject: str = "", body_hint: str = "") -> str:
    """
    Compose a draft message. Returns the draft text for the user to review.
    This tool ONLY drafts — it never sends. Sending requires a separate
    explicit action by the user.
    """
    parts = [
        f"To: {to}",
    ]
    if subject:
        parts.append(f"Subject: {subject}")
    parts.append("")
    if body_hint:
        parts.append(body_hint)
    else:
        parts.append("[No body provided — add your message here]")
    parts.append("")
    parts.append("---")
    parts.append("Review the draft above. To send, copy it manually or ask me to prepare it for a specific app.")

    return "\n".join(parts)


def register_draft(registry) -> None:
    registry.register(
        name="draft_message",
        description=(
            "Compose a draft message or email for the user to review. "
            "Always shows the draft and waits for the user to approve before anything is sent. "
            "Never sends automatically."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient name or address"},
                "subject": {"type": "string", "description": "Subject line (optional)"},
                "body_hint": {"type": "string", "description": "Key points or full body to include"},
            },
            "required": ["to"],
        },
        fn=draft_message,
        requires_confirmation=True,
    )
