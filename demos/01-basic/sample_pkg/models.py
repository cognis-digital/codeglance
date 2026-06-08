"""Domain models. Depends on config."""
from dataclasses import dataclass, field
from typing import List

from .config import Settings


@dataclass
class Customer:
    name: str
    email: str
    vip: bool = False


@dataclass
class Order:
    customer: Customer
    items: List[float] = field(default_factory=list)

    def total(self) -> float:
        return sum(self.items)

    def is_free_shipping(self, settings: Settings) -> bool:
        return self.total() >= settings.free_shipping_threshold
