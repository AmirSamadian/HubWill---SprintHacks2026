"""First-of-month local capture scheduler. Run with --once for one due check."""

import argparse
import datetime as dt
import json
import smtplib
import threading
from typing import Callable
from zoneinfo import ZoneInfo

from .delivery_history import DeliveryHistory
from .demo_delivery import send_to_demo_server
from .email_models import MonthlyEmailPreview
from .models import Period
from .monthly_email import build_email_preview
from .recipient_store import RecipientStore, recipient_store, state_directory
from .reports import build_report
from .repository import OrderRepository, repository


REPORTING_TIMEZONE = ZoneInfo("America/New_York")


def due_month(now: dt.datetime) -> dt.date | None:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Scheduler time must include a timezone.")
    local = now.astimezone(REPORTING_TIMEZONE)
    due_at = local.replace(day=1, hour=8, minute=0, second=0, microsecond=0)
    if local < due_at:
        return None
    # Catch up the latest completed month when the scheduler starts late.
    return (local.date().replace(day=1) - dt.timedelta(days=1)).replace(day=1)


def run_due_report(
    now: dt.datetime, orders: OrderRepository, recipients: RecipientStore,
    history: DeliveryHistory,
    deliver: Callable[[MonthlyEmailPreview], None] = send_to_demo_server,
) -> dict[str, str | None]:
    month_start = due_month(now)
    if month_start is None:
        return {"report_month": None, "status": "not_due", "detail": "Next check is after 8 a.m. Eastern on the first."}
    month = month_start.strftime("%Y-%m")
    settings = recipients.load()
    if not settings.recipients:
        return {"report_month": month, "status": "awaiting_recipients", "detail": "Save recipient addresses before scheduling."}
    # Prepare the report before claiming delivery; calculation failures send nothing.
    preview = build_email_preview(build_report(Period.month, month_start, orders), settings)
    if not history.claim(month):
        entry = history.get(month)
        return entry or {"report_month": month, "status": "needs_review", "detail": "Scheduling state could not be read."}
    try:
        deliver(preview)
    except ConnectionRefusedError:
        # No SMTP connection was established, so retrying cannot duplicate a capture.
        history.finish(month, "retryable", "Start the local SMTP server; the next check will retry.")
    except (OSError, smtplib.SMTPException):
        # A timeout/disconnect may occur after acceptance. Do not blindly resend.
        history.finish(month, "needs_review", "SMTP delivery was interrupted; inspect captures before retrying.")
    else:
        history.finish(month, "captured_locally", "Scheduled email captured locally; no real inbox delivery.")
    return history.get(month)


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule monthly reports to the local dummy SMTP server.")
    parser.add_argument("--once", action="store_true", help="Check the real current time once and exit.")
    args = parser.parse_args()
    history = DeliveryHistory(state_directory)
    previous_result = None
    stopped = threading.Event()
    try:
        while True:
            try:
                result = run_due_report(dt.datetime.now(dt.timezone.utc), repository, recipient_store, history)
            except Exception as error:
                # Keep failures visible without terminating an unattended local demo.
                # Only report the exception type, avoiding raw private settings in logs.
                result = {"status": "error", "detail": f"Scheduler check failed: {type(error).__name__}."}
            if result != previous_result:
                print(json.dumps(result), flush=True)
                previous_result = result
            if args.once:
                # Shell scripts can detect failed or uncertain one-time checks.
                raise SystemExit(1 if result["status"] in {"error", "needs_review", "retryable", "in_progress"} else 0)
            stopped.wait(60)
    except KeyboardInterrupt:
        print("Monthly scheduler stopped.", flush=True)


if __name__ == "__main__":
    main()
