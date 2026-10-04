# Monthly email feature

The email renderer in `app/monthly_email.py` takes the shared monthly
`DashboardReport` and recipient settings. It formats values without querying
the database or duplicating dashboard calculations. Preview, manual delivery
and the scheduler all build that report from PostgreSQL through the same
calculations as the dashboard (`app/dashboard.py`, via `app/reports.py`), so the
email and the dashboard always show the same figures. Mock orders are used only
by tests; output built from them is still marked as a demo.

The short snapshot highlights revenue, transactions, and units sold, with
average selling price as a secondary metric. Up to three factual observations
describe revenue movement against the previous month, the leading revenue
channel (including ties), and eBay returning buyers. These are observations,
not judgments about overall company health. Buyer retention is eBay-only.

A compact HTML bar chart includes exact revenue and transaction values for
each marketplace. Bars are relative to the highest channel revenue; they do
not represent market share. Negative values retain their numbers without a
bar. All vendors outside eBay, Amazon, and ShopGoodwill are grouped as Other
vendors. Inline styles and table bars require no hosted images or scripts.

Missing values remain unavailable. Brief interpretation notes stay in the
footer; lengthy metric definitions and unavailable-metric lists are omitted
from the email. The detailed report retains those fields. Real mail-client
rendering may vary; the plain-text alternative contains the same snapshot.

## Local preview

From `backend`, start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open <http://127.0.0.1:8000/api/email/monthly/preview/html?date=2026-09-01>.
Previewing does not send an email and does not require recipient settings.

## Local delivery and scheduling

In a separate terminal from `backend`, start the capture server:

```powershell
.\.venv\Scripts\python.exe -m app.demo_smtp
```

Set recipients using `PUT /api/email/recipients` in
<http://127.0.0.1:8000/docs>. Use `POST /api/email/monthly/send-demo` for a
manual capture. These messages are saved under `backend/local-state/demo-mail`
and never delivered to real inboxes. The sender `reports@example.test` does
not require an account for local capture.

Run `python -m app.scheduler` from the backend environment for scheduled local
delivery. It checks every minute and processes the previous calendar month
starting at 8 AM America/New_York on the first day of the month. The computer,
scheduler, and capture server must be running. Restarting after the scheduled
date catches up the latest completed month; it does not backfill older months.
The local delivery history prevents repeat scheduled captures. Manual captures
are separate from that history.

## Validation

From `backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
