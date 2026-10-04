"""Check email calculations, safe rendering, validation, and local persistence."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.email_models import RecipientSettings
from app.models import Period
from app.monthly_email import build_email_preview
from app.recipient_store import RecipientStore
from app.reports import build_report
from app.repository import MockOrderRepository, mock_order


class MonthlyEmailTests(unittest.TestCase):
    def test_pasted_recipients_validate_and_deduplicate(self):
        settings = RecipientSettings(recipients="team@example.com; TEAM@example.com\njudge@example.org")
        self.assertEqual(settings.recipients, ["team@example.com", "judge@example.org"])
        with self.assertRaises(ValidationError):
            RecipientSettings(recipients="team@example.com,invalid")

    def test_empty_input_clears_recipients(self):
        self.assertEqual(RecipientSettings(recipients="  ").recipients, [])

    def test_local_settings_survive_new_store_and_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RecipientStore(Path(directory))
            self.assertEqual(store.load().recipients, [])
            store.save(RecipientSettings(recipients=["team@example.com"]))
            self.assertEqual(RecipientStore(Path(directory)).load().recipients, ["team@example.com"])
            store.save(RecipientSettings())
            self.assertEqual(store.load().recipients, [])

    def test_damaged_settings_fail_visibly(self):
        with tempfile.TemporaryDirectory() as directory:
            store = RecipientStore(Path(directory))
            store.path.write_text("broken JSON", encoding="utf-8")
            with self.assertRaises(ValueError):
                store.load()

    def test_preview_uses_report_values_and_marks_mock_data(self):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository())
        preview = build_email_preview(report, RecipientSettings())
        self.assertIn("September 2026 [DEMO]", preview.subject)
        self.assertIn("Total item revenue: $400.00", preview.text_body)
        self.assertIn("eBay returning buyer rate: 50.00%", preview.text_body)
        self.assertIn("Retention covers eBay only", preview.text_body)
        self.assertEqual(preview.delivery_status, "preview_only")

    def test_other_vendors_are_combined_in_email_and_html_is_escaped(self):
        repository = MockOrderRepository((
            mock_order("1", "goodwillbooks", "2026-09-01", "20.00"),
            mock_order("1", "etsy", "2026-09-01", "30.00"),
        ))
        report = build_report(Period.month, date(2026, 9, 1), repository)
        report.notice = '<script>alert("test")</script>'
        preview = build_email_preview(report, RecipientSettings())
        self.assertIn("Other vendors: $50.00; 2 transactions", preview.text_body)
        self.assertNotIn("<script>", preview.html_body)
        self.assertIn("&lt;script&gt;", preview.html_body)

    def test_daily_report_cannot_be_rendered_as_monthly_email(self):
        report = build_report(Period.day, date(2026, 9, 1), MockOrderRepository())
        with self.assertRaises(ValueError):
            build_email_preview(report, RecipientSettings())

    def test_missing_buyer_data_and_zero_baseline_are_not_reported_as_zero_rates(self):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository(()))
        report.ebay_buyers = None
        preview = build_email_preview(report, RecipientSettings())
        self.assertIn("month-over-month revenue comparison is unavailable", preview.text_body)
        self.assertIn("buyer information is unavailable", preview.text_body)
        self.assertIn("buyer information is unavailable", preview.html_body)
        self.assertNotIn("Returning buyer rate: 0.00%", preview.text_body)

    def test_email_shows_reporting_dates_and_one_marketplace_table(self):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository())
        preview = build_email_preview(report, RecipientSettings())
        self.assertIn("2026-09-01 through 2026-09-30 (America/New_York)", preview.text_body)
        self.assertEqual(preview.html_body.count("<div style=\"margin-top:7px\">"), 4)
        self.assertIn("Revenue was up 100.00%", preview.text_body)
        self.assertIn("previous calendar month ($200.00)", preview.text_body)

    def test_lengthy_definitions_are_omitted_but_limitations_remain(self):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository())
        report.revenue_definition = '<img src=x onerror="alert(1)">'
        report.unavailable_metrics = ["<script>bad()</script>"]
        preview = build_email_preview(report, RecipientSettings())
        self.assertNotIn("<img", preview.html_body)
        self.assertNotIn("<script>", preview.html_body)
        self.assertIn("does not assess overall profitability", preview.html_body)

    def test_decline_and_tied_marketplaces_are_described_honestly(self):
        repository = MockOrderRepository((
            mock_order("1", "amazon", "2026-08-01", "200"),
            mock_order("2", "amazon", "2026-09-01", "50"),
            mock_order("3", "ebay", "2026-09-01", "50"),
        ))
        preview = build_email_preview(build_report(Period.month, date(2026, 9, 1), repository), RecipientSettings())
        self.assertIn("Revenue was down 50.00%", preview.text_body)
        self.assertIn("Amazon and eBay tied for the lead", preview.text_body)
        self.assertLess(len(preview.text_body.split()), 250)

    def test_negative_revenue_does_not_make_negative_chart_widths(self):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository(()))
        report.marketplaces[0].revenue = -10
        preview = build_email_preview(report, RecipientSettings())
        self.assertIn("$-10.00", preview.html_body)
        self.assertNotIn('width="-', preview.html_body)
        self.assertNotIn("led in revenue", preview.text_body)
