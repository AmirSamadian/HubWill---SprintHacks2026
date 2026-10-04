// All dates are handled as local 'YYYY-MM-DD' strings and months as 'YYYY-MM'.

const pad = (n) => String(n).padStart(2, '0')

export function toISODate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function parseISODate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function addDays(iso, n) {
  const d = parseISODate(iso)
  d.setDate(d.getDate() + n)
  return toISODate(d)
}

export function yesterday() {
  return addDays(toISODate(new Date()), -1)
}

export function monthOf(iso) {
  return iso.slice(0, 7)
}

export function addMonths(ym, n) {
  const [y, m] = ym.split('-').map(Number)
  const d = new Date(y, m - 1 + n, 1)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`
}

export function daysInMonth(ym) {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m, 0).getDate()
}

export function datesOfMonth(ym) {
  return Array.from({ length: daysInMonth(ym) }, (_, i) => `${ym}-${pad(i + 1)}`)
}

export function formatLongDate(iso) {
  return parseISODate(iso).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

export function formatShortDate(iso) {
  return parseISODate(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export function formatMonth(ym, style = 'long') {
  return parseISODate(`${ym}-01`).toLocaleDateString('en-US', { month: style, year: 'numeric' })
}

export function formatMonthShort(ym) {
  return parseISODate(`${ym}-01`).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}
