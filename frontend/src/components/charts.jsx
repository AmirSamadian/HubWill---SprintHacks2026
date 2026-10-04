import { useState } from 'react'
import { Card, Swatch } from './ui'

// Shared chart chrome: recessive grid and axes, ink-colored text.
export const GRID = { stroke: '#e5e7eb', strokeDasharray: '0', vertical: false }
export const AXIS = {
  stroke: '#d1d5db',
  tick: { fill: '#6b7280', fontSize: 11 },
  tickLine: false,
  axisLine: false,
}
export const SURFACE = '#ffffff'
export const CURSOR = { fill: 'rgba(0,83,160,0.06)' }

/** Tooltip body: a title row, then one row per series with a swatch. */
export function ChartTooltip({ active, payload, label, labelFormatter = (l) => l, valueFormatter = (v) => v, showTotal = false }) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((p) => p.value !== null && p.value !== undefined)
  const sum = rows.reduce((s, p) => s + Number(p.value), 0)
  return (
    <div className="min-w-44 rounded-md bg-surface px-3 py-2 text-xs shadow-lg ring-1 ring-black/10">
      <div className="mb-1.5 font-semibold text-ink">{labelFormatter(label, payload)}</div>
      {rows.map((p) => (
        <div key={p.dataKey ?? p.name} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-2 text-ink-2">
            <Swatch color={p.payload?.fill ?? p.color ?? p.fill} />
            {p.name}
          </span>
          <span className="tabular font-semibold text-ink">{valueFormatter(p.value, p)}</span>
        </div>
      ))}
      {showTotal && rows.length > 1 && (
        <div className="mt-1 flex justify-between gap-4 border-t border-black/10 pt-1">
          <span className="text-ink-2">Total</span>
          <span className="tabular font-semibold text-brand">{valueFormatter(sum)}</span>
        </div>
      )}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {items.map((i) => (
        <li key={i.name} className="flex items-center gap-1.5">
          <Swatch color={i.color} />
          {i.name}
        </li>
      ))}
    </ul>
  )
}

/**
 * Chart frame with title, optional legend, and a "Table" toggle so every chart's
 * numbers are readable without relying on color or hover.
 * `table` = { columns: [{ key, label, format? }], rows: [...] }
 */
export function ChartCard({ title, subtitle, legend, table, actions, height = 260, className = '', children }) {
  const [showTable, setShowTable] = useState(false)
  return (
    <Card className={`flex flex-col p-5 ${className}`}>
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-3">{subtitle}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
        {actions}
        {table && (
          <button
            type="button"
            onClick={() => setShowTable((s) => !s)}
            className="shrink-0 rounded px-2 py-1 text-[11px] uppercase tracking-wider text-ink-3 ring-1 ring-black/10 hover:text-ink"
          >
            {showTable ? 'Chart' : 'Table'}
          </button>
        )}
        </div>
      </div>
      {legend && !showTable && (
        <div className="mb-3">
          <Legend items={legend} />
        </div>
      )}
      {showTable ? (
        <DataTable {...table} maxHeight={height + 40} />
      ) : (
        <div style={{ height }} className="w-full">
          {children}
        </div>
      )}
    </Card>
  )
}

export function DataTable({ columns, rows, maxHeight }) {
  return (
    <div className="overflow-auto" style={{ maxHeight }}>
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-surface">
          <tr>
            {columns.map((c, i) => (
              <th key={c.key} className={`py-2 pr-3 font-medium uppercase tracking-wider text-brand ${i ? 'text-right' : ''}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, ri) => (
            <tr key={ri} className="border-t border-black/5">
              {columns.map((c, i) => (
                <td key={c.key} className={`tabular py-1.5 pr-3 ${i ? 'text-right text-ink' : 'text-ink-2'}`}>
                  {c.format ? c.format(r[c.key], r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
