"""Check the full SMTP capture path without contacting any external inbox."""

import socket
import tempfile
import unittest
from datetime import date
from email import policy
from email.parser import BytesParser
from pathlib import Path

from aiosmtpd.controller import Controller

from app.demo_delivery import send_to_demo_server
from app.demo_smtp import CaptureHandler
from app.email_models import RecipientSettings
from app.models import Period
from app.monthly_email import build_email_preview
from app.reports import build_report
from app.repository import MockOrderRepository


class DemoDeliveryTests(unittest.TestCase):
    def preview(self, recipients):
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository())
        return build_email_preview(report, RecipientSettings(recipients=recipients))

    def test_local_smtp_captures_subject_recipients_and_both_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            controller = Controller(CaptureHandler(Path(directory)), hostname="127.0.0.1", port=port)
            controller.start()
            try:
                send_to_demo_server(self.preview(["team@example.com", "judge@example.org"]), port=port)
                files = list(Path(directory).glob("*.eml"))
                self.assertEqual(len(files), 1)
                message = BytesParser(policy=policy.default).parsebytes(files[0].read_bytes())
                self.assertIn("[LOCAL CAPTURE]", message["Subject"])
                self.assertIn("judge@example.org", message["To"])
                self.assertIn("reports@example.test", message["From"])
                self.assertIn("$400.00", message.get_body(preferencelist=("plain",)).get_content())
                self.assertIn("<table", message.get_body(preferencelist=("html",)).get_content())
            finally:
                controller.stop()

    def test_empty_recipients_fail_before_connecting(self):
        with self.assertRaises(ValueError):
            send_to_demo_server(self.preview([]))
