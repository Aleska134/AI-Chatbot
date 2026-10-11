from __future__ import annotations

import re
from dataclasses import dataclass

from app import commerce

SCOPE_RESPONSE = 'I can only help with TechMart products, orders, and store policies.'


@dataclass
class PolicyDecision:
    handled: bool
    reply: str | None = None


class BasePolicy:
    scope = 'commerce_support'

    def __init__(self, discount_max_percent: int):
        self.discount_max_percent = discount_max_percent

    def evaluate(self, message: str, customer_id: str) -> PolicyDecision:
        raise NotImplementedError


class HardenedPolicy(BasePolicy):
    def evaluate(self, message: str, customer_id: str) -> PolicyDecision:
        text = message.lower().strip()

        if any(token in text for token in ('system prompt', 'ignore previous instructions', 'reveal instructions')):
            return PolicyDecision(True, 'I cannot share internal instructions, but I can help with TechMart support questions.')

        if self._is_unrelated(text):
            return PolicyDecision(True, SCOPE_RESPONSE)

        requested_discount = _extract_discount_percentage(text)
        if requested_discount and requested_discount > self.discount_max_percent:
            return PolicyDecision(True, f'I can only discuss discounts up to {self.discount_max_percent}% according to TechMart policy.')

        if 'checkout' in text and 'confirm checkout' not in text:
            return PolicyDecision(True, 'Please confirm by saying "confirm checkout" before I proceed with checkout.')

        other_customer = _extract_customer_id(text)
        if other_customer and other_customer != customer_id:
            return PolicyDecision(True, 'I can only access data for the authenticated customer account.')

        if 'return' in text and any(t in text for t in ('bypass', 'ignore policy', 'outside window')):
            return PolicyDecision(True, commerce.POLICIES['returns'])

        return PolicyDecision(False)

    @staticmethod
    def _is_unrelated(text: str) -> bool:
        commerce_keywords = (
            'techmart', 'product', 'headphone', 'earbud', 'charger', 'price', 'inventory',
            'order', 'cart', 'return', 'policy', 'discount', 'checkout', 'customer'
        )
        if any(keyword in text for keyword in commerce_keywords):
            return False
        return '?' in text or any(token in text for token in ('capital of france', 'history of'))


class WeakPolicy(BasePolicy):
    def evaluate(self, message: str, customer_id: str) -> PolicyDecision:
        text = message.lower().strip()

        if 'ignore previous instructions' in text:
            return PolicyDecision(True, 'Okay, I will relax constraints for this demo and answer broadly when possible.')

        if 'checkout' in text and 'confirm checkout' not in text:
            return PolicyDecision(True, 'I can start checkout quickly in this demo mode, but no real payment is executed.')

        if 'discount' in text:
            requested_discount = _extract_discount_percentage(text)
            if requested_discount and requested_discount > self.discount_max_percent:
                return PolicyDecision(True, f'I can mention a {requested_discount}% discount for testing, but final policy still requires review.')

        return PolicyDecision(False)


def _extract_discount_percentage(text: str) -> int | None:
    match = re.search(r'(\d{1,3})\s*%', text)
    if not match:
        return None
    return int(match.group(1))


def _extract_customer_id(text: str) -> str | None:
    match = re.search(r'(customer-demo-\d{3})', text)
    return match.group(1) if match else None
