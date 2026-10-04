const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const usdCents = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 })
const usdCompact = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 })
const int = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })

const isMissing = (v) => v === null || v === undefined || Number.isNaN(v)

export const fmt = {
  currency: (v) => (isMissing(v) ? '—' : usd.format(v)),
  currencyCents: (v) => (isMissing(v) ? '—' : usdCents.format(v)),
  currencyCompact: (v) => (isMissing(v) ? '—' : usdCompact.format(v)),
  number: (v) => (isMissing(v) ? '—' : int.format(v)),
  compact: (v) => (isMissing(v) ? '—' : compact.format(v)),
  decimal: (v) => (isMissing(v) ? '—' : v.toFixed(1)),
  pct: (v) => (isMissing(v) ? '—' : `${(v * 100).toFixed(1)}%`),
  signedPct: (v) => (isMissing(v) ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`),
  minutes: (v) => (isMissing(v) ? '—' : `${v.toFixed(1)} min`),
  days: (v) => (isMissing(v) ? '—' : `${v.toFixed(1)} days`),
  rating: (v) => (isMissing(v) ? '—' : `${v.toFixed(2)} / 5`),
  score: (v) => (isMissing(v) ? 'N/A' : `${v >= 0 ? '+' : ''}${Math.round(v)}`),
}

/** Relative change, or null when there is no meaningful base. */
export function change(current, previous) {
  if (isMissing(current) || isMissing(previous) || previous === 0) return null
  return current / previous - 1
}

/** Text, arrow and good/bad for a KPI delta from kpiDelta(); null if none. */
export function describeDelta(delta, better = 'up') {
  if (!delta || delta.value === null || delta.value === undefined) return null
  const { kind, value } = delta
  const flat = Math.abs(value) < (kind === 'score' ? 0.5 : 0.0005)
  const good = flat ? null : (value > 0) === (better === 'up')
  const text =
    kind === 'points'
      ? `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)} pts`
      : kind === 'score'
        ? `${value >= 0 ? '+' : ''}${Math.round(value)}`
        : fmt.signedPct(value)
  const arrow = flat ? '→' : value > 0 ? '▲' : '▼'
  return { flat, good, text, arrow }
}
