"""Data source boundary: later replace mock orders with a PostgreSQL query."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class PaidOrder:
    # IDs are scoped to a marketplace; different channels may reuse the same ID.
    order_id: str
    marketplace: str
    reporting_date: date
    item_revenue: Decimal
    units: int
    ebay_buyer_id: str | None = None


class OrderRepository(Protocol):
    def paid_orders_before(self, end_exclusive: date) -> tuple[PaidOrder, ...]:
        """Return paid orders, including history needed for buyer comparisons."""
        ...


def mock_order(
    order_id: str, marketplace: str, day: str, revenue: str,
    units: int = 1, buyer: str | None = None,
) -> PaidOrder:
    return PaidOrder(order_id, marketplace, date.fromisoformat(day), Decimal(revenue), units, buyer)


MOCK_ORDERS = (
    mock_order("old-1", "ebay", "2025-09-10", "80.00", buyer="buyer-a"),
    mock_order("old-2", "amazon", "2025-10-03", "120.00", units=2),
    mock_order("aug-1", "ebay", "2026-08-10", "40.00", buyer="buyer-a"),
    mock_order("aug-2", "shopgoodwill", "2026-08-20", "160.00", units=4),
    mock_order("sep-1", "ebay", "2026-09-01", "50.00", buyer="buyer-a"),
    mock_order("sep-2", "ebay", "2026-09-15", "30.00", buyer="buyer-b"),
    mock_order("sep-3", "ebay", "2026-09-20", "20.00", buyer="buyer-b"),
    mock_order("sep-4", "amazon", "2026-09-30", "100.00", units=2),
    mock_order("sep-5", "shopgoodwill", "2026-09-30", "200.00", units=4),
    mock_order("oct-1", "ebay", "2026-10-02", "40.00", buyer="buyer-a"),
    mock_order("1001", "ebay", "2026-10-03", "60.00", units=2, buyer="buyer-b"),
    mock_order("1001", "amazon", "2026-10-03", "90.00", units=3),
    mock_order("oct-4", "shopgoodwill", "2026-10-03", "150.00", units=3),
    mock_order("oct-5", "goodwillbooks", "2026-10-03", "25.00"),
)


class MockOrderRepository:
    def __init__(self, orders: tuple[PaidOrder, ...] = MOCK_ORDERS) -> None:
        self.orders = orders

    def paid_orders_before(self, end_exclusive: date) -> tuple[PaidOrder, ...]:
        return tuple(order for order in self.orders if order.reporting_date < end_exclusive)


# Swapping this repository is the integration point for the team's SQL schema.
repository: OrderRepository = MockOrderRepository()
