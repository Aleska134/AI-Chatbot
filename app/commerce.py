"""Deterministic mock commerce data and operations for TechMart.

Everything here is in-memory mock data for safe local testing. There are no
real customers, no real payments, and no external side effects. The catalog is
intentionally aligned with the external security testing platform so both
systems describe the same store.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from app.domain import (
    MAX_DISCOUNT_PERCENT,
    RETURN_WINDOW_DAYS,
    STANDARD_COUPON_CODE,
    STORE_NAME,
)


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: float
    inventory: int


# Catalog aligned with the security testing platform (laptop, headphones, keyboard).
_SEED_PRODUCTS: tuple[Product, ...] = (
    Product("prod-laptop-001", f"{STORE_NAME} Pro Laptop", "computers", 1299.99, 8),
    Product(
        "prod-headphones-001",
        f"{STORE_NAME} Wireless Headphones",
        "audio",
        149.99,
        20,
    ),
    Product(
        "prod-keyboard-001",
        f"{STORE_NAME} Mechanical Keyboard",
        "accessories",
        89.99,
        15,
    ),
)

CUSTOMERS: dict[str, dict[str, str]] = {
    "customer-demo-001": {"name": "Alex Carter", "email": "alex.demo@techmart.local"},
    "customer-demo-002": {"name": "Jordan Lee", "email": "jordan.demo@techmart.local"},
}

POLICIES: dict[str, str] = {
    "returns": f"Returns are accepted within {RETURN_WINDOW_DAYS} days with proof of purchase.",
    "discounts": (
        f"The maximum discount is {MAX_DISCOUNT_PERCENT}% using coupon "
        f"{STANDARD_COUPON_CODE}, and larger discounts require approval."
    ),
    "checkout": "Checkout requires explicit customer confirmation.",
}


class MockStore:
    """A deterministic, per-instance mock store.

    State (inventory, carts, orders) lives in memory and resets when the store
    is recreated, which keeps tests isolated and deterministic. Nothing here
    touches an external system.
    """

    def __init__(self) -> None:
        self._products: dict[str, Product] = {p.sku: p for p in _SEED_PRODUCTS}
        self._carts: dict[str, list[dict[str, object]]] = {
            "customer-demo-001": [{"sku": "prod-headphones-001", "quantity": 1}],
            "customer-demo-002": [{"sku": "prod-keyboard-001", "quantity": 2}],
        }
        self._orders: dict[str, list[dict[str, object]]] = {
            "customer-demo-001": [
                {"order_id": "order-1001", "status": "processing", "total": 149.99}
            ],
            "customer-demo-002": [
                {"order_id": "order-1002", "status": "delivered", "total": 179.98}
            ],
        }
        self._order_counter = 1002

    # --- Customer identity -------------------------------------------------

    @staticmethod
    def is_known_customer(customer_id: str) -> bool:
        return customer_id in CUSTOMERS

    # --- Catalog -----------------------------------------------------------

    def all_products(self) -> list[Product]:
        return list(self._products.values())

    def search_products(self, query: str) -> list[Product]:
        normalized = query.strip().lower()
        if not normalized:
            return self.all_products()
        return [
            p
            for p in self._products.values()
            if normalized in p.name.lower() or normalized in p.category.lower()
        ]

    def list_wireless_products(self) -> list[Product]:
        return [p for p in self._products.values() if "wireless" in p.name.lower()]

    def get_product(self, sku: str) -> Product | None:
        return self._products.get(sku)

    # --- Orders and carts (scoped to one customer) -------------------------

    def get_orders_for_customer(self, customer_id: str) -> list[dict[str, object]]:
        return copy.deepcopy(self._orders.get(customer_id, []))

    def get_cart_for_customer(self, customer_id: str) -> list[dict[str, object]]:
        return copy.deepcopy(self._carts.get(customer_id, []))

    def cart_item_count(self, customer_id: str) -> int:
        return sum(int(item["quantity"]) for item in self._carts.get(customer_id, []))

    # --- Checkout (deterministic, no real payment) -------------------------

    def checkout(self, customer_id: str, coupon_code: str | None = None) -> dict[str, object]:
        """Complete a deterministic mock checkout for the customer's own cart.

        Decrements local inventory and records a mock order. Never contacts a
        payment provider. Returns a result describing what happened.
        """
        cart = self._carts.get(customer_id, [])
        if not cart:
            return {"completed": False, "reason": "empty_cart", "order_id": None}

        # Validate inventory locally.
        for item in cart:
            product = self._products.get(str(item["sku"]))
            if product is None or int(item["quantity"]) > product.inventory:
                return {
                    "completed": False,
                    "reason": "insufficient_inventory",
                    "order_id": None,
                }

        subtotal = 0.0
        for item in cart:
            product = self._products[str(item["sku"])]
            subtotal += product.price * int(item["quantity"])
            # Deterministic local inventory decrement.
            self._products[product.sku] = Product(
                product.sku,
                product.name,
                product.category,
                product.price,
                product.inventory - int(item["quantity"]),
            )

        discount_percent = (
            MAX_DISCOUNT_PERCENT if coupon_code == STANDARD_COUPON_CODE else 0
        )
        total = round(subtotal * (1 - discount_percent / 100), 2)

        self._order_counter += 1
        order_id = f"order-{self._order_counter}"
        self._orders.setdefault(customer_id, []).append(
            {"order_id": order_id, "status": "paid", "total": total}
        )
        # The cart becomes empty after checkout (a fresh open cart).
        self._carts[customer_id] = []

        return {
            "completed": True,
            "reason": "completed",
            "order_id": order_id,
            "total": total,
            "discount_percent": discount_percent,
        }
