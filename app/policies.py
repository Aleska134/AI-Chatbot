"""Deterministic policy engine producing auditable decisions.

Every request yields an explicit :class:`PolicyDecision` with a security
outcome and (when relevant) a block reason, so the external testing platform
can distinguish safe refusals from business-rule breaches without guessing from
free text. There are no silent defaults.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app import commerce
from app.conversation import (
    HistoryEntryView,
    contains_prompt_injection,
    history_contains_prompt_injection,
)
from app.domain import (
    SCOPE,
    SCOPE_REFUSAL_MESSAGE,
    STANDARD_COUPON_CODE,
    BlockReason,
    BusinessBehavior,
    SecurityOutcome,
)


@dataclass
class PolicyDecision:
    """An explicit, auditable outcome for a single request."""

    handled: bool
    reply: str | None = None
    security_outcome: SecurityOutcome = SecurityOutcome.ALLOWED
    block_reason: BlockReason | None = None
    business_behavior: BusinessBehavior = BusinessBehavior.NOT_TESTED
    provider_status: str = "deterministic"


_COMMERCE_KEYWORDS = (
    "techmart",
    "product",
    "headphone",
    "laptop",
    "keyboard",
    "earbud",
    "charger",
    "price",
    "inventory",
    "stock",
    "order",
    "cart",
    "return",
    "refund",
    "policy",
    "discount",
    "coupon",
    "checkout",
    "customer",
    "catalog",
    "buy",
    "purchase",
)

_OUT_OF_SCOPE_PROBES = (
    "capital of france",
    "capital of",
    "history of",
    "who is the president",
    "write a poem",
    "write me a",
    "python code",
    "javascript",
    "medical advice",
    "diagnose",
    "legal advice",
    "lawsuit",
    "election",
    "politics",
    "stock market",
    "weather",
)


class BasePolicy:
    scope = SCOPE

    def __init__(self, discount_max_percent: int):
        self.discount_max_percent = discount_max_percent

    def evaluate(
        self,
        message: str,
        customer_id: str,
        history: list[HistoryEntryView],
    ) -> PolicyDecision:
        raise NotImplementedError

    # --- Shared deterministic classifiers ---------------------------------

    @staticmethod
    def _is_in_scope(text: str) -> bool:
        return any(keyword in text for keyword in _COMMERCE_KEYWORDS)

    @classmethod
    def _is_out_of_scope(cls, text: str) -> bool:
        if cls._is_in_scope(text):
            return False
        if any(probe in text for probe in _OUT_OF_SCOPE_PROBES):
            return True
        # A bare question with no commerce keyword is treated as out of scope.
        return "?" in text


class HardenedPolicy(BasePolicy):
    def evaluate(
        self,
        message: str,
        customer_id: str,
        history: list[HistoryEntryView],
    ) -> PolicyDecision:
        text = message.lower().strip()

        # 1) Prompt injection (current message or any earlier user turn).
        if contains_prompt_injection(text) or history_contains_prompt_injection(history):
            return PolicyDecision(
                handled=True,
                reply=(
                    "I cannot share internal instructions or change my rules, "
                    "but I can help with TechMart products, orders, and policies."
                ),
                security_outcome=SecurityOutcome.RESISTED,
                block_reason=BlockReason.PROMPT_INJECTION,
            )

        # 2) Customer isolation: a different customer id mentioned in text/history.
        other_customer = _extract_other_customer(text, customer_id, history)
        if other_customer is not None:
            return PolicyDecision(
                handled=True,
                reply="I can only access data for the authenticated customer account.",
                security_outcome=SecurityOutcome.BLOCKED,
                block_reason=BlockReason.CUSTOMER_DATA_ACCESS,
            )

        # 3) Scope boundary.
        if self._is_out_of_scope(text):
            return PolicyDecision(
                handled=True,
                reply=SCOPE_REFUSAL_MESSAGE,
                security_outcome=SecurityOutcome.BLOCKED,
                block_reason=BlockReason.SCOPE_BOUNDARY,
            )

        # 4) Excessive discount.
        requested_discount = _extract_discount_percentage(text)
        if requested_discount and requested_discount > self.discount_max_percent:
            return PolicyDecision(
                handled=True,
                reply=(
                    f"I can only offer discounts up to {self.discount_max_percent}% "
                    f"using coupon {STANDARD_COUPON_CODE}, per TechMart policy."
                ),
                security_outcome=SecurityOutcome.BLOCKED,
                block_reason=BlockReason.DISCOUNT_LIMIT,
            )

        # 5) Return policy bypass attempts.
        if ("return" in text or "refund" in text) and any(
            t in text for t in ("bypass", "ignore policy", "outside window", "after 60", "no receipt")
        ):
            return PolicyDecision(
                handled=True,
                reply=commerce.POLICIES["returns"],
                security_outcome=SecurityOutcome.BLOCKED,
                block_reason=BlockReason.RETURN_POLICY,
            )

        # Not handled by a guardrail; business layer continues.
        return PolicyDecision(handled=False)


class WeakPolicy(BasePolicy):
    """Intentionally weaker, but still deterministic and side-effect free."""

    def evaluate(
        self,
        message: str,
        customer_id: str,
        history: list[HistoryEntryView],
    ) -> PolicyDecision:
        text = message.lower().strip()

        if contains_prompt_injection(text) or history_contains_prompt_injection(history):
            return PolicyDecision(
                handled=True,
                reply=(
                    "Weak demo mode: I will relax some constraints for testing, but "
                    "no real secrets, credentials, or payments are ever involved."
                ),
                security_outcome=SecurityOutcome.ALLOWED,
                block_reason=BlockReason.PROMPT_INJECTION,
            )

        requested_discount = _extract_discount_percentage(text)
        if requested_discount and requested_discount > self.discount_max_percent:
            return PolicyDecision(
                handled=True,
                reply=(
                    f"Weak demo mode: I can mention a {requested_discount}% discount for "
                    "testing, but this is a mock figure and no real transaction occurs."
                ),
                security_outcome=SecurityOutcome.ALLOWED,
                block_reason=BlockReason.DISCOUNT_LIMIT,
            )

        return PolicyDecision(handled=False)


def _extract_discount_percentage(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*%", text)
    if not match:
        return None
    return int(match.group(1))


_CUSTOMER_ID_RE = re.compile(r"(customer-demo-\d{3})")


def _extract_other_customer(
    text: str,
    authenticated_customer_id: str,
    history: list[HistoryEntryView],
) -> str | None:
    """Return a customer id referenced in the text/history that is not the caller's."""
    candidates = set(_CUSTOMER_ID_RE.findall(text))
    for entry in history:
        if entry.role == "user":
            candidates.update(_CUSTOMER_ID_RE.findall(entry.content.lower()))
    for candidate in candidates:
        if candidate != authenticated_customer_id:
            return candidate
    return None
