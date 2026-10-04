# "Ask the data" chatbot

A chat service that answers questions about the Goodwill database. It can
answer questions the dashboard doesn't cover, such as individual listings,
relisting, days to sell, refunds, fees, shipping costs and review text.

The dashboard shows it as a floating **Ask the data** button on every tab.

## How it stays factual

The chatbot uses Claude with a single tool: a read-only SQL query against
PostgreSQL. "Retrieval" here means querying the database, not searching
documents. Answers are restricted to what those queries return:

1. **Query first, then answer.** Claude may only state facts it read from
   `run_sql` results in the current conversation. It must compute every
   total, count, average and percentage in SQL rather than doing arithmetic
   itself.
2. **Every number is checked automatically.**
   - Before an answer is shown, `app/verify.py` checks that each number in
     the text matches a value in the query results. Formatting such as `$`,
     `%`, commas and rounding is allowed for.
   - If a number doesn't match, Claude gets one chance to recompute it in SQL.
     If it still fails, the answer is **withheld** and the user is told why.
3. **Every answer shows its sources.** The SQL and the returned rows are under
   each answer ("Show queries & rows"), so anyone can check them.
4. **Unanswerable questions get "no".** If the database doesn't hold the data
   (labor, donation intake, cost of goods, profit), it says so.

Limits:
- The automatic check covers numbers, not wording. A statement like "Electronics
  led sales" relies on the rules above and the visible sources.
- Small whole numbers, like years and day-of-month numbers, are easy to match by
  coincidence, so they're only weakly checked.
- No AI system is perfect. Every answer can be traced to real rows, and
  invented figures are blocked.

## Safety

- **Read-only user.** It connects as `goodwill_chatbot`, a PostgreSQL user that
  can only `SELECT`. Every transaction is read-only, and queries are stopped
  after 5 seconds.
- **Query guard.** `app/database.py` also rejects anything other than a single
  `SELECT` statement: no comments, no multiple statements, no write keywords.
- **No personal details.** The user can't read customer names, usernames,
  cities, zip codes or marketplace buyer IDs, only state and country.
- **No credentials exposed.** Nothing from `.env` is logged or returned by
  the API.
- **Browser access.** Only the dashboard's own address may call the API (CORS).

## Setup (once)

From the repository root, with the PostgreSQL commands on your PATH:

```sh
export PATH="/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"
set -a; source .env; set +a                      # your admin connection settings
PGDATABASE=goodwill_db_test psql -X -f chatbot/setup_readonly_role.sql

cd chatbot
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env                             # then put your key in ANTHROPIC_API_KEY
```

- **API key.** Get one from console.anthropic.com and paste it into
  `chatbot/.env`, which is git-ignored. Never commit it or paste it into a chat.
- **Other databases.** To point the chatbot elsewhere, run the setup script
  against that database and change `CHATBOT_DATABASE_URL`.

## Run

```sh
cd chatbot
.venv/bin/python -m uvicorn app.main:app --port 8001
```

Then start the dashboard (`cd frontend && npm run dev`) and click **Ask the data**.

**Notes:**
- `http://127.0.0.1:8001/api/health` reports whether the database is reachable
  and whether an API key is set.
- Run the service from a terminal you've approved in Postgres.app. Postgres.app
  refuses password-free connections from apps you haven't approved.
- The dashboard looks for the service at `http://127.0.0.1:8001`. Override it
  with `VITE_CHAT_URL` in `frontend/.env.local`.

## Model and cost

- **Model.** It uses `claude-opus-5-5` with adaptive thinking at `high` effort.
  Change the model with `CHATBOT_MODEL`.
- **Refusal fallback.** Server-side refusal fallback (`fallbacks: "default"`) is
  enabled: if Claude declines a request on safety grounds, the API retries it on
  Anthropic's recommended fallback model.
- **Cost.** Each question is a few API calls (one per query round), billed to the
  API key's account. The system prompt is cached between calls to reduce cost.

## Tests

```sh
cd chatbot
.venv/bin/python -m unittest discover -s tests -v
```

The tests use a scripted stand-in for Claude, so they make no API calls. They
cover:
- **The SQL guard.**
- **The number check.**
- **The agent loop:** verified answers, correction and withholding, query
  errors, and refusals.
- **The real read-only user against `goodwill_db_test`:** denied personal
  columns, blocked writes, the row limit, and the schema the model sees.

## Files

| File | Purpose |
|---|---|
| `app/main.py` | HTTP API: `POST /api/chat`, `GET /api/health` |
| `app/agent.py` | System prompt, `run_sql` tool and the Claude tool loop |
| `app/verify.py` | Checks every number in an answer against the query results |
| `app/database.py` | Read-only query execution, SQL guard, schema description |
| `app/config.py` | Settings from the environment and `chatbot/.env` |
| `setup_readonly_role.sql` | Creates the `goodwill_chatbot` read-only user |
| `../frontend/src/components/ChatPanel.jsx` | The dashboard chat panel |
