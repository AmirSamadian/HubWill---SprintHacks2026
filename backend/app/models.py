"""Stable API response models, independent of PostgreSQL table names."""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Period(str, Enum):
    day = "day"
    month = "month"
    year = "year"


class Totals(BaseModel):
    # Decimal values serialize as strings, preserving exact currency amounts.
    revenue: Decimal
    transactions: int
    units_sold: int
    average_selling_price: Decimal | None


class MarketplaceSummary(Totals):
    marketplace: str


class TrendPoint(BaseModel):
    bucket_start: date
    revenue: Decimal
    transactions: int


class EbayBuyers(BaseModel):
    scope: str = "ebay_only"
    unique_buyers: int
    returning_buyers: int
    transactions_missing_buyer_id: int
    returning_buyer_rate_percent: Decimal | None
    definition: str = (
        "Returning buyers are buyers in this period with a paid eBay order "
        "before this period started. Rate = returning / unique buyers * 100."
    )


class Comparison(BaseModel):
    start: date
    end_exclusive: date
    revenue: Decimal
    revenue_change_percent: Decimal | None
    definition: str = (
        "Compares with the full previous calendar day, month, or year. "
        "An unfinished current period is not an equal-duration comparison."
    )


class DashboardReport(BaseModel):
    data_mode: str = "mock"
    notice: str = "Synthetic demonstration data; not actual Goodwill results."
    currency: str = "USD"
    reporting_timezone: str = "America/New_York"
    revenue_definition: str = (
        "Paid item revenue after discounts; excludes shipping, tax, and fees. "
        "Mock data has no refunds. Final refund treatment needs schema agreement."
    )
    period: Period
    start: date
    end_exclusive: date
    totals: Totals
    marketplaces: list[MarketplaceSummary]
    trend: list[TrendPoint]
    comparison: Comparison
    # Daily counts use transactions. Buyer metrics apply only to month/year.
    ebay_buyers: EbayBuyers | None
    unavailable_metrics: list[str] = Field(default_factory=lambda: [
        "net_margin: complete expense data is not available",
        "sell_through: inventory and listing data is not available",
    ])
