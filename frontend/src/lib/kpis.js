// Labels and display rules for the Goodwill Michiana KPIs. The values, their
// month-over-month changes and category figures are all computed by the
// backend (backend/app/dashboard.py, per DECISIONS D008); this file only reads
// them. A null value means the database cannot supply it and shows as "—".

/** Each KPI: label, format key (see fmt in ./format.js) and which direction is good. */
const kpi = (label, format) => ({ label, format, better: 'up' })

export const KPIS = {
  // Financial
  revenue: kpi('Total E-Commerce Revenue', 'currency'),
  revenueGrowthYoY: kpi('Revenue Growth % (YoY)', 'signedPct'),
  grossMarginPct: kpi('Gross Margin %', 'pct'),
  netMarginPct: kpi('Net Margin %', 'pct'),

  // Sales
  unitsSold: kpi('Units Sold', 'number'),
  avgSellingPrice: kpi('Average Selling Price (ASP)', 'currencyCents'),
  listingsCreated: kpi('Total Listings Created', 'number'),
  medianSalePrice: kpi('Median Sale Price', 'currencyCents'),

  // Customer & marketplace
  buyers: kpi('Number of Buyers', 'number'),
  repeatBuyerRate: kpi('Repeat Buyer Rate', 'pct'),
  newBuyers: kpi('New Buyers', 'number'),
  satisfaction: kpi('Customer Satisfaction Rating', 'rating'),
}

// The KPIs that make up the one-page COO operating view, in groups. Labor and
// inventory metrics are left out because that data isn't available.
export const SCORECARD = [
  {
    id: 'financial',
    eyebrow: 'Financial',
    kpis: ['revenue', 'revenueGrowthYoY', 'netMarginPct'],
  },
  {
    id: 'sales',
    eyebrow: 'Sales',
    kpis: ['unitsSold', 'avgSellingPrice', 'medianSalePrice'],
  },
  {
    id: 'categories',
    eyebrow: 'Top categories',
    kpis: ['topCategoriesByRevenue', 'topCategoriesByMargin'],
  },
]

/** Value of one KPI for a report, or null if the backend could not compute it. */
export function kpiValue(id, report) {
  return report?.kpis?.[id] ?? null
}

/** Month-over-month change for a KPI ({ kind, value }), or null when it isn't a fair comparison. */
export function kpiDelta(id, report) {
  return report?.kpiDeltas?.[id] ?? null
}

/** Category rows (sales, units, ASP; margin fields are null without cost data). */
export function categoryRows(report) {
  return report.categories ?? []
}

/** Top categories by a figure; categories without that figure are left out. */
export function topCategories(report, key, n = 10) {
  return categoryRows(report)
    .filter((c) => c[key] !== null && c[key] !== undefined)
    .sort((a, b) => b[key] - a[key])
    .slice(0, n)
}
