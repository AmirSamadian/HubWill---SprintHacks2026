import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AXIS_LG, ChartCard, ChartTooltip, CURSOR, GRID, SURFACE } from '../../components/charts'
import { ACCENT, resolveChannels } from '../../config/channels'
import { formatLongDate, formatMonth, formatMonthShort, formatShortDate, parseISODate } from '../../lib/dates'
import { change, fmt } from '../../lib/format'
import { KpiTiles } from './shared'

const PRIOR_YEAR = '#a3acb9'

export default function FinancialSection({ report, previous, history }) {
  const channels = resolveChannels(report.channels)

  const daily = report.daily.map((d) => {
    const point = { date: d.date }
    for (const c of d.channels) point[c.id] = c.revenue
    return point
  })

  const yoy = history.map((h) => ({ ...h, growth: change(h.revenue, h.revenuePriorYear) }))

  return (
    <section>
      <div className="grid items-start gap-5 lg:grid-cols-[240px_1fr]">
        <KpiTiles report={report} previous={previous} cols="" ids={['grossMarginPct']} />
        <ChartCard
          title="Revenue vs. same month last year"
          subtitle={report.isPartial ? 'Each month compared over the same number of days as the month to date.' : 'Trailing 12 months.'}
          legend={[
            { name: 'This year', color: ACCENT },
            { name: 'Prior year', color: PRIOR_YEAR },
          ]}
          table={{
            columns: [
              { key: 'month', label: 'Month', format: (m) => formatMonth(m, 'short') },
              { key: 'revenue', label: 'Revenue', format: fmt.currency },
              { key: 'revenuePriorYear', label: 'Prior year', format: fmt.currency },
              { key: 'growth', label: 'YoY', format: fmt.signedPct },
            ],
            rows: yoy,
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={yoy} margin={{ top: 4, right: 4, left: 4, bottom: 0 }} barGap={2}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="month" {...AXIS_LG} tickFormatter={formatMonthShort} />
              <YAxis {...AXIS_LG} tickFormatter={fmt.currencyCompact} width={66} />
              <Tooltip
                cursor={CURSOR}
                content={
                  <ChartTooltip
                    labelFormatter={(m, payload) => `${formatMonth(m)} · ${fmt.signedPct(payload?.[0]?.payload.growth)} YoY`}
                    valueFormatter={fmt.currency}
                  />
                }
              />
              <Bar dataKey="revenuePriorYear" name="Prior year" fill={PRIOR_YEAR} radius={[4, 4, 0, 0]} maxBarSize={18} />
              <Bar dataKey="revenue" name="This year" fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <ChartCard
        className="mt-5"
        title="Daily revenue by marketplace"
        subtitle={`${formatMonth(report.month)}, stacked by marketplace`}
        legend={channels.map((c) => ({ name: c.name, color: c.color }))}
        table={{
          columns: [
            { key: 'date', label: 'Date', format: formatShortDate },
            ...channels.map((c) => ({ key: c.id, label: c.name, format: fmt.currency })),
          ],
          rows: daily,
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={daily} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="date" {...AXIS_LG} tickFormatter={(d) => parseISODate(d).getDate()} interval={0} />
            <YAxis {...AXIS_LG} tickFormatter={fmt.currencyCompact} width={66} />
            <Tooltip cursor={CURSOR} content={<ChartTooltip labelFormatter={formatLongDate} valueFormatter={fmt.currency} showTotal />} />
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
                maxBarSize={28}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </section>
  )
}
