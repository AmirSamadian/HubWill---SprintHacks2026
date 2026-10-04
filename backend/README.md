# Dashboard backend

Milestone 1 provides a local FastAPI server and a health endpoint. PostgreSQL,
dashboard reports, and monthly emails will be added in separate increments.

## Run locally

From the repository root in PowerShell:

```powershell
cd backend
# Only create the environment if .venv does not already exist.
py -m venv .venv
# Install dependencies using the environment's Python directly; activation is optional.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If your environment already exists, skip the `py -m venv .venv` line.
If `py` is unavailable, try `python -m venv .venv` when creating a new environment.

Open http://127.0.0.1:8000/api/health and expect:

```json
{"status":"ok","service":"goodwill-dashboard-backend"}
```

Interactive API documentation is at http://127.0.0.1:8000/docs.
This health check verifies the API process only, not database readiness.

The root `.gitignore` excludes `.venv`, Python caches, and local `.env` secrets.

## First commit checkpoint

After verifying the endpoint, use a second terminal at the repository root:

```powershell
git add .gitignore backend
git diff --cached
git commit -m "chore: scaffold dashboard backend"
```

Keep this change on the existing `BackEnd` branch. Review everything staged before
committing, including any changes staged previously.

## Milestone 2: mock dashboard reports

The health endpoint is unchanged. Report examples:

- Daily: http://127.0.0.1:8000/api/dashboard?period=day&date=2026-10-03
- Monthly: http://127.0.0.1:8000/api/dashboard?period=month&date=2026-09-01
- Yearly: http://127.0.0.1:8000/api/dashboard?period=year&date=2026-01-01

All reports explicitly identify synthetic mock data. Daily revenue for October 3
is $325 across four transactions and nine units. September revenue is $400;
September has two distinct eBay buyers, one of whom bought before September.

### Files and responsibilities

- `app/main.py`: HTTP routes and validation.
- `app/models.py`: API response structure, independent of database column names.
- `app/repository.py`: normalized paid-order fields and the replaceable mock source.
- `app/reports.py`: calendar ranges and shared calculations.
- `tests/test_reports.py`: calculation and boundary checks.

The PostgreSQL adapter will map the team's schema to `PaidOrder` values. The mock
adapter loads history for simplicity; SQL aggregation can replace this later if
data volume requires it. Normalized orders must be unique by marketplace and
order ID. Reporting dates represent dates in America/New_York; timestamp
conversion belongs in the future PostgreSQL adapter. Never put database credentials
in the frontend.

### Metric definitions

- Transactions count paid orders, not unique people; order IDs are channel-scoped.
- Revenue is paid item revenue after discounts, excluding shipping, taxes and fees.
  Final refund treatment remains to be agreed when the real schema arrives.
- Average selling price is item revenue divided by units, not transactions.
- Month/year unique and returning buyer metrics use eBay only. Returning means a
  purchase before the reporting period started; multiple orders within the period
  do not by themselves make a buyer returning. This is not cohort retention.
- Missing eBay buyer IDs are excluded from buyer calculations and counted separately.
- Comparisons use the previous full calendar period, not matched elapsed days.
- No comparison baseline or no buyers produces `null` rates, not invented zeros.
- Currency amounts and percentages serialize as exact decimal strings.
- Yearly charts use monthly buckets; other charts use daily buckets, including zeros.
- Net margin and sell-through remain unavailable until their required inputs exist.

Run verification from `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

After verification, from the repository root:

```powershell
git add backend
git diff --cached
git commit -m "feat: add dashboard report contracts and mock data"
```
