"""Read stored facts for reports. PostgreSQL in the app; small fixtures in tests.

Both sources return the same Snapshot, so every report, API response and email
runs through the same calculations in dashboard.py.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass
class Snapshot:
    sources: list[dict]  # source_id, name
    orders: list[dict]  # sales_order + sales_order_mv fields, with local 'day'
    lines: list[dict]  # order_item fields with category names
    listings: list[dict]  # listing_id, local 'day' listed
    data_mode: str = 'database'


class OrderRepository(Protocol):
    def snapshot(self, timezone: str) -> Snapshot:
        """Return stored facts; dates are converted to the reporting timezone."""
        ...


class DatabaseUnavailable(RuntimeError):
    """A public-safe error that never includes a connection string or password."""


class PostgresRepository:
    def __init__(self, connect=None):
        # Injection is used only by isolated database tests.
        self._connect = connect

    def snapshot(self, timezone: str) -> Snapshot:
        import psycopg
        from psycopg.rows import dict_row
        from . import config  # noqa: F401  Load the root .env before libpq reads PG* variables.

        try:
            connect = self._connect or psycopg.connect
            with connect(row_factory=dict_row, connect_timeout=5) as connection:
                # One consistent, read-only view of the data for the whole report.
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
                           c.category_id, c.name AS category_name,
                           parent.name AS parent_category_name
                    FROM public.order_item oi
                    JOIN public.listing l USING (listing_id)
                    JOIN public.product p USING (product_id)
                    JOIN public.category c ON c.category_id = p.category_id
                    LEFT JOIN public.category parent ON parent.category_id = c.parent_category_id
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
            merchandise, refund = totals.get(line['order_id'], (Decimal(0), Decimal(0)))
            totals[line['order_id']] = (
                merchandise + line['quantity'] * line['unit_price'] - line['discount_amount'],
                refund - line['refund_amount'],
            )
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


# ---------------------------------------------------------------- test fixtures

@dataclass(frozen=True)
class PaidOrder:
    # IDs are scoped to a marketplace; different channels may reuse the same ID.
    order_id: str
    marketplace: str
    reporting_date: date
    item_revenue: Decimal
    units: int
    ebay_buyer_id: str | None = None


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

_SOURCE_NAMES = {"shopgoodwill": "ShopGoodwill", "amazon": "Amazon", "ebay": "eBay"}


@dataclass
class MockOrderRepository:
    """Small in-memory fixture shaped like the database: no shipping, tax,
    fees, refunds or listings, one line per order."""

    orders: tuple[PaidOrder, ...] = MOCK_ORDERS
    listings: list[dict] = field(default_factory=list)

    def snapshot(self, timezone: str) -> Snapshot:
        names = list(_SOURCE_NAMES) + sorted({o.marketplace for o in self.orders} - set(_SOURCE_NAMES))
        source_ids = {name: index + 1 for index, name in enumerate(names)}
        sources = [{'source_id': source_ids[n], 'name': _SOURCE_NAMES.get(n, n)} for n in names]
        orders, lines = [], []
        for index, order in enumerate(self.orders, start=1):
            orders.append({
                'order_id': index, 'source_id': source_ids[order.marketplace],
                'customer_id': order.ebay_buyer_id, 'status': 'COMPLETED', 'day': order.reporting_date,
                'shipping_charge_amount': Decimal(0), 'shipping_cost_amount': Decimal(0),
                'tax_amount': Decimal(0), 'operation_fee_amount': Decimal(0),
                'materialized_order_id': index, 'merchandise_revenue': order.item_revenue,
                'refund_impact': Decimal(0), 'total_transaction_revenue': order.item_revenue,
            })
            lines.append({
                'order_id': index, 'quantity': order.units, 'unit_price': order.item_revenue / order.units,
                'discount_amount': Decimal(0), 'refund_amount': Decimal(0),
                'category_id': 1, 'category_name': 'Uncategorized', 'parent_category_name': None,
            })
        return Snapshot(sources, orders, lines, list(self.listings), data_mode='mock')
