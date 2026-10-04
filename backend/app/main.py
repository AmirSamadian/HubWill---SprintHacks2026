"""Application entry point. Run from backend with: python -m uvicorn app.main:app."""

from fastapi import FastAPI
from pydantic import BaseModel


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
