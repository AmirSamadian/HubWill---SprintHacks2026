"""DashboardReport (the /api/dashboard and monthly email contract), built from
the shared calculations in dashboard.py so every output reports the same numbers."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .dashboard import NAMED_MARKETPLACES, ReportData, change, marketplace_key
from .models import (
    Comparison, DashboardReport, EbayBuyers, MarketplaceSummary, Period,
    Totals, TrendPoint,
)
from .repository import OrderRepository


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


def rounded(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def totals(data: ReportData, orders) -> Totals:
    summary = data.summary(orders)
    # Revenue is None (unavailable) if an order has no items; never shown as zero.
    return Totals(
        revenue=rounded(summary["revenue"]),
        transactions=summary["transactions"], units_sold=summary["units"],
        average_selling_price=rounded(summary["average_selling_price"]),
    )


def build_report(period: Period, selected: date, repository: OrderRepository, data: ReportData | None = None) -> DashboardReport:
    data = data or ReportData(repository.snapshot(_timezone()))
    start, end, previous_start = report_window(period, selected)
    current = data.orders_between(start, end)
    previous = data.orders_between(previous_start, start)
    current_totals, previous_totals = totals(data, current), totals(data, previous)

    # Full calendar periods: month compares to previous month, year to previous year.
    # If a period is still underway, its comparison is not an equal-duration comparison.
    growth = change(current_totals.revenue, previous_totals.revenue)
    marketplaces = []
    for marketplace in (*NAMED_MARKETPLACES, "other"):
        # Every source outside the three named marketplaces is combined into Other.
        subset = [o for o in current if marketplace_key(data.source_by_id[o["source_id"]]["name"]) == marketplace]
        marketplaces.append(MarketplaceSummary(marketplace=marketplace, **totals(data, subset).model_dump()))

    trend = []
    cursor = start
    while cursor < end:
        bucket_end = next_month(cursor) if period == Period.year else cursor + timedelta(days=1)
        summary = totals(data, data.orders_between(cursor, bucket_end))
        # Include empty buckets so charts preserve dates with no sales.
        trend.append(TrendPoint(bucket_start=cursor, revenue=summary.revenue, transactions=summary.transactions))
        cursor = bucket_end

    buyers = None
    if period != Period.day:
        figures = data.ebay_buyers(current, start)
        rate = figures["repeatBuyerRate"]
        buyers = EbayBuyers(
            unique_buyers=figures["buyers"], returning_buyers=figures["repeatBuyers"],
            transactions_missing_buyer_id=figures["missingBuyerOrders"],
            returning_buyer_rate_percent=rounded(rate * 100) if rate is not None else None,
        )

    report = DashboardReport(
        period=period, start=start, end_exclusive=end,
        totals=current_totals, marketplaces=marketplaces, trend=trend,
        comparison=Comparison(
            start=previous_start, end_exclusive=start, revenue=previous_totals.revenue,
            revenue_change_percent=rounded(growth * 100) if growth is not None else None,
        ),
        ebay_buyers=buyers,
        data_mode=data.snapshot.data_mode,
        reporting_timezone=data.config.reporting_timezone,
        revenue_definition=data.config.revenue_definition,
        unavailable_metrics=[
            "net_margin: cost-of-goods and expense data are not stored",
            "sell_through: the listing cohort definition is not agreed",
        ],
    )
    if data.snapshot.data_mode == "database":
        report.notice = "Figures from stored database records."
    return report


def _timezone() -> str:
    from .config import settings
    return settings().reporting_timezone
