import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AXIS, ChartCard, ChartTooltip, CURSOR, GRID } from '../../components/charts'
import { SectionHeader } from '../../components/ui'
import { ACCENT } from '../../config/channels'
import { formatLongDate, formatShortDate, parseISODate } from '../../lib/dates'
import { fmt } from '../../lib/format'
import { hbarHeight, HBar, KpiTiles } from './shared'

export default function ProductionSection({ report, previous }) {
  const p = report.production
  const funnel = [
    { name: 'Identified for e-commerce', value: p.itemsIdentified },
    { name: 'Sent to e-commerce', value: p.itemsSentToEcommerce },
    { name: 'Listed', value: p.listingsCreated },
    { name: 'Sold', value: report.sales.unitsSold },
  ].map((s, i, all) => {
    const pctOfTop = s.value / all[0].value
    return { ...s, pctOfTop, label: `${fmt.number(s.value)} · ${fmt.pct(pctOfTop)}` }
  })
  const employees = [...p.employees].sort((a, b) => b.listingsCreated - a.listingsCreated)

  return (
    <section>
      <SectionHeader
        eyebrow="KPI Framework · Productivity"
        title="Listing & production"
        subtitle="Throughput from donation to live listing, and where the backlog sits."
      />
      <KpiTiles
        report={report}
        previous={previous}
        cols="sm:grid-cols-2 lg:grid-cols-4"
        ids={[
          'itemsIdentified',
          'itemsSent',
          'listingsCreated',
          'listingsPerDay',
          'listingsPerEmployee',
          'avgTimeToList',
          'daysDonationToListing',
          'unlistedBacklog',
        ]}
      />

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <ChartCard
          title="Item pipeline"
          subtitle="Items at each stage this month, with share of items identified"
          height={hbarHeight(funnel.length) + 40}
          table={{
            columns: [
              { key: 'name', label: 'Stage' },
              { key: 'value', label: 'Items', format: fmt.number },
              { key: 'pctOfTop', label: '% of identified', format: fmt.pct },
            ],
            rows: funnel,
          }}
        >
          <HBar
            data={funnel}
            dataKey="value"
            label="Items"
            format={fmt.number}
            labelKey="label"
            labelWidth={170}
          />
        </ChartCard>

        <ChartCard
          title="Listings per employee"
          subtitle="Listings created this month"
          height={hbarHeight(employees.length) + 40}
          table={{
            columns: [
              { key: 'name', label: 'Employee' },
              { key: 'listingsCreated', label: 'Listings', format: fmt.number },
            ],
            rows: employees,
          }}
        >
          <HBar data={employees} dataKey="listingsCreated" label="Listings" format={fmt.number} labelWidth={90} />
        </ChartCard>
      </div>

      <ChartCard
        className="mt-5"
        title="Listings created per day"
        subtitle="Weekend days run lighter by design"
        height={220}
        table={{
          columns: [
            { key: 'date', label: 'Date', format: formatShortDate },
            { key: 'listingsCreated', label: 'Listings', format: fmt.number },
          ],
          rows: p.dailyListings,
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={p.dailyListings} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <CartesianGrid {...GRID} />
            <XAxis dataKey="date" {...AXIS} tickFormatter={(d) => parseISODate(d).getDate()} interval={0} />
            <YAxis {...AXIS} width={40} />
            <Tooltip cursor={CURSOR} content={<ChartTooltip labelFormatter={formatLongDate} valueFormatter={fmt.number} />} />
            <Bar dataKey="listingsCreated" name="Listings" fill={ACCENT} radius={[4, 4, 0, 0]} maxBarSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </section>
  )
}
