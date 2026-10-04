"""Chatbot API. Run from chatbot/ with: python -m uvicorn app.main:app --port 8001"""

import logging
from functools import lru_cache
from typing import Literal

import anthropic
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config
from .agent import answer_question
from .database import describe_schema

log = logging.getLogger("chatbot")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1, max_length=30)


class Source(BaseModel):
    purpose: str = ""
    sql: str
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    truncated: bool = False
    error: str | None = None


class ChatResponse(BaseModel):
    answer: str
    verified: bool
    sources: list[Source]
    unsupported_numbers: list[str] = []


app = FastAPI(title="Goodwill Michiana Data Chatbot", version="0.1.0")
# Browsers may call the API only from the configured origins or a dashboard served
# from this computer (any port: Vite moves to 5174+ when 5173 is taken).
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@lru_cache(maxsize=1)
def schema_text():
    # The schema only changes with migrations; restart the service after migrating.
    return describe_schema()


@app.get("/api/health")
def health():
    try:
        schema_text()
        database = "ok"
    except psycopg.Error as error:
        log.warning("Database check failed: %s", error)
        database = "unavailable"
    return {"status": "ok", "database": database, "anthropic_api_key_configured": config.api_key_configured()}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if request.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be the user's question.")
    if not config.api_key_configured():
        raise HTTPException(503, "The chatbot has no Anthropic API key. Add ANTHROPIC_API_KEY to chatbot/.env.")
    try:
        schema = schema_text()
    except psycopg.Error as error:
        log.warning("Database unavailable: %s", error)
        raise HTTPException(503, "The chatbot cannot reach the database.") from error

    try:
        result = answer_question([m.model_dump() for m in request.messages], schema)
    except anthropic.AuthenticationError as error:
        raise HTTPException(503, "The Anthropic API key was rejected.") from error
    except anthropic.RateLimitError as error:
        raise HTTPException(429, "The AI service is busy. Try again in a minute.") from error
    except anthropic.APIStatusError as error:
        raise HTTPException(502, f"The AI service returned an error ({error.status_code}).") from error
    except anthropic.APIConnectionError as error:
        raise HTTPException(502, "Could not reach the AI service.") from error

    return ChatResponse(answer=result.answer, verified=result.verified,
                        sources=[Source(**s) for s in result.sources],
                        unsupported_numbers=result.unsupported)
