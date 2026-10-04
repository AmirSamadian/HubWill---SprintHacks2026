# Goodwill Michiana E-Commerce Dashboard (frontend)

React + Tailwind + Recharts dashboard for the Goodwill Michiana KPI framework.

```bash
cd frontend
npm install
npm run dev
```

## Tabs

- **Daily Report**: the nightly channel breakdown. Shows revenue and customers per marketplace plus the Total E-Commerce row, charts comparing marketplaces, and a 14-day trend. Pick the day with the date picker or the ← → buttons.
- **Monthly Analytics**: pick a month/year from the dropdown or step through months with ← →. The top of the page is the COO scorecard:
  - financial headline (revenue, YoY growth, net margin)
  - **watch list** of metrics that moved the wrong way
  - revenue by marketplace
  - sales effectiveness
  - top 10 categories by revenue and margin, plus repeat buyer rate

  A tabbed "Detailed performance" card holds the supporting charts (Financial, Categories, Customers).

  Labor and inventory metrics are intentionally left out because that data isn't available.

The watch list rules live in [`src/lib/watchlist.js`](src/lib/watchlist.js) as plain data (`watchItems(report, previous)`), so a future written report can reuse them.

Every chart has a **Table** toggle that shows the underlying numbers.

## Where the data comes from

All numbers come from the backend (`backend/`), which reads the PostgreSQL
database. Start the backend before the dashboard (see `backend/README.md` →
"Database integration"). [`src/api/index.js`](src/api/index.js) is the only
file that talks to it. By default it calls `http://127.0.0.1:8000/api`; set
`VITE_API_URL` in `frontend/.env.local` to change that.

It uses three endpoints:
- `GET /reports/daily?date=YYYY-MM-DD`
- `GET /reports/monthly?month=YYYY-MM`
- `GET /reports/monthly/history?month=YYYY-MM&months=12`

**The backend computes every metric:** revenue, growth, ASP, repeat buyers,
month-over-month changes, top categories and the watch list. This follows
DECISIONS D008. [`src/lib/kpis.js`](src/lib/kpis.js) and
[`src/lib/watchlist.js`](src/lib/watchlist.js) only hold labels and read those
values.

**Unavailable values show as "—".** A value the database can't supply comes back
as `null` and is never shown as 0. For example:
- margins, because there's no cost data
- customer satisfaction, because the rating scale isn't agreed
- daily customers on Amazon and ShopGoodwill, which don't share buyer identity

**Errors are shown on the page.** If the backend isn't running or returns an
error, the page shows the reason.

## Adding a marketplace

Add an entry to [`src/config/channels.js`](src/config/channels.js), for example `{ id: 'mercari', name: 'Mercari' }`. It picks up the next chart color and gets its own row in the nightly table and in every marketplace chart. A marketplace that shows up in the data but isn't in the config still appears, using the name the data provides.
