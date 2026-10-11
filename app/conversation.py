"""Conversation history validation and multi-turn context helpers.

History is never trusted blindly. Only ``user`` and ``assistant`` roles are
allowed (system messages are rejected at the schema level), and the content is
scanned for the same adversarial patterns as the current message so that
multi-turn attacks are not smuggled in through prior turns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Patterns that indicate an attempt to override instructions or exfiltrate the
# system prompt. Checked against both the current message and history.
PROMPT_INJECTION_PATTERNS = (
    r"ignore (?:all |any |the )?previous instructions",
    r"ignore (?:all |any |the )?prior instructions",
    r"disregard (?:all |any |the )?(?:previous|prior) instructions",
    r"reveal (?:your |the )?(?:system )?(?:prompt|instructions)",
    r"show (?:me )?(?:your |the )?(?:system )?(?:prompt|instructions)",
    r"print (?:your |the )?(?:hidden |internal )?(?:configuration|config|prompt)",
    r"system prompt",
    r"internal instructions",
    r"developer mode",
    r"\bdo anything now\b",
    r"\bdan\b",
    r"you are now",
    r"act as (?:a )?(?:system|developer|admin)",
    r"pretend (?:to be|you are) (?:a )?(?:system|developer|admin)",
    r"override (?:the )?(?:policy|policies|rules|tools?)",
)

_CHECKOUT_CONFIRM_PATTERNS = (
    r"confirm checkout",
    r"confirm (?:the )?(?:order|purchase)",
    r"yes,? (?:please )?(?:check ?out|confirm|complete)",
    r"i confirm",
    r"go ahead and (?:check ?out|complete)",
)

_CHECKOUT_DECLINE_PATTERNS = (
    r"do not (?:check ?out|confirm|complete)",
    r"don'?t (?:check ?out|confirm|complete)",
    r"cancel (?:the )?(?:checkout|order|purchase)",
    r"no,? (?:don'?t|do not)",
)

_CHECKOUT_REQUEST_PATTERNS = (
    r"check ?out",
    r"place (?:my |the )?order",
    r"complete (?:my |the )?purchase",
    r"\bbuy\b",
)


@dataclass
class HistoryEntryView:
    role: str
    content: str


def normalize_history(history) -> list[HistoryEntryView]:
    """Coerce incoming history (pydantic models or dicts) into simple views."""
    views: list[HistoryEntryView] = []
    for entry in history or []:
        if hasattr(entry, "role"):
            role = getattr(entry, "role")
            content = getattr(entry, "content")
        else:
            role = entry.get("role")
            content = entry.get("content")
        views.append(HistoryEntryView(role=str(role), content=str(content)))
    return views


def contains_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in PROMPT_INJECTION_PATTERNS)


def history_contains_prompt_injection(history: list[HistoryEntryView]) -> bool:
    """Detect injection attempts smuggled into earlier user turns."""
    return any(
        entry.role == "user" and contains_prompt_injection(entry.content)
        for entry in history
    )


def is_checkout_confirmation(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _CHECKOUT_CONFIRM_PATTERNS)


def is_checkout_decline(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _CHECKOUT_DECLINE_PATTERNS)


def mentions_checkout(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _CHECKOUT_REQUEST_PATTERNS)


def assistant_requested_confirmation(history: list[HistoryEntryView]) -> bool:
    """True if the most recent assistant turn asked the user to confirm checkout."""
    for entry in reversed(history):
        if entry.role == "assistant":
            lowered = entry.content.lower()
            return "confirm checkout" in lowered or "confirm by saying" in lowered
        if entry.role == "user":
            # Only look at the immediately preceding assistant turn.
            continue
    return False


_REFERENCE_PATTERNS = (
    r"that product",
    r"those (?:ones|products|headphones|items)",
    r"the previous order",
    r"\bit\b",
    r"\bthem\b",
    r"confirm it",
)


def is_contextual_reference(text: str) -> bool:
    """Detect references like 'that product' that need prior-turn context."""
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in _REFERENCE_PATTERNS)


def last_mentioned_topic(history: list[HistoryEntryView]) -> str | None:
    """Return a coarse topic from the most recent assistant/user turns.

    Used to resolve contextual references deterministically (e.g. 'that
    product' after the assistant listed products).
    """
    for entry in reversed(history):
        lowered = entry.content.lower()
        if any(k in lowered for k in ("headphone", "laptop", "keyboard", "product", "catalog")):
            return "product"
        if "order" in lowered:
            return "order"
        if "cart" in lowered:
            return "cart"
    return None
