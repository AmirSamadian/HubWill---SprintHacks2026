"""Validated runtime recipients, previews, and delivery results."""

import re
from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


class RecipientSettings(BaseModel):
    recipients: list[EmailStr] = Field(default_factory=list, max_length=50)

    @field_validator("recipients", mode="before", json_schema_input_type=str | list[str])
    @classmethod
    def split_addresses(cls, value):
        # Support a pasted comma/semicolon/newline list as well as an API array.
        # An empty list clears settings; it does not trigger an email.
        if isinstance(value, str):
            return [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
        return value

    @field_validator("recipients")
    @classmethod
    def remove_duplicates(cls, addresses):
        # Treat case variations as duplicates for this application's recipient list.
        unique = {}
        for address in addresses:
            unique.setdefault(str(address).casefold(), address)
        return list(unique.values())


class MonthlyEmailPreview(BaseModel):
    start: date
    end_exclusive: date
    recipients: list[EmailStr]
    subject: str
    text_body: str
    html_body: str
    data_mode: str
    delivery_status: str = "preview_only"
    notice: str = "This endpoint previews a report; no email has been sent."


class DemoDeliveryResult(BaseModel):
    delivery_status: str = "captured_locally"
    recipients: list[EmailStr]
    subject: str
    notice: str = "Email captured by the local dummy server; no real inbox delivery."


class SendEmailRequest(RecipientSettings):
    # Manual delivery uses this request, never a stale saved recipient list.
    recipients: list[EmailStr] = Field(min_length=1, max_length=50)


class EmailDeliveryResult(BaseModel):
    delivery_status: str = "accepted_by_smtp"
    recipients: list[EmailStr]
    subject: str
    notice: str = "The SMTP server accepted the message; inbox delivery is not guaranteed."
