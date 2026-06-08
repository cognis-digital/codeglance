"""Configuration leaf module — no internal dependencies."""
from dataclasses import dataclass


@dataclass
class Settings:
    currency: str = "USD"
    max_order_total: float = 10000.0
    free_shipping_threshold: float = 50.0
