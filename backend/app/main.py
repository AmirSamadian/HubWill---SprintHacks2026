"""Application entry point. Run from backend with: python -m uvicorn app.main:app."""

import datetime as dt
import smtplib

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .demo_delivery import send_to_demo_server
from .delivery_history import DeliveryHistory
from .email_models import DemoDeliveryResult, MonthlyEmailPreview, RecipientSettings
from .models import DashboardReport, Period
from .monthly_email import build_email_preview
from .recipient_store import recipient_store, state_directory
from .reports import build_report
from .repository import repository


class HealthResponse(BaseModel):
    """A stable response shape for checking whether the API is running."""

    status: str
    service: str


app = FastAPI(
    title="Goodwill Michiana Dashboard API",
    description="Local dashboard backend for the SprintHack demonstration.",
    version="0.1.0",
)


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    # This checks the API process only. Database readiness comes in a later step.
    return HealthResponse(status="ok", service="goodwill-dashboard-backend")


@app.get("/api/dashboard", response_model=DashboardReport, tags=["Dashboard"])
def dashboard(
    period: Period,
    date: dt.date = Query(description="A date within the requested day, month, or year."),
) -> DashboardReport:
    # The route knows the API contract; the repository handles the data source.
    try:
        return build_report(period, date, repository)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/email/recipients", response_model=RecipientSettings, tags=["Monthly email"])
def get_recipients() -> RecipientSettings:
    try:
        return recipient_store.load()
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Saved recipient settings could not be read.") from error


@app.put("/api/email/recipients", response_model=RecipientSettings, tags=["Monthly email"])
def set_recipients(settings: RecipientSettings) -> RecipientSettings:
    # Replace the saved list only after every submitted address validates.
    try:
        return recipient_store.save(settings)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Recipient settings could not be saved.") from error


@app.get("/api/email/monthly/preview", response_model=MonthlyEmailPreview, tags=["Monthly email"])
def monthly_preview(date: dt.date = Query(description="A date within the month to preview.")) -> MonthlyEmailPreview:
    report = dashboard(period=Period.month, date=date)
    return build_email_preview(report, get_recipients())


@app.get("/api/email/monthly/preview/html", response_class=HTMLResponse, tags=["Monthly email"])
def monthly_preview_html(date: dt.date = Query(description="A date within the month to preview.")) -> HTMLResponse:
    # Browser-friendly email preview, rendered from the same content as the JSON API.
    return HTMLResponse(content=monthly_preview(date).html_body)


@app.post("/api/email/monthly/send-demo", response_model=DemoDeliveryResult, tags=["Monthly email"])
def send_monthly_demo(date: dt.date = Query(description="A date within the month to capture locally.")) -> DemoDeliveryResult:
    preview = monthly_preview(date)
    if not preview.recipients:
        raise HTTPException(status_code=400, detail="Save at least one recipient first.")
    try:
        send_to_demo_server(preview)
    except (OSError, smtplib.SMTPException) as error:
        raise HTTPException(
            status_code=503, detail="Local SMTP capture failed. Start python -m app.demo_smtp and retry.",
        ) from error
    # Repeated manual demo requests produce separate local captures by design.
    return DemoDeliveryResult(recipients=preview.recipients, subject="[LOCAL CAPTURE] " + preview.subject)


@app.get("/api/email/schedule/history", tags=["Monthly email"])
def scheduled_delivery_history() -> list[dict[str, str]]:
    try:
        return DeliveryHistory(state_directory).entries()
    except Exception as error:
        raise HTTPException(status_code=500, detail="Scheduled email history could not be read.") from error
