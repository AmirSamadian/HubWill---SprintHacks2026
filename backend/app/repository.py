"""PostgreSQL facts for application requests; mock orders remain test fixtures."""

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


class DatabaseUnavailable(RuntimeError):
    """A public-safe error that never includes a connection string or password."""


@dataclass
class Snapshot:
    sources: list[dict]
    orders: list[dict]
    lines: list[dict]
    listings: list[dict]


class PostgresRepository:
    def __init__(self, connect=None):
        # Injection is used only by isolated database tests.
        self._connect = connect

    def snapshot(self, timezone: str) -> Snapshot:
        import psycopg
        from psycopg.rows import dict_row
        from . import config  # Load the root .env before libpq reads PG* variables.

        try:
            connect = self._connect or psycopg.connect
            with connect(row_factory=dict_row, connect_timeout=5) as connection:
                connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                connection.execute("SET LOCAL statement_timeout = '15s'")
                sources = connection.execute(
                    'SELECT source_id, name FROM public.source ORDER BY source_id'
                ).fetchall()
                orders = connection.execute('''
                    SELECT o.order_id, o.source_id, o.customer_id, o.status,
                           (o.ordered_at AT TIME ZONE %s)::date AS day,
                           o.shipping_charge_amount, o.shipping_cost_amount,
                           o.tax_amount, o.operation_fee_amount,
                           mv.order_id AS materialized_order_id,
                           mv.merchandise_revenue, mv.refund_impact,
                           mv.total_transaction_revenue
                    FROM public.sales_order o
                    LEFT JOIN public.sales_order_mv mv USING (order_id)
                ''', (timezone,)).fetchall()
                lines = connection.execute('''
                    SELECT oi.order_id, oi.quantity, oi.unit_price,
                           oi.discount_amount, oi.refund_amount,
                           c.category_id, c.name AS category_name
                    FROM public.order_item oi
                    JOIN public.listing l USING (listing_id)
                    JOIN public.product p USING (product_id)
                    JOIN public.category c USING (category_id)
                ''').fetchall()
                listings = connection.execute('''
                    SELECT listing_id, (listed_at AT TIME ZONE %s)::date AS day
                    FROM public.listing
                ''', (timezone,)).fetchall()
            self._check_materialized_totals(orders, lines)
            return Snapshot(sources, orders, lines, listings)
        except psycopg.Error:
            raise DatabaseUnavailable(
                'Database unavailable. Check local PostgreSQL settings and apply database migrations.'
            ) from None

    @staticmethod
    def _check_materialized_totals(orders, lines):
        # Never refresh or write during a report request. Detect stale aggregates
        # instead of combining old financial totals with newly imported lines.
        totals = {}
        for line in lines:
            merchandise, refund = totals.setdefault(line['order_id'], [Decimal(0), Decimal(0)])
            totals[line['order_id']] = [
                merchandise + line['quantity'] * line['unit_price'] - line['discount_amount'],
                refund - line['refund_amount'],
            ]
        for order in orders:
            amounts = totals.get(order['order_id'])
            merchandise, refund = amounts if amounts else (None, None)
            revenue = (merchandise + refund + order['shipping_charge_amount']
                       - order['shipping_cost_amount'] - order['operation_fee_amount']) if amounts else None
            if (order['materialized_order_id'] is None
                    or order['merchandise_revenue'] != merchandise
                    or order['refund_impact'] != refund
                    or order['total_transaction_revenue'] != revenue):
                raise DatabaseUnavailable(
                    'Order totals need refreshing after ingestion: REFRESH MATERIALIZED VIEW public.sales_order_mv;'
                )


repository = PostgresRepository()
