"""Verify calendar boundaries and business calculations against small fixtures."""

import unittest
from datetime import date
from decimal import Decimal

from app.models import Period
from app.reports import build_report, report_window
from app.repository import MockOrderRepository, mock_order


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.repository = MockOrderRepository()

    def test_daily_counts_transactions_across_marketplace_id_collisions(self):
        report = build_report(Period.day, date(2026, 10, 3), self.repository)
        self.assertEqual(report.totals.revenue, Decimal("325.00"))
        self.assertEqual(report.totals.transactions, 4)
        self.assertEqual(report.totals.units_sold, 9)
        self.assertIsNone(report.ebay_buyers)
        self.assertEqual(sum(m.revenue for m in report.marketplaces), report.totals.revenue)

    def test_monthly_buyers_are_distinct_and_returning_uses_prior_history(self):
        report = build_report(Period.month, date(2026, 9, 15), self.repository)
        self.assertEqual(report.totals.revenue, Decimal("400.00"))
        self.assertEqual(report.comparison.revenue_change_percent, Decimal("100.00"))
        self.assertEqual(report.ebay_buyers.unique_buyers, 2)
        self.assertEqual(report.ebay_buyers.returning_buyers, 1)
        self.assertEqual(report.ebay_buyers.returning_buyer_rate_percent, Decimal("50.00"))
        self.assertEqual(len(report.trend), 30)

    def test_year_uses_monthly_buckets_and_previous_year_comparison(self):
        report = build_report(Period.year, date(2026, 9, 1), self.repository)
        self.assertEqual(len(report.trend), 12)
        self.assertEqual(report.totals.revenue, Decimal("965.00"))
        self.assertEqual(report.comparison.revenue, Decimal("200.00"))
        self.assertEqual(report.ebay_buyers.returning_buyers, 1)

    def test_no_data_has_zero_counts_but_undefined_rates(self):
        report = build_report(Period.month, date(2024, 9, 1), self.repository)
        self.assertEqual(report.totals.transactions, 0)
        self.assertIsNone(report.totals.average_selling_price)
        self.assertIsNone(report.comparison.revenue_change_percent)
        self.assertIsNone(report.ebay_buyers.returning_buyer_rate_percent)

    def test_end_boundary_is_excluded_and_money_is_exact(self):
        repository = MockOrderRepository((
            mock_order("1", "amazon", "2026-09-30", "0.10"),
            mock_order("2", "amazon", "2026-09-30", "0.20"),
            mock_order("3", "amazon", "2026-10-01", "999.00"),
        ))
        report = build_report(Period.month, date(2026, 9, 1), repository)
        self.assertEqual(report.totals.revenue, Decimal("0.30"))
        self.assertEqual(report.totals.average_selling_price, Decimal("0.15"))

    def test_leap_month_and_year_rollover(self):
        self.assertEqual(report_window(Period.month, date(2024, 2, 29)),
                         (date(2024, 2, 1), date(2024, 3, 1), date(2024, 1, 1)))
        self.assertEqual(report_window(Period.month, date(2026, 1, 15)),
                         (date(2026, 1, 1), date(2026, 2, 1), date(2025, 12, 1)))

    def test_other_combines_all_remaining_vendors_for_every_period(self):
        repository = MockOrderRepository((
            mock_order("1", "amazon", "2026-10-03", "100.00", units=2),
            mock_order("1", "goodwillbooks", "2026-10-03", "20.00", units=2),
            mock_order("1", "etsy", "2026-10-03", "30.00", units=3),
            mock_order("1", "other", "2026-10-03", "10.00"),
            mock_order("future", "etsy", "2027-01-01", "999.00"),
        ))
        for period in Period:
            with self.subTest(period=period):
                report = build_report(period, date(2026, 10, 3), repository)
                rows = {row.marketplace: row for row in report.marketplaces}
                self.assertEqual(set(rows), {"shopgoodwill", "amazon", "ebay", "other"})
                self.assertEqual(rows["other"].revenue, Decimal("60.00"))
                self.assertEqual(rows["other"].transactions, 3)
                self.assertEqual(rows["other"].units_sold, 6)
                self.assertEqual(rows["other"].average_selling_price, Decimal("10.00"))
                self.assertEqual(sum(row.revenue for row in rows.values()), report.totals.revenue)
                self.assertEqual(sum(row.transactions for row in rows.values()), report.totals.transactions)


if __name__ == "__main__":
    unittest.main()
