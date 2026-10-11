from __future__ import annotations

from dataclasses import dataclass

from app import commerce
from app.config import Settings
from app.policies import HardenedPolicy, WeakPolicy, BasePolicy


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    reply: str
    provider_status: str = 'deterministic'


class MerchantAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.policy: BasePolicy = (
            HardenedPolicy(settings.discount_max_percent)
            if settings.chatbot_mode == 'hardened'
            else WeakPolicy(settings.discount_max_percent)
        )

    def respond(self, message: str, customer_id: str) -> AgentResult:
        decision = self.policy.evaluate(message, customer_id)
        if decision.handled and decision.reply:
            return AgentResult(decision.reply)

        try:
            return self._business_response(message, customer_id)
        except ProviderError:
            return AgentResult(
                'I am temporarily unable to process provider-backed generation. I can still help with TechMart catalog, orders, and policies.',
                provider_status='fallback',
            )

    def _business_response(self, message: str, customer_id: str) -> AgentResult:
        text = message.lower()

        if 'trigger provider failure' in text:
            raise ProviderError('simulated provider error')

        if 'wireless headphones' in text or 'wireless' in text:
            products = commerce.list_wireless_products()
            product_lines = ', '.join(
                f'{p.name} (${p.price:.2f}, inventory: {p.inventory})' for p in products
            )
            return AgentResult(f'Here are the available wireless headphones and accessories: {product_lines}.')

        if 'price' in text or 'inventory' in text or 'product' in text:
            query = 'wireless' if 'wireless' in text else 'techmart'
            products = commerce.search_products(query)
            if not products:
                return AgentResult('I could not find matching products in the TechMart mock catalog.')
            line = '; '.join(f'{p.name} - ${p.price:.2f} ({p.inventory} in stock)' for p in products)
            return AgentResult(f'TechMart catalog results: {line}.')

        if 'order' in text:
            orders = commerce.get_orders_for_customer(customer_id)
            if not orders:
                return AgentResult('No mock orders were found for this customer.')
            formatted = ', '.join(f"{o['order_id']} ({o['status']})" for o in orders)
            return AgentResult(f'Your mock orders: {formatted}.')

        if 'cart' in text:
            cart = commerce.get_cart_for_customer(customer_id)
            return AgentResult(f'Your mock cart currently has {len(cart)} item(s).')

        if 'return' in text or 'policy' in text:
            return AgentResult(commerce.POLICIES['returns'])

        if self.settings.chatbot_mode == 'weak':
            if 'capital of france' in text:
                return AgentResult('It sounds like a general question. The capital of France is Paris, and it has a long historical legacy.')
            return AgentResult('In weak mode I can discuss broader topics, but this is still a local mock commerce bot.')

        return AgentResult('How can I help with TechMart products, orders, or store policies today?')
