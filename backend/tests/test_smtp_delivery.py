"""Verify real-delivery behavior with mocked SMTP; never contact a mail server."""

import os
import smtplib
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.email_models import SendEmailRequest
from app.models import Period
from app.monthly_email import build_email_preview
from app.repository import MockOrderRepository
from app.reports import build_report
from app.smtp_delivery import EmailConfigurationError, EmailDeliveryError, SmtpSettings, send_via_smtp


class SmtpDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.request = SendEmailRequest(recipients="one@example.com; two@example.com; ONE@example.com")
        self.preview = build_email_preview(build_report(Period.month, date(2026, 9, 1), MockOrderRepository()), self.request)
        self.settings = SmtpSettings("smtp.example.com", 587, "starttls", "sender@example.com", "sender@example.com", "private-test-secret")

    def test_runtime_recipients_validate_before_sending(self):
        self.assertEqual(len(self.request.recipients), 2)
        for value in ([], "", "one@example.com,invalid"):
            with self.assertRaises(ValidationError):
                SendEmailRequest(recipients=value)

    @patch("app.smtp_delivery.smtplib.SMTP")
    def test_tls_precedes_login_and_recipient_addresses_are_not_in_headers(self, factory):
        smtp = factory.return_value.__enter__.return_value
        smtp.send_message.return_value = {}
        send_via_smtp(self.preview, self.settings)
        actions = [call[0] for call in smtp.method_calls]
        self.assertLess(actions.index("starttls"), actions.index("login"))
        args, kwargs = smtp.send_message.call_args
        message = args[0]
        self.assertEqual(kwargs["to_addrs"], ["one@example.com", "two@example.com"])
        self.assertEqual(message["To"], "undisclosed-recipients:;")
        self.assertNotIn("Bcc", message)
        self.assertEqual(message["From"], "sender@example.com")
        self.assertTrue(message.get_body(preferencelist=("html",)))
        self.assertTrue(message.get_body(preferencelist=("plain",)))

    @patch("app.smtp_delivery.smtplib.SMTP_SSL")
    def test_ssl_mode_and_partial_refusal_are_not_success(self, factory):
        smtp = factory.return_value.__enter__.return_value
        smtp.send_message.return_value = {"two@example.com": (550, b"refused")}
        settings = SmtpSettings("smtp.example.com", 465, "ssl", "sender@example.com", "sender@example.com", "secret")
        with self.assertRaises(EmailDeliveryError):
            send_via_smtp(self.preview, settings)
        smtp.starttls.assert_not_called()

    @patch("app.smtp_delivery.smtplib.SMTP")
    def test_authentication_error_does_not_expose_provider_response(self, factory):
        smtp = factory.return_value.__enter__.return_value
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"private-test-secret")
        with self.assertRaises(EmailDeliveryError) as result:
            send_via_smtp(self.preview, self.settings)
        self.assertNotIn("private-test-secret", str(result.exception))
        self.assertNotIn("private-test-secret", repr(self.settings))
        smtp.send_message.assert_not_called()

    def test_missing_or_unencrypted_configuration_is_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(EmailConfigurationError):
                SmtpSettings.from_environment()
        with patch.dict(os.environ, {"SMTP_HOST": "smtp.example.com", "SMTP_FROM": "sender@example.com",
                                   "SMTP_USERNAME": "sender@example.com", "SMTP_PASSWORD": "secret",
                                   "SMTP_SECURITY": "none"}, clear=True):
            with self.assertRaises(EmailConfigurationError):
                SmtpSettings.from_environment()

    def test_send_route_uses_request_recipients_not_saved_settings(self):
        from app.main import send_monthly_email
        report = build_report(Period.month, date(2026, 9, 1), MockOrderRepository())
        with patch("app.main.dashboard", return_value=report), patch("app.main.send_via_smtp") as deliver:
            result = send_monthly_email(self.request, date(2026, 9, 1))
        self.assertEqual(deliver.call_args.args[0].recipients, self.request.recipients)
        self.assertEqual(result.delivery_status, "accepted_by_smtp")
