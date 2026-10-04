"""Authenticated TLS SMTP delivery. Credentials stay in the root .env."""

import os
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from pydantic import EmailStr, TypeAdapter

from . import config  # Explicitly loads root .env without logging its values.
from .email_models import MonthlyEmailPreview


class EmailConfigurationError(ValueError):
    """Safe configuration error with no credentials in its message."""


class EmailDeliveryError(Exception):
    """Delivery failed or was partial; do not automatically resend."""


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    security: str
    sender: str
    username: str = field(repr=False)
    password: str = field(repr=False)

    @classmethod
    def from_environment(cls):
        names = ("SMTP_HOST", "SMTP_FROM", "SMTP_USERNAME", "SMTP_PASSWORD")
        if any(not os.environ.get(name, "").strip() for name in names):
            raise EmailConfigurationError("Set SMTP_HOST, SMTP_FROM, SMTP_USERNAME and SMTP_PASSWORD privately in root .env.")
        security = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
        if security not in {"starttls", "ssl"}:
            raise EmailConfigurationError("SMTP_SECURITY must be starttls or ssl.")
        try:
            port = int(os.environ.get("SMTP_PORT", "587" if security == "starttls" else "465"))
            if not 1 <= port <= 65535:
                raise ValueError()
            sender = str(TypeAdapter(EmailStr).validate_python(os.environ["SMTP_FROM"]))
        except ValueError:
            raise EmailConfigurationError("Check SMTP_PORT and SMTP_FROM in root .env.") from None
        host = os.environ["SMTP_HOST"].strip()
        if any(character.isspace() for character in host):
            raise EmailConfigurationError("SMTP_HOST must be a hostname without spaces.")
        return cls(host, port, security, sender, os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])


def send_via_smtp(preview: MonthlyEmailPreview, settings: SmtpSettings | None = None) -> None:
    if not preview.recipients:
        raise ValueError("Provide at least one recipient.")
    settings = settings or SmtpSettings.from_environment()
    message = EmailMessage()
    message["From"] = settings.sender
    # Use envelope recipients so they do not see each other's addresses.
    message["To"] = "undisclosed-recipients:;"
    message["Subject"] = preview.subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid()
    message.set_content(preview.text_body)
    message.add_alternative(preview.html_body, subtype="html")
    context = ssl.create_default_context()
    try:
        if settings.security == "ssl":
            client = smtplib.SMTP_SSL(settings.host, settings.port, timeout=20, context=context)
        elif settings.security == "starttls":
            client = smtplib.SMTP(settings.host, settings.port, timeout=20)
        else:
            raise EmailConfigurationError("Encrypted SMTP delivery is required.")
        with client as smtp:
            smtp.ehlo()
            if settings.security == "starttls":
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings.username, settings.password)
            refused = smtp.send_message(message, from_addr=settings.sender,
                                        to_addrs=[str(address) for address in preview.recipients])
            if refused:
                # Some recipients may have accepted it; retrying all could duplicate.
                raise EmailDeliveryError("Some recipients were refused. Check delivery before retrying.")
    except (OSError, smtplib.SMTPException):
        # Provider responses may contain private addresses or authentication details.
        raise EmailDeliveryError("SMTP delivery failed or is uncertain. Check provider settings and delivery before retrying.") from None
