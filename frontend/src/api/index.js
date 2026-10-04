// Single entry point for dashboard data. Every report comes from the backend
// (backend/app/dashboard.py), which reads the PostgreSQL database and computes
// all business metrics. Set VITE_API_URL in frontend/.env.local to use a
// backend somewhere other than http://127.0.0.1:8000/api.

import { addMonths, monthOf, yesterday } from '../lib/dates'

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'

async function getJSON(path) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`)
  } catch {
    throw new Error(`Cannot reach the backend at ${API_URL}. Start it with: cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    // FastAPI puts the reason in "detail" (e.g. database unavailable, bad month).
    const detail = typeof body?.detail === 'string' ? body.detail : `${res.status} ${res.statusText}`
    throw new Error(detail)
  }
  return body
}

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
 * { date, channels: [{ id, name, revenue, orders, customers }], totals: { revenue, orders, customers }, ... }
 * Values the database cannot supply are null (for example customers for
 * marketplaces that do not share buyer identity).
 */
export async function fetchDailyReport(date) {
  return getJSON(`/reports/daily?date=${date}`)
}

/**
 * Everything the monthly tab needs: the selected month (including its KPIs,
 * month-over-month deltas and watch list, computed by the backend) and a
 * 12-month history for trend charts.
 */
export async function fetchMonthlyReport(month) {
  const [report, history] = await Promise.all([
    getJSON(`/reports/monthly?month=${month}`),
    getJSON(`/reports/monthly/history?month=${month}&months=12`),
  ])
  return { report, previous: { month: report.previousMonth }, history }
}
