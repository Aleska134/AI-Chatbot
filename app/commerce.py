"""Deterministic mock commerce data and operations for TechMart.

Data lives in a seeded in-memory SQLite database (see ``app.mock_data``). There
are no real customers, no real payments, and no external side effects. The catalog is
intentionally aligned with the external security testing platform so both
systems describe the same store.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from app.mock_data import build_database

from app.domain import (
    MAX_DISCOUNT_PERCENT,
    RETURN_WINDOW_DAYS,
    STANDARD_COUPON_CODE,
)


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: float
    inventory: int


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
        self.db = build_database()
        self._carts: dict[str, list[dict[str, object]]] = {
            "customer-demo-001": [{"sku": "prod-headphones-001", "quantity": 1}],
            "customer-demo-002": [{"sku": "prod-keyboard-001", "quantity": 2}],
        }
        self._order_counter = 1100

    # --- Customer identity -------------------------------------------------

    def is_known_customer(self, customer_id: str) -> bool:
        return self.get_customer(customer_id) is not None

    def get_customer(self, customer_id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_customers_named_in(self, text: str) -> list[dict]:
        """Customers whose full name appears in the text (case-insensitive)."""
        rows = self.db.execute("SELECT * FROM customers").fetchall()
        return [dict(r) for r in rows if r["name"].lower() in text.lower()]

    # --- Catalog -----------------------------------------------------------

    def _products(self) -> dict[str, Product]:
        rows = self.db.execute(
            "SELECT sku, name, category, price, inventory FROM products"
        ).fetchall()
        return {r["sku"]: Product(*r) for r in rows}

    def all_products(self) -> list[Product]:
        return list(self._products().values())

    def search_products(self, query: str) -> list[Product]:
        normalized = query.strip().lower()
        if not normalized:
            return self.all_products()
        return [
            p
            for p in self._products().values()
            if normalized in p.name.lower() or normalized in p.category.lower()
        ]

    def list_wireless_products(self) -> list[Product]:
        return [p for p in self._products().values() if "wireless" in p.name.lower()]

    def get_product(self, sku: str) -> Product | None:
        return self._products().get(sku)

    def get_internal_product_data(self) -> list[dict]:
        """Confidential cost prices and suppliers (staff only)."""
        rows = self.db.execute("SELECT name, cost_price, supplier FROM products")
        return [dict(r) for r in rows.fetchall()]

    def get_reviews(self, sku: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM reviews WHERE sku = ?", (sku,))
        return [dict(r) for r in rows.fetchall()]

    def get_staff_codes(self) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM staff_codes")]

    # --- Orders and carts (scoped to one customer) -------------------------

    def get_orders_for_customer(self, customer_id: str) -> list[dict[str, object]]:
        rows = self.db.execute(
            "SELECT order_id, status, total FROM orders WHERE customer_id = ? "
            "ORDER BY order_id", (customer_id,)
        )
        return [dict(r) for r in rows.fetchall()]

    def get_order(self, order_id: str) -> dict | None:
        """Look up any order by id. Callers must enforce ownership."""
        row = self.db.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        return dict(row) if row else None

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
        products = self._products()
        for item in cart:
            product = products.get(str(item["sku"]))
            if product is None or int(item["quantity"]) > product.inventory:
                return {
                    "completed": False,
                    "reason": "insufficient_inventory",
                    "order_id": None,
                }

        subtotal = 0.0
        for item in cart:
            product = products[str(item["sku"])]
            subtotal += product.price * int(item["quantity"])
            # Deterministic local inventory decrement.
            self.db.execute(
                "UPDATE products SET inventory = inventory - ? WHERE sku = ?",
                (int(item["quantity"]), product.sku),
            )

        discount_percent = (
            MAX_DISCOUNT_PERCENT if coupon_code == STANDARD_COUPON_CODE else 0
        )
        total = round(subtotal * (1 - discount_percent / 100), 2)

        self._order_counter += 1
        order_id = f"order-{self._order_counter}"
        customer = self.get_customer(customer_id) or {}
        self.db.execute(
            "INSERT INTO orders VALUES (?, ?, 'paid', ?, ?)",
            (order_id, customer_id, total, customer.get("address", "")),
        )
        self.db.commit()
        # The cart becomes empty after checkout (a fresh open cart).
        self._carts[customer_id] = []

        return {
            "completed": True,
            "reason": "completed",
            "order_id": order_id,
            "total": total,
            "discount_percent": discount_percent,
        }
