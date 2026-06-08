"""Business logic — the central, branchy module. Depends on models + config."""
from typing import List, Optional

from .config import Settings
from .models import Order, Customer


class OrderService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or Settings()
        self._orders: List[Order] = []

    def validate(self, order: Order) -> List[str]:
        errors: List[str] = []
        if not order.items:
            errors.append("empty order")
        if order.total() <= 0:
            errors.append("non-positive total")
        if order.total() > self.settings.max_order_total:
            errors.append("exceeds max order total")
        for price in order.items:
            if price < 0:
                errors.append("negative line item")
                break
        return errors

    def place(self, order: Order) -> dict:
        errors = self.validate(order)
        if errors:
            return {"ok": False, "errors": errors}
        shipping = 0.0 if order.is_free_shipping(self.settings) else 5.0
        if order.customer.vip:
            shipping = 0.0
        self._orders.append(order)
        return {
            "ok": True,
            "total": order.total() + shipping,
            "shipping": shipping,
            "currency": self.settings.currency,
        }


def place_order(customer: Customer, items: List[float]) -> dict:
    return OrderService().place(Order(customer=customer, items=items))
