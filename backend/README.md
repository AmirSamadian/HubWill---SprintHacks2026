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

- Marketplace rows are ShopGoodwill, Amazon, eBay, and Other. Other combines all
  remaining vendors' revenue, transactions, and units for the selected period.
  Original vendor names remain in source records; no separate vendor rows or
  duplicate subtotals are added. This applies to daily, monthly, and yearly reports.
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

## Milestone 3: monthly email preview and recipient settings

Update dependencies, then restart the server if needed:

```powershell
# Run from backend.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- `GET /api/email/recipients`: read the saved recipient list (empty initially).
- `PUT /api/email/recipients`: validate and replace the saved list.
- `GET /api/email/monthly/preview?date=2026-09-01`: JSON subject, recipients,
  plain text and HTML content.
- `GET /api/email/monthly/preview/html?date=2026-09-01`: view the HTML email in a browser.

Use `/docs` and the recipient PUT endpoint's **Try it out** action with:

```json
{"recipients": "team@example.com, judge@example.org"}
```

An array is also accepted:

```json
{"recipients": ["team@example.com", "judge@example.org"]}
```

Comma, semicolon and newline separators are supported. Duplicate addresses are
removed case-insensitively. Up to 50 input addresses are accepted. Addresses are
syntax-validated; this does not confirm that a mailbox exists. Any invalid address
rejects the update with HTTP 422, preserving the previous list. An empty array
clears recipients. These endpoints do not send email or start a scheduler.

Settings are stored in `backend/local-state/recipients.json`, excluded by the
root `.gitignore`. `DASHBOARD_STATE_DIR` may override the local state directory
for testing. Do not manually commit recipient settings. Storage failures return
HTTP 500 instead of pretending the settings were saved.

The preview contains revenue, previous-month change, transactions, units, average
selling price, the four marketplace rows, eBay-only returning buyer metrics, and
unavailable-metric explanations. Mock data is visibly labeled. Sender verification,
delivery, and the first-of-month schedule will be implemented in the next increment.

After tests pass, commit from the repository root on `BackEnd`:

```powershell
git add .gitignore backend
git diff --cached
git commit -m "feat: add monthly email preview and recipient settings"
```

## Milestone 4: account-free local SMTP demo

No sender account, password, API key, or domain is required. This mode captures
mail locally and does **not** deliver it to real inboxes. Sender placeholder:
`reports@example.test`. Captures are `.eml` files under
`backend/local-state/demo-mail/`, excluded from Git.

1. From `backend`, update dependencies:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

2. In one terminal at `backend`, start the dummy server:

   ```powershell
   .\.venv\Scripts\python.exe -m app.demo_smtp
   ```

3. In another terminal at `backend`, start the API:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

4. At http://127.0.0.1:8000/docs, configure recipients if necessary, then execute
   `POST /api/email/monthly/send-demo` with `date` set to `2026-09-01`.
5. Expect `delivery_status: captured_locally`. The SMTP terminal prints the saved
   `.eml` path. Open the file in an email client or text editor to inspect it.

Both processes stop with Ctrl+C. Missing recipients return HTTP 400; an unavailable
capture server returns HTTP 503. Each manual demo request creates another capture.
The first-of-month scheduler is a separate next increment, not yet implemented.

After verification, commit from the repository root on `BackEnd`:

```powershell
git add backend
git diff --cached
git commit -m "feat: add account-free local SMTP capture demo"
```
