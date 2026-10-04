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
        self.assertIn("Returning buyer rate: 50.00%", preview.text_body)
        self.assertIn("eBay buyer information only", preview.text_body)
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
