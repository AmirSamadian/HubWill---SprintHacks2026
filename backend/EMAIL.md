# Monthly email feature

## Real Gmail delivery

Configure these privately in the git-ignored **root** `.env`, alongside the
existing database settings. Do not replace the PG settings or commit this file.
The application explicitly loads root `.env` through `app.config`.

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=your-sender@gmail.com
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-app-password
```

Create an app password with Google 2-Step Verification enabled:
<https://support.google.com/accounts/answer/185833>. Account restrictions may
prevent app passwords. Enter the generated password privately, not a normal
Google password. Gmail SMTP settings:
<https://support.google.com/mail/answer/7104828>.

Restart the API after changing environment configuration. In `/docs`, use
`POST /api/email/monthly/send`, choose the month with its `date` query, and
submit runtime recipients:

```json
{"recipients": ["recipient@example.com", "another@example.com"]}
```

Comma, semicolon, and newline-separated strings are also accepted. An empty
or invalid list fails validation. This endpoint sends real mail immediately;
manual requests are separate sends and do not update saved recipients. The
response `accepted_by_smtp` means server acceptance, not guaranteed inbox
delivery. Provider failures and partial refusal require checking delivery
before retrying. Addresses are envelope recipients and hidden from one another.
Keep this unauthenticated local demo API bound to `127.0.0.1`.

For monthly automatic real delivery, first set the saved runtime recipient
list with `PUT /api/email/recipients`. This is necessary because no user is
present to type addresses when the scheduled time arrives. Then run:

```powershell
.\.venv\Scripts\python.exe -m app.scheduler --delivery smtp
```

Starting this scheduler after the first day catches up the latest completed
month and can send immediately. It runs at 8 AM Eastern on the first of each
month and uses a separate ledger under `backend/local-state/smtp`. Real
history is available at `/api/email/schedule/history?delivery=smtp`.
Uncertain sends are marked `needs_review` rather than automatically repeated.
The computer and scheduler must remain running. `--delivery demo` remains the
default local capture mode.

Validation uses mocked SMTP, never real credentials or external delivery.

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
