# Goodwill Michiana — E-Commerce Insights

A local dashboard and reporting app built for **SprintHack@ND 2026**. It turns marketplace exports into a shared PostgreSQL database, presents daily and monthly performance, and sends a concise monthly email snapshot. An optional **Ask the data** chatbot answers questions using read-only database queries.

> **Demo data:** the included exports and historical dataset are synthetic. They do not represent actual Goodwill results or real customers.

## Features

- **Daily reporting:** revenue, orders, and available buyer counts by marketplace, with charts and trends.
- **Monthly analytics:** revenue growth, sales effectiveness, category performance, eBay buyer activity, and a watch list.
- **Monthly email:** headline metrics, observed trends, and marketplace revenue bars; preview, local capture, or real SMTP delivery.
- **Source ingestion:** parse Amazon, eBay, and ShopGoodwill exports, archive the originals, and load normalized records.
- **Optional data chatbot:** answers backed by SQL results, with visible queries and numeric verification.

The backend calculates metrics for the dashboard and email from the same database. The email groups vendors outside Amazon, eBay, and ShopGoodwill as **Other vendors**. Buyer retention uses **eBay only**, because comparable buyer identities are unavailable from the other supplied sources.

## Requirements

| Requirement | Purpose |
|---|---|
| Python **3.10+** | Backend and optional chatbot; Python 3.12 was used for backend validation |
| Node.js **22.12+** (or 20.19+) and npm | React/Vite frontend; required versions come from the dependency lockfile |
| PostgreSQL **17**, including `psql` and `createdb` | Local database, migrations, and data loading |
| Git | Download the repository |
| Internet access during setup | Install Python and npm dependencies |
| SMTP account and credentials, optional | Real email delivery; Gmail requires an app password |
| Anthropic API key and internet access, optional | Chatbot requests, billed to the key's account |

Python and npm packages are declared in `backend/requirements.txt`, `chatbot/requirements.txt`, and `frontend/package.json`. PostgreSQL Stack Builder and Node's optional native build tools are not required by this setup.

**This guide uses Windows PowerShell.** On macOS/Linux, use `python3` instead of `py`, `.venv/bin/python` instead of `.venv\Scripts\python.exe`, and `npm` instead of `npm.cmd`. PostgreSQL installation/service management depends on your platform. The application ports and folder layout are the same.

## Setup

### 1. Get the project

```powershell
git clone https://github.com/pryan24-nd/SprintHack.git
cd SprintHack
```

All setup commands below start from this **repository root**, unless a section explicitly changes folders. If you already have the final checkout, skip cloning.

Check your tools:

```powershell
py --version
node --version
npm.cmd --version
psql --version
```

If PostgreSQL commands are not found, add the installed client directory to this terminal's PATH. For the default Windows installation:

```powershell
$env:Path = "C:\Program Files\PostgreSQL\17\bin;" + $env:Path
```

### 2. Install the backend dependencies

```powershell
py -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Skip environment creation if `backend/.venv` already exists. Using the environment's Python directly avoids PowerShell activation-policy issues.

### 3. Configure your local connection

Create the root configuration file **only if it does not already exist**:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally:

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=goodwill_db
PGUSER=your_verified_local_postgresql_role
PGPASSWORD=your_local_postgresql_password
```

Replace the role and password with credentials for your own PostgreSQL installation. A username in `.env` does not create a database account. The installer commonly creates `postgres`, but verify your local login. The setup role needs database creation and schema permissions. Password-free local authentication can leave `PGPASSWORD` empty; password-based connections require a password or a protected password file.

The backend and scheduler automatically load the **root `.env`**. Existing shell variables take precedence. Do not create a separate `backend/.env`. Never commit passwords, app passwords, API keys, or private recipient files; `.env` and local state are git-ignored.

Optional root settings:

| Variable | Default | Meaning |
|---|---|---|
| `REPORTING_TIMEZONE` | `America/New_York` | Calendar boundaries for reports |
| `DASHBOARD_REVENUE_METRIC` | `merchandise_before_refunds` | Also supports `merchandise_after_refunds` and `transaction_revenue` |
| `DASHBOARD_ALLOWED_ORIGINS` | Empty | Additional browser origins; local origins are supported |
| `DASHBOARD_STATE_DIR` | `backend/local-state` | Recipient settings and scheduling history |

### 4. Start PostgreSQL and create the database

PostgreSQL must be running independently of the Python app. On Windows, check it with:

```powershell
Get-Service -Name postgresql-x64-17
```

If stopped, run this in a separate **administrator PowerShell** window:

```powershell
Start-Service -Name postgresql-x64-17
```

Service names can differ for custom installations. Closing the administrator terminal does not stop the service.

Unlike the backend, `psql` does **not** automatically load `.env`. Set the connection variables for SQL commands explicitly, matching your root file:

```powershell
$env:PGHOST = "localhost"
$env:PGPORT = "5432"
$env:PGUSER = "your_verified_local_postgresql_role"
$env:PGDATABASE = "goodwill_db"
```

The commands below use `-W` to prompt privately for the PostgreSQL password. Check whether the database exists:

```powershell
psql -X -W -d postgres -At -c "SELECT datname FROM pg_database WHERE datname = 'goodwill_db';"
```

If it prints `goodwill_db`, reuse it. If the query succeeds with no result, create it:

```powershell
createdb -W goodwill_db
```

If authentication fails, fix the login before continuing. Do not delete or recreate an existing database.

Apply migrations:

```powershell
psql -X -W -v ON_ERROR_STOP=1 -d goodwill_db -f database/migrate.sql
```

Migrations create tables, a materialized order-total view, and reference seeds. Reapplication skips registered migrations and preserves existing rows. **Migrations alone do not load sales data.**

### 5. Load the demonstration data

For a dashboard with historical trends, load the included normalized synthetic dataset:

```powershell
psql -X -W -v ON_ERROR_STOP=1 -d goodwill_db -f test-data/historical/load_historical.sql
```

Run this from the repository root so CSV paths resolve correctly. It adds roughly three years of history (**November 2023–October 2026**), keeps existing rows, skips already-present keys, and refreshes `sales_order_mv`. See the [historical dataset guide](test-data/historical/README.md) for assumptions and date coverage.

To demonstrate parsing the source export fixtures as well, run from the root:

```powershell
.\backend\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; import runpy; load_dotenv('.env', override=False); runpy.run_path('ingestion/ingest.py', run_name='__main__')"
```

This explicitly loads `.env` before running ingestion. `psql` must be on PATH, and `PGDATABASE` must identify the intended database. Ingestion archives source files and uses an insert-only loader that refreshes totals. For custom inputs, dry runs, and provisional enrichment rules, see [ingestion/README.md](ingestion/README.md).

### 6. Install the frontend dependencies

```powershell
cd frontend
npm.cmd ci
cd ..
```

`npm ci` uses the committed lockfile. Use `npm.cmd` on Windows if PowerShell refuses to run `npm.ps1`.

## Run the dashboard

Keep these processes in **separate terminals**. Start each terminal at the repository root.

**Terminal 1 — backend:**

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```powershell
cd frontend
npm.cmd run dev
```

Open the URL printed by Vite (usually **http://localhost:5173**). If that port is occupied, Vite may select another port. Keep both terminals open; press **Ctrl+C** in each to stop the processes.

| URL | Purpose |
|---|---|
| http://127.0.0.1:8000/api/health | Backend process check; does not verify PostgreSQL |
| http://127.0.0.1:8000/docs | Interactive API documentation |
| http://127.0.0.1:8000/api/reports/monthly?month=2026-09 | Database-backed monthly report |
| http://127.0.0.1:8000/api/email/monthly/preview/html?date=2026-09-01 | Email preview; sends nothing |

For the included data, choose **September 2026** for a completed monthly report. The initial dashboard selection follows the current date; dates outside the dataset can show zero activity. Daily reports exclude today because it is incomplete.

To change service URLs, create the git-ignored `frontend/.env.local`:

```dotenv
VITE_API_URL=http://127.0.0.1:8000/api
VITE_CHAT_URL=http://127.0.0.1:8001
```

Restart Vite after changing frontend environment settings.

## Monthly email

### Preview and real sending

Preview works with the backend and database running and requires no SMTP credentials. For real Gmail delivery, add these privately to root `.env`:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=your-sender@gmail.com
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-generated-app-password
```

Enable Google 2-Step Verification and create an [app password](https://support.google.com/accounts/answer/185833). Use that generated password, not the normal Gmail password. Some managed accounts restrict app passwords. Restart the backend after editing `.env`.

In `/docs`, expand **POST `/api/email/monthly/send`**, select **Try it out**, set `date` to `2026-09-01`, and enter runtime recipients:

```json
{"recipients": ["recipient@example.com", "another@example.com"]}
```

Clicking **Execute sends a real email**. Recipients do not belong in `.env`; this manual request does not save them. `accepted_by_smtp` means the server accepted the message, not guaranteed inbox delivery. Check spam as well. Partial or uncertain failures should be checked before retrying, because repeated manual requests can send duplicates.

### Automatic monthly delivery

Save the recipient list at runtime through **PUT `/api/email/recipients`** using the same JSON format. Then start a third terminal from `backend`:

```powershell
.\.venv\Scripts\python.exe -m app.scheduler --delivery smtp
```

The scheduler checks once per minute and sends the previous calendar month at or after **8 AM America/New_York on the first day of the month**. Starting late can send the latest completed month immediately. It does not backfill all older months. The computer, PostgreSQL, and scheduler must remain running; the API is needed to manage recipients, but scheduling runs separately.

Scheduling history prevents repeated scheduled delivery of the same month. Real and demo histories are separate; uncertain delivery is held for review. History is available at `/api/email/schedule/history?delivery=smtp`.

### Test without a real account

From `backend`, start the local capture server in another terminal:

```powershell
.\.venv\Scripts\python.exe -m app.demo_smtp
```

Save recipients using the PUT endpoint, then use **POST `/api/email/monthly/send-demo`**. Messages are saved as `.eml` files under `backend/local-state/demo-mail`; no external inbox receives them. `python -m app.scheduler --delivery demo` schedules local capture instead. See [backend/EMAIL.md](backend/EMAIL.md) for delivery details.

## Optional: Ask the data chatbot

The dashboard and email work without this service. Chatbot requests require an Anthropic API key and may incur API charges.

From the root, using the administrator PostgreSQL connection variables set earlier:

```powershell
psql -X -W -v ON_ERROR_STOP=1 -d goodwill_db -f chatbot/setup_readonly_role.sql
py -m venv chatbot/.venv
.\chatbot\.venv\Scripts\python.exe -m pip install -r chatbot/requirements.txt
if (-not (Test-Path chatbot/.env)) { Copy-Item chatbot/.env.example chatbot/.env }
```

The SQL script creates the `goodwill_chatbot` read-only role but **does not set its password**. On password-authenticated Windows installations, open an administrator SQL session:

```powershell
psql -X -W -d goodwill_db
```

Inside `psql`, set a password privately, then exit:

```text
\password goodwill_chatbot
\q
```

Configure `chatbot/.env` locally:

```dotenv
ANTHROPIC_API_KEY=your-private-key
CHATBOT_DATABASE_URL=postgresql://goodwill_chatbot:your-url-encoded-password@localhost:5432/goodwill_db
CHATBOT_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Use the same database as the dashboard; the supplied chatbot example defaults to `goodwill_db_test` and must be changed for this setup. Percent-encode special characters in the URL password. Use the restricted chatbot role, not the database administrator account.

In a separate terminal:

```powershell
cd chatbot
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open **Ask the data** on the dashboard. Check http://127.0.0.1:8001/api/health for database connectivity and API-key configuration. Queries run read-only; responses expose query results for inspection. Numeric verification is a safeguard, not a guarantee that all wording is correct. See [chatbot/README.md](chatbot/README.md) for model settings and limitations.

## Validation

Backend tests (from root; SMTP tests simulate delivery):

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd ..
```

Ingestion tests (from root):

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Frontend checks (from `frontend`):

```powershell
npm.cmd run build
npm.cmd run lint
```

For SQL tests, create **`goodwill_db_test` only if missing**, apply `database/migrate.sql` twice, then run `tests/database/test_database.sql` with `psql -X -W -v ON_ERROR_STOP=1 -d goodwill_db_test -f <file>`. Never run database behavior tests against `goodwill_db`. Tests roll back their rows, but sequence values may advance. Backend database comparison tests are enabled with `DASHBOARD_TEST_PGDATABASE=goodwill_db_test` and require a populated test database. See [database/README.md](database/README.md); use the current `database/migrate.sql` path where older examples still say `backend/database/migrate.sql`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `npm` is not recognized | Install Node.js, then completely reopen the IDE/terminal to refresh PATH |
| PowerShell blocks `npm.ps1` | Use `npm.cmd` |
| `No module named dotenv` or `psycopg` | Install `backend/requirements.txt` with the same environment's Python used to launch the backend |
| Health works, but report returns 503 | Check PostgreSQL service, verified local credentials, database name, migrations, and root `.env`; restart the backend after edits |
| Report shows zeros | Migrations do not import sales; load the dataset and select a month with data |
| Order totals need refreshing | Run `psql -X -W -d goodwill_db -c "REFRESH MATERIALIZED VIEW public.sales_order_mv;"` after an import |
| Browser cannot reach the API | Keep the backend terminal running; check ports and `VITE_API_URL` |
| Gmail rejects sending | Verify sender, app password, account restrictions, and SMTP settings; check delivery before retrying |
| Chatbot cannot connect | Verify its read-only role/password and `CHATBOT_DATABASE_URL`; its default database differs from the dashboard |
| Environment edits have no effect | Restart the affected service; existing shell variables override `.env` |

## Scope and limitations

- All included data is synthetic. Ingestion enrichment and fee/timezone assumptions are documented, provisional rules.
- Margins, labor productivity, and some customer metrics cannot be computed reliably from the available facts. Missing values display as unavailable rather than fabricated zeroes.
- Revenue defaults to item revenue after discounts **before refunds**, excluding shipping, tax, and fees; alternative formulas are configurable. This is operational reporting, not an accounting close.
- Business Central integration, journal entries, AR invoices, and automated financial posting are outside this implementation.
- Services are intended for a local hackathon demo. This setup binds Python APIs to loopback and does not provide production authentication or hosted deployment.

## Project structure

```text
backend/              FastAPI reporting, shared calculations, email, and scheduling
frontend/             React, Vite, Tailwind, and Recharts dashboard
chatbot/              Optional read-only SQL chatbot service
database/             PostgreSQL schema, reference seeds, and migration runner
ingestion/            Export parsing, normalization, archiving, and SQL loading
test-data/            Source-like exports and synthetic historical CSVs
tests/                Ingestion tests and SQL database behavior tests
docs/                 Product context, architecture, decisions, and database contract
```

For implementation details, see [DATABASE_SPEC.md](docs/DATABASE_SPEC.md), [backend/README.md](backend/README.md), and [frontend/README.md](frontend/README.md). Older milestone sections describe earlier stages; the startup sequence above targets the final integrated app.
