import { ChartCard } from '../../components/charts'
import { Card, SectionHeader } from '../../components/ui'
import { ACCENT } from '../../config/channels'
import { fmt } from '../../lib/format'
import { hbarHeight, HBar, KpiTiles, SplitBar } from './shared'

const ACTIVE = '#a3acb9'
const STALE = '#6fb8f2' // aged listings that need attention (also flagged with ⚠)

export default function SalesSection({ report, previous }) {
  const s = report.sales
  const staleDays = 60
  const employees = [...report.production.employees].sort((a, b) => b.revenue - a.revenue)

  return (
    <section>
      <SectionHeader
        eyebrow="KPI Framework · Sales Effectiveness"
        title="Sales effectiveness"
        subtitle="How well listed inventory converts into sales, and at what price."
      />
      <KpiTiles
        report={report}
        previous={previous}
        ids={['avgSellingPrice', 'medianSalePrice', 'sellThroughRate', 'daysToSell', 'unsoldInventoryPct', 'relistedInventoryPct']}
      />

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="text-sm font-semibold text-ink">Inventory status</h3>
          <p className="mb-4 mt-0.5 text-xs text-ink-3">
            Items available to sell this month. Stale = listed more than {staleDays} days without selling.
          </p>
          <SplitBar
            segments={[
              { name: 'Sold', value: s.unitsSold, color: ACCENT },
              { name: `Active (under ${staleDays} days)`, value: s.activeListings - s.staleListings, color: ACTIVE, textColor: '#111111' },
              { name: `⚠ Stale (${staleDays}+ days)`, value: s.staleListings, color: STALE, textColor: '#111111' },
            ]}
          />
          <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-black/10 pt-4 text-sm">
            <div>
              <dt className="text-ink-3">Units sold</dt>
              <dd className="tabular font-semibold text-ink">{fmt.number(s.unitsSold)}</dd>
            </div>
            <div>
              <dt className="text-ink-3">Relisted this month</dt>
              <dd className="tabular font-semibold text-ink">{fmt.number(s.relistedListings)}</dd>
            </div>
          </dl>
        </Card>

        <ChartCard
          title="Sales per employee"
          subtitle="Revenue from items each lister created"
          height={hbarHeight(employees.length) + 40}
          table={{
            columns: [
              { key: 'name', label: 'Employee' },
              { key: 'revenue', label: 'Revenue', format: fmt.currency },
            ],
            rows: employees,
          }}
        >
          <HBar data={employees} dataKey="revenue" label="Revenue" format={fmt.currencyCompact} labelWidth={90} />
        </ChartCard>
      </div>
    </section>
  )
}
