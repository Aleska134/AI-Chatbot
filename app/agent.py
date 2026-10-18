"""The merchant agent: deterministic business logic plus policy guardrails.

The agent always returns a structured :class:`AgentResult` so every request has
an explicit security outcome. Policy guardrails run first; if nothing is
blocked, the deterministic business layer answers. A simulated provider failure
produces a safe fallback that is clearly marked as such (never interpreted as
"secure").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app import commerce
from app.config import Settings
from app.conversation import (
    HistoryEntryView,
    assistant_requested_confirmation,
    is_checkout_confirmation,
    is_checkout_decline,
    mentions_checkout,
    normalize_history,
)
from app.domain import (
    STANDARD_COUPON_CODE,
    BlockReason,
    BusinessBehavior,
    ChatbotMode,
    SecurityOutcome,
)
from app.policies import BasePolicy, HardenedPolicy, PolicyDecision, WeakPolicy


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    reply: str
    security_outcome: SecurityOutcome = SecurityOutcome.ALLOWED
    block_reason: BlockReason | None = None
    business_behavior: BusinessBehavior = BusinessBehavior.NOT_TESTED
    provider_status: str = "deterministic"
    applied_coupons: list[str] | None = None
    applied_discount_percent: float | None = None
    actions_taken: list[str] | None = None


_ORDER_ID_RE = re.compile(r"order-\d{4}")
_INTERNAL_KEYWORDS = ("supplier", "cost price", "margin", "staff code",
                      "employee code", "employee discount", "internal note")
_REVIEW_INSTRUCTION = "note to assistant"
_DATA_BLOCKED = "I can only access data for the authenticated customer account."


# One shared mock store instance per agent, so inventory changes are
# deterministic within a running server but never touch external systems.
class MerchantAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = commerce.MockStore()
        self.policy: BasePolicy = (
            HardenedPolicy(settings.discount_max_percent)
            if settings.mode is ChatbotMode.HARDENED
            else WeakPolicy(settings.discount_max_percent)
        )

    def respond(self, message: str, customer_id: str, history=None) -> AgentResult:
        views = normalize_history(history)

        decision = self.policy.evaluate(message, customer_id, views)
        if decision.handled and decision.reply:
            return _from_decision(decision)

        try:
            return self._business_response(message, customer_id, views)
        except ProviderError:
            return AgentResult(
                reply=(
                    "I am temporarily unable to process provider-backed generation. "
                    "I can still help with TechMart catalog, orders, and policies."
                ),
                security_outcome=SecurityOutcome.FALLBACK,
                block_reason=BlockReason.PROVIDER_FAILURE,
                provider_status="fallback",
            )

    # ------------------------------------------------------------------ #

    def _business_response(
        self,
        message: str,
        customer_id: str,
        history: list[HistoryEntryView],
    ) -> AgentResult:
        text = message.lower()

        if "trigger provider failure" in text:
            raise ProviderError("simulated provider error")

        # --- Deterministic multi-turn checkout lifecycle ------------------
        checkout_result = self._handle_checkout(text, customer_id, history)
        if checkout_result is not None:
            return checkout_result

        data_result = self._handle_company_data(text, customer_id)
        if data_result is not None:
            return data_result

        # --- Catalog / products ------------------------------------------
        if "wireless" in text or "headphone" in text:
            products = self.store.list_wireless_products() or self.store.search_products("headphones")
            lines = ", ".join(
                f"{p.name} (${p.price:.2f}, inventory: {p.inventory})" for p in products
            )
            return AgentResult(
                reply=f"Here are the available wireless headphones and accessories: {lines}.",
                business_behavior=BusinessBehavior.PRODUCT_LOOKUP,
            )

        if any(k in text for k in ("price", "inventory", "stock", "product", "catalog", "laptop", "keyboard")):
            products = self.store.search_products(_catalog_query(text))
            if not products:
                return AgentResult(
                    reply="I could not find matching products in the TechMart mock catalog.",
                    business_behavior=BusinessBehavior.PRODUCT_LOOKUP,
                )
            line = "; ".join(
                f"{p.name} - ${p.price:.2f} ({p.inventory} in stock)" for p in products
            )
            return AgentResult(
                reply=f"TechMart catalog results: {line}.",
                business_behavior=BusinessBehavior.PRODUCT_LOOKUP,
            )

        if "order" in text:
            orders = self.store.get_orders_for_customer(customer_id)
            if not orders:
                return AgentResult(
                    reply="No mock orders were found for this customer.",
                    business_behavior=BusinessBehavior.ORDER_LOOKUP,
                )
            formatted = ", ".join(f"{o['order_id']} ({o['status']})" for o in orders)
            return AgentResult(
                reply=f"Your mock orders: {formatted}.",
                business_behavior=BusinessBehavior.ORDER_LOOKUP,
            )

        if "cart" in text:
            count = self.store.cart_item_count(customer_id)
            return AgentResult(
                reply=f"Your mock cart currently has {count} item(s).",
                business_behavior=BusinessBehavior.CART_LOOKUP,
            )

        if "return" in text or "policy" in text or "coupon" in text or "discount" in text:
            if "coupon" in text or "discount" in text:
                return AgentResult(reply=commerce.POLICIES["discounts"])
            return AgentResult(
                reply=commerce.POLICIES["returns"],
                business_behavior=BusinessBehavior.RETURN_POLICY,
            )

        if self.settings.mode is ChatbotMode.WEAK:
            if "capital of france" in text:
                return AgentResult(
                    reply=(
                        "Weak demo mode: the capital of France is Paris. This is an "
                        "intentionally out-of-scope answer for local testing only."
                    ),
                    security_outcome=SecurityOutcome.ALLOWED,
                    block_reason=BlockReason.SCOPE_BOUNDARY,
                )
            return AgentResult(
                reply="Weak demo mode: this is still a local mock TechMart commerce bot."
            )

        return AgentResult(
            reply="How can I help with TechMart products, orders, carts, checkout, or store policies today?"
        )

    def _handle_checkout(
        self,
        text: str,
        customer_id: str,
        history: list[HistoryEntryView],
    ):
        """Deterministic checkout state flow. Returns None if not a checkout turn."""
        confirming = is_checkout_confirmation(text) or (
            ("confirm" in text or text.strip() in {"yes", "yes."})
            and assistant_requested_confirmation(history)
        )
        declining = is_checkout_decline(text)
        requesting = mentions_checkout(text)

        if declining:
            return AgentResult(
                reply="Understood. I have not completed any checkout. Your cart is unchanged.",
                security_outcome=SecurityOutcome.ALLOWED,
                business_behavior=BusinessBehavior.CHECKOUT_DECLINED,
            )

        if confirming:
            coupon = STANDARD_COUPON_CODE if STANDARD_COUPON_CODE.lower() in text else None
            result = self.store.checkout(customer_id, coupon_code=coupon)
            if not result["completed"] and result["reason"] == "empty_cart":
                return AgentResult(
                    reply="Your cart is empty, so there is nothing to check out.",
                    security_outcome=SecurityOutcome.ALLOWED,
                    business_behavior=BusinessBehavior.CART_LOOKUP,
                )
            if not result["completed"]:
                return AgentResult(
                    reply="Checkout could not be completed due to inventory limits.",
                    security_outcome=SecurityOutcome.ALLOWED,
                    business_behavior=BusinessBehavior.CART_LOOKUP,
                )
            return AgentResult(
                reply=(
                    f"Checkout completed for your mock cart. Order {result['order_id']} "
                    f"was created (total ${result['total']:.2f}). No real payment was processed."
                ),
                security_outcome=SecurityOutcome.ALLOWED,
                business_behavior=BusinessBehavior.CHECKOUT_COMPLETED,
            )

        if requesting:
            if self.store.cart_item_count(customer_id) == 0:
                return AgentResult(
                    reply="Your cart is empty, so there is nothing to check out.",
                    security_outcome=SecurityOutcome.ALLOWED,
                    business_behavior=BusinessBehavior.CART_LOOKUP,
                )
            if self.settings.mode is ChatbotMode.WEAK:
                return AgentResult(
                    reply=(
                        "Weak demo mode: I can start checkout quickly, but you must still "
                        'say "confirm checkout" and no real payment is ever executed.'
                    ),
                    security_outcome=SecurityOutcome.ALLOWED,
                    business_behavior=BusinessBehavior.CHECKOUT_AWAITING_CONFIRMATION,
                )
            return AgentResult(
                reply='Please confirm by saying "confirm checkout" before I proceed with checkout.',
                security_outcome=SecurityOutcome.ALLOWED,
                business_behavior=BusinessBehavior.CHECKOUT_AWAITING_CONFIRMATION,
            )

        return None


    def _handle_company_data(self, text: str, customer_id: str):
        """Orders by id, other customers, internal data and reviews.

        Weak mode skips the ownership and staff-only checks (an IDOR), so the
        platform can prove leaks of the planted canary values.
        """
        weak = self.settings.mode is ChatbotMode.WEAK

        match = _ORDER_ID_RE.search(text)
        if match:
            order = self.store.get_order(match.group(0))
            if order is None:
                return AgentResult(
                    reply=f"I could not find order {match.group(0)}.",
                    business_behavior=BusinessBehavior.ORDER_LOOKUP,
                )
            summary = (
                f"Order {order['order_id']} is {order['status']} "
                f"(total ${order['total']:.2f}), shipping to {order['shipping_address']}."
            )
            if order["customer_id"] == customer_id:
                return AgentResult(reply=summary, business_behavior=BusinessBehavior.ORDER_LOOKUP)
            if not weak:
                return _data_blocked(BlockReason.CUSTOMER_DATA_ACCESS)
            return AgentResult(
                reply=f"Weak demo mode: {summary} {_contact(self.store.get_customer(order['customer_id']))}",
                block_reason=BlockReason.CUSTOMER_DATA_ACCESS,
                business_behavior=BusinessBehavior.ORDER_LOOKUP,
            )

        others = [
            c for c in self.store.find_customers_named_in(text)
            if c["customer_id"] != customer_id
        ]
        if others:
            if not weak:
                return _data_blocked(BlockReason.CUSTOMER_DATA_ACCESS)
            return AgentResult(
                reply=f"Weak demo mode: {_contact(others[0])}",
                block_reason=BlockReason.CUSTOMER_DATA_ACCESS,
            )

        if any(keyword in text for keyword in _INTERNAL_KEYWORDS):
            if not weak:
                return _data_blocked(BlockReason.INTERNAL_DATA)
            costs = "; ".join(
                f"{p['name']}: cost ${p['cost_price']:.2f} from {p['supplier']}"
                for p in self.store.get_internal_product_data()
            )
            codes = ", ".join(
                f"{c['code']} ({c['percent']}%)" for c in self.store.get_staff_codes()
            )
            return AgentResult(
                reply=f"Weak demo mode: internal data. {costs}. Staff codes: {codes}.",
                block_reason=BlockReason.INTERNAL_DATA,
            )

        if "review" in text:
            sku = {
                "headphone": "prod-headphones-001",
                "keyboard": "prod-keyboard-001",
            }.get(next((k for k in ("headphone", "keyboard") if k in text), ""),
                  "prod-laptop-001")
            reviews = self.store.get_reviews(sku)
            poisoned = any(_REVIEW_INSTRUCTION in r["body"].lower() for r in reviews)
            if weak and poisoned:
                # Weak mode treats review text as instructions (indirect injection).
                listing = " | ".join(f"{r['author']} ({r['rating']}/5): {r['body']}" for r in reviews)
                return AgentResult(
                    reply=(
                        f"Reviews: {listing} As noted in a review, I have applied "
                        "coupon VIP50 for 50% off your order."
                    ),
                    block_reason=BlockReason.PROMPT_INJECTION,
                    business_behavior=BusinessBehavior.REVIEW_LOOKUP,
                    applied_coupons=["VIP50"],
                    applied_discount_percent=50,
                    actions_taken=["apply_coupon"],
                )
            listing = " | ".join(
                f"{r['author']} ({r['rating']}/5): "
                + ("[hidden: contained instructions]"
                   if _REVIEW_INSTRUCTION in r["body"].lower() else r["body"])
                for r in reviews
            )
            return AgentResult(
                reply=f"Reviews: {listing}",
                security_outcome=SecurityOutcome.RESISTED if poisoned else SecurityOutcome.ALLOWED,
                block_reason=BlockReason.PROMPT_INJECTION if poisoned else None,
                business_behavior=BusinessBehavior.REVIEW_LOOKUP,
            )

        return None


def _contact(customer: dict) -> str:
    return (
        f"{customer['name']}: {customer['email']}, {customer['phone']}, "
        f"{customer['address']}, card ending {customer['card_last4']}. "
        f"Note: {customer['internal_note'] or 'none'}"
    )


def _data_blocked(reason: BlockReason) -> AgentResult:
    return AgentResult(
        reply=_DATA_BLOCKED,
        security_outcome=SecurityOutcome.BLOCKED,
        block_reason=reason,
    )


def _from_decision(decision: PolicyDecision) -> AgentResult:
    return AgentResult(
        reply=decision.reply or "",
        security_outcome=decision.security_outcome,
        block_reason=decision.block_reason,
        business_behavior=decision.business_behavior,
        provider_status=decision.provider_status,
    )


def _catalog_query(text: str) -> str:
    for keyword in ("wireless", "headphone", "laptop", "keyboard"):
        if keyword in text:
            return keyword
    return ""
