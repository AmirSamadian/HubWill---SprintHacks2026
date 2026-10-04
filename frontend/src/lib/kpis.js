// Every KPI in the Goodwill Michiana framework, computed from the raw monthly
// report. The backend only has to supply raw facts; all ratios live here so the
// definitions are written down in exactly one place.

import { change } from './format'

const safeDiv = (a, b) => (b ? a / b : null)

/**
 * Each KPI: label, format key (see fmt in ./format.js), how to compute it, and
 * which direction is good. `additive` KPIs are totals that grow with the number
 * of days, so they are not compared month-over-month while a month is partial.
 */
export const KPIS = {
  // Financial
  revenue: { label: 'Total E-Commerce Revenue', format: 'currency', better: 'up', additive: true, get: (r) => r.financial.revenue },
  revenueGrowthYoY: { label: 'Revenue Growth % (YoY)', format: 'signedPct', better: 'up', get: (r) => change(r.financial.revenue, r.financial.revenuePriorYear) },
  grossMarginPct: { label: 'Gross Margin %', format: 'pct', better: 'up', get: (r) => safeDiv(r.financial.revenue - r.financial.cogs, r.financial.revenue) },
  netMarginPct: { label: 'Net Margin %', format: 'pct', better: 'up', get: (r) => safeDiv(netProfit(r), r.financial.revenue) },

  // Sales
  unitsSold: { label: 'Units Sold', format: 'number', better: 'up', additive: true, get: (r) => r.sales.unitsSold },
  avgSellingPrice: { label: 'Average Selling Price (ASP)', format: 'currencyCents', better: 'up', get: (r) => safeDiv(r.financial.revenue, r.sales.unitsSold) },
  listingsCreated: { label: 'Total Listings Created', format: 'number', better: 'up', additive: true, get: (r) => r.listings.created },
  medianSalePrice: { label: 'Median Sale Price', format: 'currencyCents', better: 'up', get: (r) => r.sales.medianSalePrice },

  // Customer & marketplace
  buyers: { label: 'Number of Buyers', format: 'number', better: 'up', additive: true, get: (r) => r.customers.buyers },
  repeatBuyerRate: { label: 'Repeat Buyer Rate', format: 'pct', better: 'up', get: (r) => safeDiv(r.customers.repeatBuyers, r.customers.buyers) },
  newBuyers: { label: 'New Buyers', format: 'number', better: 'up', additive: true, get: (r) => r.customers.newBuyers },
  satisfaction: { label: 'Customer Satisfaction Rating', format: 'rating', better: 'up', get: (r) => r.customers.satisfaction },
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

function netProfit(r) {
  return r.financial.revenue - r.financial.cogs - r.financial.operatingExpenses
}

/** Value of one KPI for a report, or null if it can't be computed. */
export function kpiValue(id, report) {
  try {
    return KPIS[id].get(report) ?? null
  } catch {
    return null
  }
}

/** Month-over-month change for a KPI, or null when it isn't a fair comparison. */
export function kpiDelta(id, report, previous) {
  const kpi = KPIS[id]
  if (!previous || (kpi.additive && report.isPartial)) return null
  const cur = kpiValue(id, report)
  const prev = kpiValue(id, previous)
  if (cur === null || prev === null) return null
  // Percent and score KPIs compare in points; everything else as relative change.
  if (['pct', 'signedPct'].includes(kpi.format)) return { kind: 'points', value: cur - prev }
  if (kpi.format === 'score') return { kind: 'score', value: cur - prev }
  return { kind: 'relative', value: change(cur, prev) }
}

/** Category rows with derived margin and ASP. */
export function categoryRows(report) {
  return report.categories.map((c) => ({
    ...c,
    margin: c.revenue - c.cost,
    marginPct: safeDiv(c.revenue - c.cost, c.revenue),
    asp: safeDiv(c.revenue, c.unitsSold),
  }))
}

export function topCategories(report, key, n = 10) {
  return [...categoryRows(report)].sort((a, b) => b[key] - a[key]).slice(0, n)
}
