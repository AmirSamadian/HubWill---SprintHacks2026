"""Deliver a preview to local capture only, without an account or credentials."""

import smtplib
from email.message import EmailMessage

from .email_models import MonthlyEmailPreview


def send_to_demo_server(preview: MonthlyEmailPreview, port: int = 8025) -> None:
    if not preview.recipients:
        raise ValueError("Save at least one recipient before sending a demo report.")

    message = EmailMessage()
    # The dummy server accepts this placeholder; it is not a real sending account.
    message["From"] = "Hackathon Reports <reports@example.test>"
    message["To"] = ", ".join(str(address) for address in preview.recipients)
    message["Subject"] = "[LOCAL CAPTURE] " + preview.subject
    message.set_content(preview.text_body)
    message.add_alternative(preview.html_body, subtype="html")

    # Deliberately fixed to loopback: demo mode cannot contact an external mail server.
    with smtplib.SMTP("127.0.0.1", port, timeout=10) as smtp:
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPException("The demo server refused one or more recipients.")
