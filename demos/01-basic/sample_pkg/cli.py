"""Thin entry point. Depends on service."""
import sys

from .service import place_order
from .models import Customer


def main() -> int:
    customer = Customer(name="Ada", email="ada@example.com")
    items = [float(a) for a in sys.argv[1:]] or [19.99, 5.0]
    result = place_order(customer, items)
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
