"""Dashboard calculations, API contract and (optionally) the real database.

The database tests run only when DASHBOARD_TEST_PGDATABASE names a populated
database, e.g. DASHBOARD_TEST_PGDATABASE=goodwill_db_test. They only read.
"""

import os
import unittest
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.dashboard import ReportData, ReportError, daily_report, monthly_history, monthly_report, to_json
from app.repository import DatabaseUnavailable, MockOrderRepository, Snapshot, mock_order

TODAY = date(2026, 10, 4)


def data(repository=None, metric="merchandise_before_refunds", today=TODAY):
    config = Settings(reporting_timezone="America/New_York", revenue_metric=metric)
    return ReportData((repository or MockOrderRepository()).snapshot(config.reporting_timezone), config, today)


def order(order_id, source_id, day, merchandise, *, customer=None, status="COMPLETED", refund="0",
          shipping="0", cost="0", fee="0"):
    merchandise, refund = Decimal(merchandise), Decimal(refund)
    revenue = merchandise - refund + Decimal(shipping) - Decimal(cost) - Decimal(fee)
    return {"order_id": order_id, "source_id": source_id, "customer_id": customer, "status": status,
            "day": date.fromisoformat(day), "shipping_charge_amount": Decimal(shipping),
            "shipping_cost_amount": Decimal(cost), "tax_amount": Decimal(0), "operation_fee_amount": Decimal(fee),
            "materialized_order_id": order_id, "merchandise_revenue": merchandise, "refund_impact": -refund,
            "total_transaction_revenue": revenue}


def line(order_id, price, quantity=1, *, refund="0", category="Furniture", parent="Home"):
    return {"order_id": order_id, "quantity": quantity, "unit_price": Decimal(price), "discount_amount": Decimal(0),
            "refund_amount": Decimal(refund), "category_id": 1, "category_name": category,
            "parent_category_name": parent}


class FixtureRepository:
    def __init__(self, orders, lines, listings=()):
        self.orders, self.lines, self.listings = orders, lines, list(listings)

    def snapshot(self, timezone):
        sources = [{"source_id": 1, "name": "Amazon"}, {"source_id": 2, "name": "eBay"},
                   {"source_id": 3, "name": "ShopGoodwill"}]
        return Snapshot(sources, self.orders, self.lines, self.listings)


class DailyReport(unittest.TestCase):
    def test_channels_totals_and_unknown_customers(self):
        report = to_json(daily_report(data(), date(2026, 10, 3)))
        channels = {c["id"]: c for c in report["channels"]}
        self.assertEqual(channels["amazon"]["revenue"], 90.0)
        self.assertIsNone(channels["amazon"]["customers"])  # Amazon shares no buyer identity
        self.assertEqual(channels["ebay"]["customers"], 1)
        self.assertEqual(report["totals"]["revenue"], 325.0)
        self.assertIsNone(channels["shopgoodwill"]["customers"])
        # Unknown rows count as 0 in the total, so it equals eBay's customers.
        self.assertEqual(report["totals"]["customers"], 1)
        self.assertEqual(report["dataMode"], "mock")

    def test_today_and_future_are_rejected(self):
        with self.assertRaises(ReportError):
            daily_report(data(), TODAY)

    def test_day_without_sales_reports_zero_revenue_and_customers(self):
        report = daily_report(data(), date(2026, 9, 2))
        self.assertEqual(report["totals"], {"revenue": Decimal(0), "orders": 0, "customers": 0})


class MonthlyReport(unittest.TestCase):
    def test_kpis_follow_documented_definitions(self):
        report = monthly_report(data(), "2026-09")
        kpis = report["kpis"]
        self.assertEqual(kpis["revenue"], Decimal("400.00"))
        self.assertEqual(kpis["unitsSold"], 9)  # 1 + 1 + 1 + 2 + 4
        self.assertEqual(kpis["avgSellingPrice"], Decimal("400.00") / 9)  # merchandise / units
        self.assertEqual(kpis["buyers"], 2)
        self.assertEqual(kpis["newBuyers"], 1)  # buyer-b's first order is in September
        self.assertEqual(kpis["repeatBuyerRate"], Decimal("0.5"))  # buyer-a bought before September
        self.assertIsNone(kpis["grossMarginPct"])
        self.assertIsNone(kpis["netMarginPct"])
        self.assertIsNone(kpis["satisfaction"])
        self.assertEqual(report["previousMonth"], "2026-08")
        self.assertEqual(len(report["daily"]), 30)
        self.assertFalse(report["isPartial"])

    def test_month_over_month_deltas(self):
        deltas = monthly_report(data(), "2026-09")["kpiDeltas"]
        self.assertEqual(deltas["revenue"], {"kind": "relative", "value": Decimal(1)})  # 400 vs 200
        self.assertEqual(deltas["repeatBuyerRate"]["kind"], "points")
        self.assertIsNone(deltas["grossMarginPct"])

    def test_month_in_progress_compares_rates_but_not_totals(self):
        report = monthly_report(data(), "2026-10")
        self.assertTrue(report["isPartial"])
        self.assertEqual(report["through"], "2026-10-03")
        self.assertIsNone(report["kpiDeltas"]["revenue"])
        self.assertEqual(report["watchItems"], [])

    def test_year_over_year_uses_same_month_last_year(self):
        report = monthly_report(data(), "2025-10")
        self.assertEqual(report["financial"]["revenue"], Decimal("120.00"))
        self.assertEqual(report["financial"]["revenuePriorYear"], Decimal(0))
        self.assertIsNone(report["kpis"]["revenueGrowthYoY"])  # no baseline, not a fake 0%

    def test_future_month_and_bad_input_are_rejected(self):
        for month in ("2026-11", "2026-13", "Sept", "2026-9"):
            with self.subTest(month=month), self.assertRaises(ReportError):
                monthly_report(data(), month)

    def test_history_lists_each_month_with_growth(self):
        rows = monthly_history(data(), "2026-09", 3)
        self.assertEqual([r["month"] for r in rows], ["2026-07", "2026-08", "2026-09"])
        self.assertEqual(rows[-1]["revenue"], Decimal("400.00"))


class WatchListAndCategories(unittest.TestCase):
    def setUp(self):
        orders = [order(1, 1, "2026-08-10", "800"), order(2, 1, "2026-09-10", "600"),
                  order(3, 1, "2026-08-11", "600"), order(4, 1, "2026-09-11", "590"),
                  order(5, 1, "2026-08-12", "100"), order(6, 3, "2026-09-12", "50")]
        lines = [line(1, "800"), line(2, "600"),
                 line(3, "600", category="Lamps"), line(4, "590", category="Lamps"),
                 line(5, "100", category="Rugs"), line(6, "50", category="Home", parent=None)]
        self.repository = FixtureRepository(orders, lines)

    def test_subcategory_drop_is_flagged_with_message(self):
        items = monthly_report(data(self.repository), "2026-09")["watchItems"]
        self.assertEqual([i["item"] for i in items], ["Furniture"])  # -25%; Lamps -1.7%; Rugs under $500
        self.assertEqual(items[0]["message"],
                         "Furniture sales in the Home category have gone down by 25.0% since last month")

    def test_categories_roll_up_to_root_without_margin(self):
        categories = monthly_report(data(self.repository), "2026-09")["categories"]
        self.assertEqual(len(categories), 1)
        home = categories[0]
        self.assertEqual((home["name"], home["revenue"], home["unitsSold"]), ("Home", Decimal(1240), 3))
        self.assertIsNone(home["margin"])

    def test_transaction_revenue_cannot_be_split_by_item(self):
        report = monthly_report(data(self.repository, metric="transaction_revenue"), "2026-09")
        self.assertIsNone(report["watchItems"])
        self.assertIsNone(report["categories"][0]["revenue"])


class RevenueDefinitions(unittest.TestCase):
    def setUp(self):
        self.repository = FixtureRepository(
            [order(1, 1, "2026-09-05", "100", refund="40", shipping="5", cost="7", fee="15"),
             order(2, 1, "2026-09-06", "50", status="CANCELLED")],
            [line(1, "100", refund="40"), line(2, "50")])

    def test_each_configured_definition(self):
        expected = {"merchandise_before_refunds": Decimal(100), "merchandise_after_refunds": Decimal(60),
                    "transaction_revenue": Decimal(43)}
        for metric, revenue in expected.items():
            with self.subTest(metric=metric):
                report = monthly_report(data(self.repository, metric=metric), "2026-09")
                self.assertEqual(report["kpis"]["revenue"], revenue)

    def test_unapproved_status_is_excluded_and_reported(self):
        report = monthly_report(data(self.repository), "2026-09")
        self.assertEqual(report["kpis"]["unitsSold"], 1)
        self.assertIn("CANCELLED", " ".join(report["warnings"]))

    def test_unknown_metric_is_rejected(self):
        with self.assertRaises(ValueError):
            Settings(reporting_timezone="America/New_York", revenue_metric="gross")


class Api(unittest.TestCase):
    def setUp(self):
        self.original = main.repository
        main.repository = MockOrderRepository((mock_order("1", "amazon", "2026-01-05", "10.00"),))
        self.client = TestClient(main.app)

    def tearDown(self):
        main.repository = self.original

    def test_report_endpoints_return_frontend_shapes(self):
        daily = self.client.get("/api/reports/daily", params={"date": "2026-01-05"})
        self.assertEqual(daily.status_code, 200)
        self.assertEqual(daily.json()["totals"]["revenue"], 10.0)  # numbers, not strings
        monthly = self.client.get("/api/reports/monthly", params={"month": "2026-01"}).json()
        for key in ("month", "previousMonth", "isPartial", "channels", "daily", "financial", "sales", "listings",
                    "categories", "customers", "kpis", "kpiDeltas", "watchItems"):
            self.assertIn(key, monthly)
        history = self.client.get("/api/reports/monthly/history", params={"month": "2026-01", "months": 2})
        self.assertEqual([r["month"] for r in history.json()], ["2025-12", "2026-01"])

    def test_invalid_input_returns_422_with_reason(self):
        response = self.client.get("/api/reports/monthly", params={"month": "January"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("YYYY-MM", response.json()["detail"])

    def test_database_failure_returns_503_without_details(self):
        class Down:
            def snapshot(self, timezone):
                raise DatabaseUnavailable("Database unavailable. Check local PostgreSQL settings.")
        main.repository = Down()
        for path, params in (("/api/reports/daily", {"date": "2026-01-05"}),
                             ("/api/email/monthly/preview", {"date": "2026-01-01"})):
            response = self.client.get(path, params=params)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("password", response.text.lower())

    def test_email_preview_uses_the_same_figures(self):
        preview = self.client.get("/api/email/monthly/preview", params={"date": "2026-01-01"}).json()
        self.assertIn("Total item revenue: $10.00", preview["text_body"])
        self.assertEqual(preview["delivery_status"], "preview_only")

    def test_local_dashboard_origin_is_allowed(self):
        response = self.client.options("/api/reports/daily", headers={
            "Origin": "http://localhost:5174", "Access-Control-Request-Method": "GET"})
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5174")
        blocked = self.client.options("/api/reports/daily", headers={
            "Origin": "https://example.com", "Access-Control-Request-Method": "GET"})
        self.assertIsNone(blocked.headers.get("access-control-allow-origin"))


@unittest.skipUnless(os.environ.get("DASHBOARD_TEST_PGDATABASE"), "set DASHBOARD_TEST_PGDATABASE to a populated database")
class RealDatabase(unittest.TestCase):
    """Compares API figures with independent SQL over the same database (read-only)."""

    @classmethod
    def setUpClass(cls):
        import psycopg
        from app.repository import PostgresRepository
        database = os.environ["DASHBOARD_TEST_PGDATABASE"]
        cls.connect = staticmethod(lambda **kw: psycopg.connect(dbname=database, **kw))
        cls.data = ReportData(PostgresRepository(cls.connect).snapshot("America/New_York"),
                              Settings("America/New_York", "merchandise_before_refunds"), TODAY)

    def sql(self, query, *params):
        with self.connect() as connection:
            connection.execute("SET TIME ZONE 'America/New_York'")
            return connection.execute(query, params).fetchone()

    def test_month_matches_independent_sql(self):
        report = monthly_report(self.data, "2026-09")
        revenue, orders, units = self.sql("""
            SELECT SUM(mv.merchandise_revenue), COUNT(DISTINCT o.order_id),
                   (SELECT SUM(oi.quantity) FROM order_item oi JOIN sales_order s USING (order_id)
                    WHERE s.ordered_at::date BETWEEN %s AND %s AND s.status IN ('COMPLETED','SHIPPED','REFUNDED'))
            FROM sales_order o JOIN sales_order_mv mv USING (order_id)
            WHERE o.ordered_at::date BETWEEN %s AND %s AND o.status IN ('COMPLETED','SHIPPED','REFUNDED')""",
            date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(report["kpis"]["revenue"], revenue)
        self.assertEqual(sum(c["orders"] for c in report["channels"]), orders)
        self.assertEqual(report["kpis"]["unitsSold"], units)

    def test_day_matches_independent_sql(self):
        report = daily_report(self.data, date(2026, 10, 2))
        (revenue,) = self.sql("""
            SELECT SUM(mv.merchandise_revenue) FROM sales_order o JOIN sales_order_mv mv USING (order_id)
            WHERE o.ordered_at::date = %s AND o.status IN ('COMPLETED','SHIPPED','REFUNDED')""", date(2026, 10, 2))
        self.assertEqual(report["totals"]["revenue"], revenue)

    def test_repeat_buyers_match_independent_sql(self):
        report = monthly_report(self.data, "2026-09")
        buyers, repeat = self.sql("""
            WITH sept AS (SELECT DISTINCT customer_id FROM sales_order
                          WHERE customer_id IS NOT NULL AND ordered_at::date BETWEEN '2026-09-01' AND '2026-09-30'
                            AND status IN ('COMPLETED','SHIPPED','REFUNDED'))
            SELECT COUNT(*), COUNT(*) FILTER (WHERE EXISTS (
                SELECT 1 FROM sales_order p WHERE p.customer_id = sept.customer_id
                  AND p.ordered_at::date < '2026-09-01' AND p.status IN ('COMPLETED','SHIPPED','REFUNDED')))
            FROM sept""")
        self.assertEqual((report["kpis"]["buyers"], report["customers"]["repeatBuyers"]), (buyers, repeat))


if __name__ == "__main__":
    unittest.main()
