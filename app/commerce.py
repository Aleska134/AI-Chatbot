from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: float
    inventory: int


PRODUCTS: tuple[Product, ...] = (
    Product('sku-001', 'TechMart Wireless Headphones Pro', 'audio', 129.99, 12),
    Product('sku-002', 'TechMart Wireless Earbuds Lite', 'audio', 59.99, 28),
    Product('sku-003', 'TechMart USB-C Fast Charger', 'accessories', 24.99, 100),
)

CUSTOMERS: dict[str, dict[str, str]] = {
    'customer-demo-001': {'name': 'Alex Carter', 'email': 'alex.demo@techmart.local'},
    'customer-demo-002': {'name': 'Jordan Lee', 'email': 'jordan.demo@techmart.local'},
}

CARTS: dict[str, list[dict[str, object]]] = {
    'customer-demo-001': [{'sku': 'sku-001', 'quantity': 1}],
    'customer-demo-002': [{'sku': 'sku-003', 'quantity': 2}],
}

ORDERS: dict[str, list[dict[str, object]]] = {
    'customer-demo-001': [{'order_id': 'order-1001', 'status': 'processing', 'total': 129.99}],
    'customer-demo-002': [{'order_id': 'order-1002', 'status': 'delivered', 'total': 49.98}],
}

POLICIES: dict[str, str] = {
    'returns': 'Returns are accepted within 30 days with proof of purchase.',
    'discounts': 'Maximum manual discount is 20% and needs approval.',
    'checkout': 'Checkout requires explicit customer confirmation.',
}


def search_products(query: str) -> list[Product]:
    normalized = query.lower()
    return [p for p in PRODUCTS if normalized in p.name.lower() or normalized in p.category.lower()]


def list_wireless_products() -> list[Product]:
    return [p for p in PRODUCTS if 'wireless' in p.name.lower()]


def get_orders_for_customer(customer_id: str) -> list[dict[str, object]]:
    return ORDERS.get(customer_id, [])


def get_cart_for_customer(customer_id: str) -> list[dict[str, object]]:
    return CARTS.get(customer_id, [])
