"""Verify schedule timing, restart safety, and conservative failure handling."""

import datetime as dt
import smtplib
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.delivery_history import DeliveryHistory
from app.email_models import RecipientSettings
from app.recipient_store import RecipientStore
from app.repository import MockOrderRepository
from app.scheduler import REPORTING_TIMEZONE, due_month, run_due_report


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.recipients = RecipientStore(self.directory)
        self.recipients.save(RecipientSettings(recipients=["team@example.com"]))
        self.history = DeliveryHistory(self.directory)
        self.now = dt.datetime(2026, 10, 4, 9, tzinfo=REPORTING_TIMEZONE)

    def run_check(self, deliver):
        return run_due_report(self.now, MockOrderRepository(), self.recipients, self.history, deliver)

    def test_first_of_month_threshold_and_eastern_conversion(self):
        self.assertIsNone(due_month(dt.datetime(2026, 10, 1, 11, 59, tzinfo=dt.timezone.utc)))
        self.assertEqual(due_month(dt.datetime(2026, 10, 1, 12, tzinfo=dt.timezone.utc)), dt.date(2026, 9, 1))
        self.assertIsNone(due_month(dt.datetime(2026, 1, 1, 12, 59, tzinfo=dt.timezone.utc)))
        self.assertEqual(due_month(dt.datetime(2026, 1, 1, 13, tzinfo=dt.timezone.utc)), dt.date(2025, 12, 1))

    def test_naive_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            due_month(dt.datetime(2026, 10, 4))

    def test_late_start_captures_previous_month_once_across_restart(self):
        captures = []
        self.assertEqual(self.run_check(captures.append)["status"], "captured_locally")
        self.history = DeliveryHistory(self.directory)
        self.assertEqual(self.run_check(captures.append)["status"], "captured_locally")
        self.assertEqual(len(captures), 1)
        self.assertEqual(captures[0].start, dt.date(2026, 9, 1))

    def test_no_recipients_does_not_claim_month(self):
        self.recipients.save(RecipientSettings())
        self.assertEqual(self.run_check(lambda _: self.fail("Should not send"))["status"], "awaiting_recipients")
        self.assertEqual(self.history.entries(), [])

    def test_connection_refused_retries_when_capture_server_returns(self):
        def unavailable(_):
            raise ConnectionRefusedError()
        self.assertEqual(self.run_check(unavailable)["status"], "retryable")
        captures = []
        self.assertEqual(self.run_check(captures.append)["status"], "captured_locally")
        self.assertEqual(len(captures), 1)

    def test_ambiguous_failure_requires_review_instead_of_resending(self):
        def interrupted(_):
            raise smtplib.SMTPServerDisconnected()
        self.assertEqual(self.run_check(interrupted)["status"], "needs_review")
        self.assertEqual(self.run_check(lambda _: self.fail("Should not resend"))["status"], "needs_review")

    def test_existing_in_progress_claim_blocks_another_scheduler(self):
        self.assertTrue(self.history.claim("2026-09"))
        self.assertEqual(self.run_check(lambda _: self.fail("Already claimed"))["status"], "in_progress")

    def test_next_month_creates_a_new_scheduled_report(self):
        captures = []
        self.run_check(captures.append)
        self.now = dt.datetime(2026, 11, 1, 8, tzinfo=REPORTING_TIMEZONE)
        self.run_check(captures.append)
        self.assertEqual(len(captures), 2)
        self.assertEqual(captures[-1].start, dt.date(2026, 10, 1))

    def test_competing_workers_only_claim_month_once(self):
        # Independent connections exercise the same lock used across processes.
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(
                lambda _: DeliveryHistory(self.directory).claim("2026-09"), range(2)
            ))
        self.assertEqual(sorted(results), [False, True])
