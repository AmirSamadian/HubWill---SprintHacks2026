import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AXIS, ChartCard, ChartTooltip, CURSOR, GRID, SURFACE } from '../../components/charts'
import { Card, SectionHeader } from '../../components/ui'
import { resolveChannels, SEGMENT_COLORS } from '../../config/channels'
import { formatMonth, formatMonthShort } from '../../lib/dates'
import { fmt } from '../../lib/format'
import { hbarHeight, HBar, KpiTiles, SplitBar } from './shared'

const NEW = { name: 'First-time buyers', color: SEGMENT_COLORS.primary }
const REPEAT = { name: 'Repeat buyers', color: SEGMENT_COLORS.secondary }

export default function CustomerSection({ report, previous, history }) {
  const c = report.customers
  const retention = history.map((h) => ({ ...h, repeatRate: h.buyers ? h.repeatBuyers / h.buyers : null }))

  const channels = resolveChannels(report.channels)
  const byId = new Map(report.channels.map((ch) => [ch.id, ch]))
  const marketplace = channels.map((ch) => {
    const d = byId.get(ch.id)
    return {
      ...ch,
      customers: d?.customers ?? 0,
      conversion: d?.sessions ? d.orders / d.sessions : 0,
      sessions: d?.sessions ?? 0,
      orders: d?.orders ?? 0,
    }
  })

  return (
    <section>
      <SectionHeader
        eyebrow="KPI Framework · Customer & Marketplace"
        title="Customers & retention"
        subtitle="Who is buying, whether they come back, and how each marketplace converts."
      />
      <KpiTiles
        report={report}
        previous={previous}
        ids={['buyers', 'newBuyers', 'repeatBuyerRate', 'satisfaction', 'nps', 'conversionRate']}
      />

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <ChartCard
          className="lg:col-span-2"
          title="Retention — first-time vs. repeat buyers"
          subtitle="Trailing 12 months"
          legend={[NEW, REPEAT]}
          height={280}
          table={{
            columns: [
              { key: 'month', label: 'Month', format: (m) => formatMonth(m, 'short') },
              { key: 'newBuyers', label: 'First-time', format: fmt.number },
              { key: 'repeatBuyers', label: 'Repeat', format: fmt.number },
              { key: 'repeatRate', label: 'Repeat rate', format: fmt.pct },
            ],
            rows: retention,
          }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={retention} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="month" {...AXIS} tickFormatter={formatMonthShort} />
              <YAxis {...AXIS} tickFormatter={fmt.compact} width={44} />
              <Tooltip
                cursor={CURSOR}
                content={
                  <ChartTooltip
                    labelFormatter={(m, payload) => `${formatMonth(m)} · ${fmt.pct(payload?.[0]?.payload.repeatRate)} repeat`}
                    valueFormatter={fmt.number}
                    showTotal
                  />
                }
              />
              <Bar dataKey="newBuyers" name={NEW.name} stackId="b" fill={NEW.color} stroke={SURFACE} strokeWidth={1} maxBarSize={32} />
              <Bar
                dataKey="repeatBuyers"
                name={REPEAT.name}
                stackId="b"
                fill={REPEAT.color}
                stroke={SURFACE}
                strokeWidth={1}
                radius={[4, 4, 0, 0]}
                maxBarSize={32}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-sm font-semibold text-ink">Buyer split — {formatMonth(report.month)}</h3>
          <p className="mb-4 mt-0.5 text-xs text-ink-3">{fmt.number(c.buyers)} unique buyers</p>
          <SplitBar
            segments={[
              { ...NEW, value: c.newBuyers },
              { ...REPEAT, value: c.repeatBuyers, textColor: '#111111' },
            ]}
          />
        </Card>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <ChartCard
          title="Customers by marketplace"
          height={hbarHeight(marketplace.length) + 20}
          table={{
            columns: [
              { key: 'name', label: 'Marketplace' },
              { key: 'customers', label: 'Customers', format: fmt.number },
            ],
            rows: marketplace,
          }}
        >
          <HBar data={marketplace} dataKey="customers" label="Customers" format={fmt.number} colorKey="color" labelWidth={100} />
        </ChartCard>
        <ChartCard
          title="Conversion rate by marketplace"
          subtitle="Orders ÷ listing views"
          height={hbarHeight(marketplace.length) + 20}
          table={{
            columns: [
              { key: 'name', label: 'Marketplace' },
              { key: 'sessions', label: 'Views', format: fmt.number },
              { key: 'orders', label: 'Orders', format: fmt.number },
              { key: 'conversion', label: 'Conversion', format: fmt.pct },
            ],
            rows: marketplace,
          }}
        >
          <HBar data={marketplace} dataKey="conversion" label="Conversion" format={fmt.pct} colorKey="color" labelWidth={100} />
        </ChartCard>
      </div>
    </section>
  )
}
