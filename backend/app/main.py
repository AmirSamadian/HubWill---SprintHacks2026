"""Application entry point. Run from backend with: python -m uvicorn app.main:app."""

import datetime as dt

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .email_models import MonthlyEmailPreview, RecipientSettings
from .models import DashboardReport, Period
from .monthly_email import build_email_preview
from .recipient_store import recipient_store
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
