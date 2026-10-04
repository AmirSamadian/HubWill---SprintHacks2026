import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AXIS, ChartTooltip, CURSOR } from '../../components/charts'
import { StatTile } from '../../components/ui'
import { ACCENT } from '../../config/channels'
import { fmt } from '../../lib/format'
import { KPIS, kpiDelta, kpiValue } from '../../lib/kpis'

/** A grid of KPI tiles with month-over-month deltas. */
export function KpiTiles({ ids, report, previous, cols = 'sm:grid-cols-2 lg:grid-cols-3', emphasis = [] }) {
  return (
    <div className={`grid grid-cols-1 gap-4 ${cols}`}>
      {ids.map((id) => {
        const kpi = KPIS[id]
        return (
          <StatTile
            key={id}
            label={kpi.label}
            value={fmt[kpi.format](kpiValue(id, report))}
            delta={kpiDelta(id, report, previous)}
            better={kpi.better}
            emphasis={emphasis.includes(id)}
          />
        )
      })}
    </div>
  )
}

/**
 * Horizontal bar chart for one measure across labeled rows, with the value
 * printed at the end of each bar. Colors come from `colorKey` on each row, or
 * the brand accent when the rows aren't marketplaces. `labelKey` overrides the
 * end-of-bar text with a precomputed field.
 */
export function HBar({ data, dataKey, nameKey = 'name', format, label, colorKey, labelKey, labelWidth = 150 }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 72, left: 0, bottom: 0 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey={nameKey}
          {...AXIS}
          tick={{ fill: '#374151', fontSize: 14 }}
          width={labelWidth}
          interval={0}
        />
        <Tooltip cursor={CURSOR} content={<ChartTooltip valueFormatter={format} />} />
        <Bar dataKey={dataKey} name={label} radius={[0, 4, 4, 0]} maxBarSize={20} fill={ACCENT}>
          {colorKey && data.map((r) => <Cell key={r[nameKey]} fill={r[colorKey]} />)}
          <LabelList
            dataKey={labelKey ?? dataKey}
            position="right"
            formatter={labelKey ? undefined : format}
            fill="#111111"
            fontSize={13}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/** Height for an HBar so each row gets enough room. */
export const hbarHeight = (rows) => Math.max(130, rows * 34)

/**
 * A single 100% bar split into labeled segments, with a legend that carries
 * each segment's value and share so color is never the only cue.
 */
export function SplitBar({ segments, format = fmt.number }) {
  const sum = segments.reduce((s, x) => s + x.value, 0) || 1
  return (
    <div>
      <div className="flex h-8 w-full gap-0.5 overflow-hidden rounded">
        {segments.map((s) => (
          <div
            key={s.name}
            title={`${s.name}: ${format(s.value)} (${fmt.pct(s.value / sum)})`}
            className="flex items-center justify-center text-xs font-semibold first:rounded-l last:rounded-r"
            style={{ width: `${(s.value / sum) * 100}%`, backgroundColor: s.color, color: s.textColor ?? '#ffffff' }}
          >
            {s.value / sum > 0.12 && fmt.pct(s.value / sum)}
          </div>
        ))}
      </div>
      <ul className="mt-3 space-y-1.5 text-sm">
        {segments.map((s) => (
          <li key={s.name} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-ink-2">
              <span className="inline-block size-2.5 rounded-sm" style={{ backgroundColor: s.color }} />
              {s.name}
            </span>
            <span className="tabular text-ink">
              {format(s.value)} <span className="text-ink-3">· {fmt.pct(s.value / sum)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
