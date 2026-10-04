"""Local settings shared by the API and scheduler; never expose credentials."""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# Explicit environment variables take priority over the git-ignored root file.
# libpq reads the PG* connection variables (PGHOST, PGDATABASE, PGUSER, ...).
load_dotenv(ROOT / '.env', override=False)

# The team has not finalized which revenue definition dashboards show
# (DATABASE_SPEC §9 "Dashboard Revenue"). The default follows the documented
# backend contract: paid item revenue after discounts, excluding shipping, tax
# and fees. Refund treatment is still open, so refunds are not subtracted unless
# merchandise_after_refunds is chosen.
REVENUE_METRICS = {
    'merchandise_before_refunds': (
        'Item revenue after discounts, before refunds; excludes shipping, tax and fees.'
    ),
    'merchandise_after_refunds': (
        'Item revenue after discounts and refunds; excludes shipping, tax and fees.'
    ),
    'transaction_revenue': (
        'Transaction revenue: item revenue after discounts and refunds + buyer shipping '
        '- carrier cost - marketplace fees; tax excluded.'
    ),
}


@dataclass(frozen=True)
class Settings:
    reporting_timezone: str
    revenue_metric: str

    def __post_init__(self):
        ZoneInfo(self.reporting_timezone)
        if self.revenue_metric not in REVENUE_METRICS:
            raise ValueError('Set DASHBOARD_REVENUE_METRIC to one of: ' + ', '.join(REVENUE_METRICS))

    @property
    def revenue_definition(self) -> str:
        return REVENUE_METRICS[self.revenue_metric]


def settings() -> Settings:
    return Settings(
        # Goodwill Michiana (St. Joseph County, Indiana) observes US Eastern time.
        reporting_timezone=os.environ.get('REPORTING_TIMEZONE', 'America/New_York'),
        revenue_metric=os.environ.get('DASHBOARD_REVENUE_METRIC', 'merchandise_before_refunds'),
    )


def allowed_origins() -> list[str]:
    configured = os.environ.get('DASHBOARD_ALLOWED_ORIGINS', '')
    return [origin.strip() for origin in configured.split(',') if origin.strip()]
