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

All numbers are currently **temporary placeholders** in [`src/api/placeholderData.js`](src/api/placeholderData.js). Every export there has a `TODO(database)` comment that describes the data that should replace it.

[`src/api/index.js`](src/api/index.js) is the only place that reads that file. To connect the database, do one of these:

1. Replace the placeholder sections in `fetchDailyReport` / `fetchMonthlyReport` with real queries, keeping the same object shape.
2. Set `VITE_API_URL` in `frontend/.env.local`. The dashboard then calls:
   - `GET /reports/daily?date=YYYY-MM-DD`
   - `GET /reports/monthly?month=YYYY-MM`
   - `GET /reports/monthly/history?month=YYYY-MM&months=12`

The backend only supplies raw facts like revenue, costs, units and buyers. All ratios (margins, sell-through, repeat rate, and so on) are defined once in [`src/lib/kpis.js`](src/lib/kpis.js).

## Adding a marketplace

Add an entry to [`src/config/channels.js`](src/config/channels.js), for example `{ id: 'mercari', name: 'Mercari' }`. It picks up the next chart color and gets its own row in the nightly table and in every marketplace chart. A marketplace that shows up in the data but isn't in the config still appears, using the name the data provides.
