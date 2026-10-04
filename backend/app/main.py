"""Application entry point. Run from backend with: python -m uvicorn app.main:app."""

import datetime as dt

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .models import DashboardReport, Period
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
