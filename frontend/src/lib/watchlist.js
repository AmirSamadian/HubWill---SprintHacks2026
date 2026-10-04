// Item-level early warnings for a month: item types (e.g. couches in Home)
// whose sales fell versus the prior month. This is plain data (no UI) so the
// dashboard's watch list and any future written report share the same rules.

import { change, fmt } from './format'

// An item is flagged when its revenue drops by at least this much…
export const ITEM_DROP_THRESHOLD = -0.15
// …and it sold at least this much last month (so tiny items don't add noise).
export const MIN_PRIOR_REVENUE = 500

/**
 * Returns the flagged items, biggest dollar loss first:
 * [{ id, item, category, change, revenue, previousRevenue, message }]
 * Empty for a month in progress, since a partial month can't be compared
 * against a full one.
 */
export function watchItems(report, previous) {
  if (report.isPartial || !report.items || !previous?.items) return []

  const prior = new Map(previous.items.map((i) => [key(i), i]))
  return report.items
    .map((i) => {
      const previousRevenue = prior.get(key(i))?.revenue
      return { ...i, previousRevenue, change: change(i.revenue, previousRevenue) }
    })
    .filter((i) => i.change !== null && i.change <= ITEM_DROP_THRESHOLD && i.previousRevenue >= MIN_PRIOR_REVENUE)
    .sort((a, b) => b.previousRevenue - b.revenue - (a.previousRevenue - a.revenue))
    .map((i) => ({
      id: key(i),
      item: i.name,
      category: i.category,
      change: i.change,
      revenue: i.revenue,
      previousRevenue: i.previousRevenue,
      message: `${i.name} sales in the ${i.category} category have gone down by ${fmt.pct(-i.change)} since last month`,
    }))
}

const key = (i) => `${i.category}::${i.name}`
