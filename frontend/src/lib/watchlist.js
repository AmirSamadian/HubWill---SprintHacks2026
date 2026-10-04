// Item-level early warnings for a month: subcategories (e.g. Furniture in Home)
// whose sales fell versus the prior month. The rule is applied by the backend
// (backend/app/dashboard.py, watch_items) so the dashboard and any future
// written report share it; this file only reads the result.

/**
 * The flagged items, biggest dollar loss first:
 * [{ id, item, category, change, revenue, previousRevenue, message }]
 * Empty for a month in progress or when the data cannot support it.
 */
export function watchItems(report) {
  return report?.watchItems ?? []
}
