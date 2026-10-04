// Marketplaces shown in the dashboard.
//
// To add a new website, add an entry here (id must match the `id` the API
// returns). Order sets the display order and the chart color. A channel the API
// reports that is NOT listed here still appears — it gets the next free color
// and the name the API sends — so new marketplaces never silently disappear.
export const CHANNELS = [
  { id: 'shopgoodwill', name: 'ShopGoodwill' },
  { id: 'amazon', name: 'Amazon' },
  { id: 'ebay', name: 'eBay' },
]

// Marketplace colors: three shades of Goodwill blue, spaced far enough apart in
// lightness to stay distinguishable (validated, including for color-blind
// viewers). Slots 4+ are for future marketplaces. Assigned in fixed order,
// never cycled.
export const SERIES_COLORS = [
  '#0053a0', // Goodwill blue
  '#2f86d9', // mid blue
  '#6fb8f2', // light blue
  '#4a3aa7', // violet
  '#e87ba4', // magenta
  '#64748b', // slate
  '#e34948', // red
]

// Beyond eight marketplaces, the rest share a neutral gray rather than
// inventing a hue that would be indistinguishable from an existing one.
const OVERFLOW_COLOR = '#9ca3af'

/**
 * Merge the configured channel list with whatever channels appear in the data,
 * returning [{ id, name, color }] in display order.
 */
export function resolveChannels(dataChannels = []) {
  const known = new Map(CHANNELS.map((c) => [c.id, c]))
  const ordered = [...CHANNELS]
  const extras = dataChannels
    .filter((c) => !known.has(c.id))
    .sort((a, b) => a.id.localeCompare(b.id))
  for (const c of extras) {
    if (!ordered.some((o) => o.id === c.id)) ordered.push({ id: c.id, name: c.name ?? c.id })
  }
  return ordered.map((c, i) => ({ ...c, color: SERIES_COLORS[i] ?? OVERFLOW_COLOR }))
}

// Two-series colors for non-marketplace splits (e.g. new vs repeat buyers), so
// they never borrow a marketplace's color.
export const SEGMENT_COLORS = { primary: '#4a3aa7', secondary: '#e87ba4' }

// Single-series charts that aren't about a marketplace use Goodwill blue.
export const ACCENT = '#0053a0'
