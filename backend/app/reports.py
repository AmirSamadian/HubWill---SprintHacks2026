"""Calendar windows and report calculations shared by the dashboard and future email."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    Comparison, DashboardReport, EbayBuyers, MarketplaceSummary, Period,
    Totals, TrendPoint,
)
from .repository import OrderRepository, PaidOrder


def next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def report_window(period: Period, selected: date) -> tuple[date, date, date]:
    """Return start, exclusive end, and previous comparable calendar period start."""
    if not 2 <= selected.year <= 9998:
        raise ValueError("Choose a date between years 2 and 9998 to allow period comparisons.")
    if period == Period.day:
        return selected, selected + timedelta(days=1), selected - timedelta(days=1)
    if period == Period.month:
        start = selected.replace(day=1)
        previous = (start - timedelta(days=1)).replace(day=1)
        return start, next_month(start), previous
    start = date(selected.year, 1, 1)
    return start, date(selected.year + 1, 1, 1), date(selected.year - 1, 1, 1)


def rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def totals(orders: tuple[PaidOrder, ...]) -> Totals:
    revenue = sum((order.item_revenue for order in orders), Decimal("0.00"))
    units = sum(order.units for order in orders)
    return Totals(
        revenue=rounded(revenue), transactions=len(orders), units_sold=units,
        average_selling_price=rounded(revenue / units) if units else None,
    )


def build_report(period: Period, selected: date, repository: OrderRepository) -> DashboardReport:
    start, end, previous_start = report_window(period, selected)
    history = repository.paid_orders_before(end)
    current = tuple(order for order in history if start <= order.reporting_date < end)
    previous = tuple(order for order in history if previous_start <= order.reporting_date < start)
    current_totals, previous_totals = totals(current), totals(previous)

    # Full calendar periods: month compares to previous month, year to previous year.
    # If a period is still underway, its comparison is not an equal-duration comparison.
    change = None
    if previous_totals.revenue:
        change = rounded((current_totals.revenue - previous_totals.revenue) / previous_totals.revenue * 100)

    marketplaces = []
    named_marketplaces = ("shopgoodwill", "amazon", "ebay")
    for marketplace in (*named_marketplaces, "other"):
        # Keep vendor names in source records, but combine all remaining vendors
        # into one Other row. Each order contributes to exactly one report row.
        subset = tuple(
            order for order in current
            if (order.marketplace not in named_marketplaces if marketplace == "other"
                else order.marketplace == marketplace)
        )
        marketplaces.append(MarketplaceSummary(marketplace=marketplace, **totals(subset).model_dump()))

    trend = []
    cursor = start
    while cursor < end:
        bucket_end = next_month(cursor) if period == Period.year else cursor + timedelta(days=1)
        subset = tuple(order for order in current if cursor <= order.reporting_date < bucket_end)
        summary = totals(subset)
        # Include empty buckets so charts preserve dates with no sales.
        trend.append(TrendPoint(bucket_start=cursor, revenue=summary.revenue, transactions=summary.transactions))
        cursor = bucket_end

    buyers = None
    if period != Period.day:
        buyer_ids = {order.ebay_buyer_id for order in current if order.marketplace == "ebay" and order.ebay_buyer_id}
        prior_ids = {
            order.ebay_buyer_id for order in history
            if order.marketplace == "ebay" and order.reporting_date < start and order.ebay_buyer_id
        }
        returning = len(buyer_ids & prior_ids)
        buyers = EbayBuyers(
            unique_buyers=len(buyer_ids), returning_buyers=returning,
            transactions_missing_buyer_id=sum(
                1 for order in current if order.marketplace == "ebay" and not order.ebay_buyer_id
            ),
            returning_buyer_rate_percent=rounded(Decimal(returning) / len(buyer_ids) * 100) if buyer_ids else None,
        )

    return DashboardReport(
        period=period, start=start, end_exclusive=end,
        totals=current_totals, marketplaces=marketplaces, trend=trend,
        comparison=Comparison(
            start=previous_start, end_exclusive=start, revenue=previous_totals.revenue,
            revenue_change_percent=change,
        ),
        ebay_buyers=buyers,
    )
