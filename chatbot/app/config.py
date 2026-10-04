"""Settings, read from the environment and an optional chatbot/.env file.

The .env file is git-ignored. Values are never logged or returned by the API.
"""

import os
from pathlib import Path

CHATBOT_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    """Minimal KEY=VALUE loader; real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file(CHATBOT_DIR / ".env")

# Connect as the read-only role created by setup_readonly_role.sql.
DATABASE_URL = os.environ.get(
    "CHATBOT_DATABASE_URL", "postgresql://goodwill_chatbot@localhost:5432/goodwill_db_test"
)
MODEL = os.environ.get("CHATBOT_MODEL", "claude-opus-5-5")
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CHATBOT_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]
# Dates in answers are Goodwill Michiana's local dates.
REPORT_TIMEZONE = "America/Indiana/Indianapolis"

MAX_RESULT_ROWS = 200  # rows returned to the model and the UI per query
MAX_TOOL_ROUNDS = 8  # model turns allowed per question
MAX_VERIFICATION_RETRIES = 1  # extra attempts after an answer fails the number check


def api_key_configured():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
