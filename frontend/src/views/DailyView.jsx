import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fetchDailyReport, latestReportDate } from '../api'
import { AXIS, ChartCard, ChartTooltip, CURSOR, GRID, SURFACE } from '../components/charts'
import { Field, IconButton, inputClass, LoadState, Panel, SectionHeader, StatTile, Swatch, Tabs } from '../components/ui'
import { resolveChannels } from '../config/channels'
import { addDays, formatLongDate, formatShortDate, parseISODate } from '../lib/dates'
import { change, fmt } from '../lib/format'
import { useAsync } from '../lib/useAsync'

const METRICS = {
  revenue: { label: 'Revenue', format: fmt.currency, axis: fmt.currencyCompact },
  customers: { label: 'Customers', format: fmt.number, axis: fmt.compact },
}

/** One row per configured or reported marketplace, zero-filled if missing. */
function channelRows(channels, data) {
  const byId = new Map(data.map((c) => [c.id, c]))
  return channels.map((c) => ({ ...c, revenue: byId.get(c.id)?.revenue ?? 0, customers: byId.get(c.id)?.customers ?? 0 }))
}

const totals = (rows) => ({
  revenue: rows.reduce((s, r) => s + r.revenue, 0),
  customers: rows.reduce((s, r) => s + r.customers, 0),
})

export default function DailyView() {
  const latest = latestReportDate()
  const [date, setDate] = useState(latest)
  const { data, loading, error } = useAsync(() => fetchDailyReport(date), [date])

  return (
    <section>
      <SectionHeader
        eyebrow="Nightly Channel Breakdown"
        title="Daily Pulse"
        subtitle="Revenue and customer count by marketplace, followed by enterprise totals."
      >
        <div className="flex items-end gap-2">
          <IconButton label="Previous day" onClick={() => setDate(addDays(date, -1))}>
            ←
          </IconButton>
          <Field label="Report date">
            <input
              type="date"
              className={inputClass}
              value={date}
              max={latest}
              onChange={(e) => e.target.value && setDate(e.target.value > latest ? latest : e.target.value)}
            />
          </Field>
          <IconButton label="Next day" onClick={() => setDate(addDays(date, 1))} disabled={date >= latest}>
            →
          </IconButton>
        </div>
      </SectionHeader>

      <LoadState loading={loading} error={error}>
        {data && <DailyBody report={data} />}
      </LoadState>
    </section>
  )
}

function DailyBody({ report }) {
  const [trendMetric, setTrendMetric] = useState('revenue')
  const allChannels = [...report.channels, ...report.history.flatMap((h) => h.channels)]
  const channels = resolveChannels(allChannels)
  const rows = channelRows(channels, report.channels)
  const total = totals(rows)

  // Compare to the same weekday last week; weekday swings make day-over-day noisy.
  const lastWeek = report.history.find((h) => h.date === addDays(report.date, -7))
  const lastWeekTotal = lastWeek ? totals(channelRows(channels, lastWeek.channels)) : null
  const vsLastWeek = (key) => (lastWeekTotal ? { kind: 'relative', value: change(total[key], lastWeekTotal[key]) } : null)
  const top = [...rows].sort((a, b) => b.revenue - a.revenue)[0]
  const weekday = parseISODate(report.date).toLocaleDateString('en-US', { weekday: 'long' })

  const trend = report.history.map((h) => {
    const point = { date: h.date }
    for (const r of channelRows(channels, h.channels)) point[r.id] = r[trendMetric]
    return point
  })
  const metric = METRICS[trendMetric]

  return (
    <div className="space-y-5">
      <p className="text-sm text-ink-2">{formatLongDate(report.date)}</p>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatTile
          emphasis
          label="Total E-Commerce Revenue"
          value={fmt.currency(total.revenue)}
          delta={vsLastWeek('revenue')}
          better="up"
          deltaSuffix={`vs last ${weekday}`}
        />
        <StatTile
          label="Total Customers"
          value={fmt.number(total.customers)}
          delta={vsLastWeek('customers')}
          better="up"
          deltaSuffix={`vs last ${weekday}`}
        />
        <StatTile label="Revenue per Customer" value={fmt.currencyCents(total.customers ? total.revenue / total.customers : null)} />
        <StatTile
          label="Top Marketplace"
          value={top?.name ?? '—'}
          sub={top && total.revenue ? `${fmt.pct(top.revenue / total.revenue)} of today’s revenue` : undefined}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-5">
        <Panel eyebrow="Nightly report" className="xl:col-span-3">
          <NightlyTable rows={rows} total={total} />
        </Panel>

        <div className="grid gap-5 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-1">
          <ChannelBarChart title="Revenue by marketplace" rows={rows} metric="revenue" />
          <ChannelBarChart title="Customers by marketplace" rows={rows} metric="customers" />
        </div>
      </div>

      <ChartCard
        title={`${metric.label} by marketplace — last 14 days`}
        subtitle={`Stacked by marketplace. Highlighted bar is ${formatShortDate(report.date)}.`}
        legend={channels.map((c) => ({ name: c.name, color: c.color }))}
        height={300}
        table={{
          columns: [
            { key: 'date', label: 'Date', format: formatShortDate },
            ...channels.map((c) => ({ key: c.id, label: c.name, format: metric.format })),
          ],
          rows: trend,
        }}
        actions={
          <Tabs
            size="sm"
            value={trendMetric}
            onChange={setTrendMetric}
            tabs={[
              { id: 'revenue', label: 'Revenue' },
              { id: 'customers', label: 'Customers' },
            ]}
          />
        }
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={trend} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="date" {...AXIS} tickFormatter={formatShortDate} interval="preserveStartEnd" />
            <YAxis {...AXIS} tickFormatter={metric.axis} width={56} />
            <Tooltip
              cursor={CURSOR}
              content={<ChartTooltip labelFormatter={formatLongDate} valueFormatter={metric.format} showTotal />}
            />
            {channels.map((c, i) => (
              <Bar
                key={c.id}
                dataKey={c.id}
                name={c.name}
                stackId="day"
                fill={c.color}
                stroke={SURFACE}
                strokeWidth={1}
                radius={i === channels.length - 1 ? [4, 4, 0, 0] : 0}
                maxBarSize={36}
              >
                {trend.map((p) => (
                  <Cell key={p.date} fillOpacity={p.date === report.date ? 1 : 0.45} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  )
}

function NightlyTable({ rows, total }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] text-left">
        <thead>
          <tr className="border-b-2 border-brand text-xs uppercase tracking-wide text-brand">
            <th className="py-2 pr-4 font-bold">Revenue source</th>
            <th className="py-2 pr-4 text-right font-bold">Daily revenue</th>
            <th className="py-2 pr-4 text-right font-bold">Daily customers</th>
            <th className="w-[28%] py-2 font-bold">Share of revenue</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const share = total.revenue ? r.revenue / total.revenue : 0
            return (
              <tr key={r.id} className="border-b border-black/10">
                <td className="py-3.5 pr-4">
                  <span className="flex items-center gap-2.5 text-base font-extrabold uppercase tracking-tight text-ink">
                    <Swatch color={r.color} />
                    {r.name}
                  </span>
                </td>
                <td className="tabular py-3.5 pr-4 text-right text-lg text-ink">{fmt.currency(r.revenue)}</td>
                <td className="tabular py-3.5 pr-4 text-right text-lg text-ink">{fmt.number(r.customers)}</td>
                <td className="py-3.5">
                  <div className="flex items-center gap-2">
                    <div className="h-2 flex-1 rounded-full bg-black/5">
                      <div className="h-2 rounded-full" style={{ width: `${share * 100}%`, backgroundColor: r.color }} />
                    </div>
                    <span className="tabular w-12 text-right text-xs text-ink-2">{fmt.pct(share)}</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr className="text-brand">
            <td className="py-4 pr-4 text-base font-extrabold uppercase tracking-tight">Total E-Commerce</td>
            <td className="tabular py-4 pr-4 text-right text-xl font-extrabold">{fmt.currency(total.revenue)}</td>
            <td className="tabular py-4 pr-4 text-right text-xl font-extrabold">{fmt.number(total.customers)}</td>
            <td className="py-4 text-xs text-ink-3">{rows.length} marketplaces</td>
          </tr>
        </tfoot>
      </table>
      <p className="mt-3 text-xs text-ink-3">
        New marketplaces appear as their own row automatically once the data includes them.
      </p>
    </div>
  )
}

function ChannelBarChart({ title, rows, metric }) {
  const m = METRICS[metric]
  return (
    <ChartCard
      title={title}
      height={150}
      table={{
        columns: [
          { key: 'name', label: 'Marketplace' },
          { key: metric, label: m.label, format: m.format },
        ],
        rows,
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 64, left: 0, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="name" {...AXIS} tick={{ fill: '#374151', fontSize: 12 }} width={96} />
          <Tooltip cursor={CURSOR} content={<ChartTooltip valueFormatter={m.format} />} />
          <Bar dataKey={metric} name={m.label} radius={[0, 4, 4, 0]} maxBarSize={22}>
            {rows.map((r) => (
              <Cell key={r.id} fill={r.color} />
            ))}
            <LabelList dataKey={metric} position="right" formatter={m.format} fill="#111111" fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}
