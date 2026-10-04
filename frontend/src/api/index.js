// Single entry point for dashboard data.
//
// Right now every report is built from the TEMPORARY values in
// ./placeholderData.js — the same numbers show for any date or month. When the
// database is ready, replace the body of fetchDailyReport / fetchMonthlyReport
// with real queries (or set VITE_API_URL to call a backend). As long as the
// returned objects keep the same shape, no component needs to change.

import { addMonths, datesOfMonth, daysInMonth, monthOf, yesterday } from '../lib/dates'
import {
  TEMP_CATEGORIES,
  TEMP_CUSTOMERS,
  TEMP_DAILY_CHANNELS,
  TEMP_FINANCIAL,
  TEMP_ITEMS,
  TEMP_MONTH_CHANNELS,
  TEMP_MONTH_DAILY_REVENUE,
  TEMP_MONTHLY_HISTORY,
  TEMP_PREVIOUS_MONTH,
  TEMP_SALES,
} from './placeholderData'

const API_URL = import.meta.env.VITE_API_URL

async function getJSON(path) {
  const res = await fetch(`${API_URL}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`)
  return res.json()
}

// Lets loading states render with placeholder data the way they will for real.
const simulateLatency = (value) => new Promise((resolve) => setTimeout(() => resolve(value), 150))

/** The most recent day with a complete nightly report. */
export function latestReportDate() {
  return yesterday()
}

/** Months available in the month picker, newest first. */
export function availableMonths(count = 24) {
  const latest = monthOf(latestReportDate())
  return Array.from({ length: count }, (_, i) => addMonths(latest, -i))
}

/**
 * Nightly channel breakdown for `date`:
 * { date, channels: [{ id, name, revenue, customers }] }
 */
export async function fetchDailyReport(date) {
  if (API_URL) return getJSON(`/reports/daily?date=${date}`)

  // TODO(database): replace with a query for `date`.
  return simulateLatency({ date, channels: TEMP_DAILY_CHANNELS })
}

/**
 * Everything the monthly tab needs: the selected month, the prior month (for
 * month-over-month deltas) and a 12-month history for trend charts.
 */
export async function fetchMonthlyReport(month) {
  const previousMonth = addMonths(month, -1)
  if (API_URL) {
    const [report, previous, history] = await Promise.all([
      getJSON(`/reports/monthly?month=${month}`),
      getJSON(`/reports/monthly?month=${previousMonth}`),
      getJSON(`/reports/monthly/history?month=${month}&months=12`),
    ])
    return { report, previous, history }
  }

  // TODO(database): replace the placeholders below with queries for `month`.
  const dates = datesOfMonth(month).filter((d) => d <= latestReportDate())
  const report = {
    month,
    isPartial: dates.length < daysInMonth(month),
    through: dates.at(-1),
    daysReported: dates.length,
    channels: TEMP_MONTH_CHANNELS,
    daily: dates.map((date, i) => ({
      date,
      channels: Object.entries(TEMP_MONTH_DAILY_REVENUE[i]).map(([id, revenue]) => ({ id, revenue })),
    })),
    financial: TEMP_FINANCIAL,
    sales: TEMP_SALES,
    categories: TEMP_CATEGORIES,
    items: TEMP_ITEMS,
    customers: TEMP_CUSTOMERS,
  }

  // TODO(database): same query for `previousMonth`.
  const previous = {
    month: previousMonth,
    isPartial: false,
    daysReported: daysInMonth(previousMonth),
    channels: TEMP_PREVIOUS_MONTH.channels,
    financial: TEMP_PREVIOUS_MONTH.financial,
    sales: TEMP_PREVIOUS_MONTH.sales,
    categories: [],
    items: TEMP_PREVIOUS_MONTH.items,
    customers: TEMP_PREVIOUS_MONTH.customers,
  }

  // TODO(database): monthly totals for the 12 months ending at `month`.
  const history = TEMP_MONTHLY_HISTORY.map((row, i) => ({
    month: addMonths(month, i - TEMP_MONTHLY_HISTORY.length + 1),
    ...row,
  }))

  return simulateLatency({ report, previous, history })
}
