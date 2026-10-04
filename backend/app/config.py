"""Local settings shared by the API and scheduler; never expose credentials."""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
# Explicit environment variables take priority over the git-ignored root file.
load_dotenv(ROOT / '.env', override=False)


@dataclass(frozen=True)
class Settings:
    reporting_timezone: str
    revenue_metric: str

    def __post_init__(self):
        ZoneInfo(self.reporting_timezone)
        if self.revenue_metric not in {
            'merchandise_before_refunds', 'merchandise_after_refunds', 'transaction_revenue',
        }:
            raise ValueError('Set DASHBOARD_REVENUE_METRIC to an agreed revenue definition.')


def settings() -> Settings:
    return Settings(
        reporting_timezone=os.environ.get('REPORTING_TIMEZONE', 'America/New_York'),
        revenue_metric='transaction_revenue',
    )
