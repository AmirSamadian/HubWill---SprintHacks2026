import { useState } from 'react'
import { ChartCard } from '../../components/charts'
import { Panel, SectionHeader } from '../../components/ui'
import { fmt } from '../../lib/format'
import { categoryRows, topCategories } from '../../lib/kpis'
import { hbarHeight, HBar } from './shared'

const COLUMNS = [
  { key: 'name', label: 'Category' },
  { key: 'revenue', label: 'Sales', format: fmt.currency },
  { key: 'margin', label: 'Margin', format: fmt.currency },
  { key: 'marginPct', label: 'Margin %', format: fmt.pct },
  { key: 'unitsSold', label: 'Units sold', format: fmt.number },
  { key: 'sellThrough', label: 'Sell-through', format: fmt.pct },
  { key: 'asp', label: 'ASP', format: fmt.currencyCents },
]

export default function CategorySection({ report }) {
  const byRevenue = topCategories(report, 'revenue')
  const byMargin = topCategories(report, 'margin')

  return (
    <section id="categories" className="scroll-mt-6">
      <SectionHeader
        eyebrow="KPI Framework · Category Performance"
        title="Category performance"
        subtitle="Category economics explain what is driving the headline results."
      />
      <div className="grid gap-5 lg:grid-cols-2">
        <ChartCard
          title="Top 10 categories by revenue"
          height={hbarHeight(10)}
          table={{ columns: COLUMNS.slice(0, 2), rows: byRevenue }}
        >
          <HBar data={byRevenue} dataKey="revenue" label="Sales" format={fmt.currencyCompact} labelWidth={160} />
        </ChartCard>
        <ChartCard
          title="Top 10 categories by margin"
          subtitle="Gross margin dollars"
          height={hbarHeight(10)}
          table={{ columns: [COLUMNS[0], COLUMNS[2], COLUMNS[3]], rows: byMargin }}
        >
          <HBar data={byMargin} dataKey="margin" label="Margin" format={fmt.currencyCompact} labelWidth={160} />
        </ChartCard>
      </div>

      <Panel eyebrow="All categories" className="mt-5">
        <CategoryTable rows={categoryRows(report)} />
      </Panel>
    </section>
  )
}

function CategoryTable({ rows }) {
  const [sort, setSort] = useState({ key: 'revenue', dir: -1 })
  const sorted = [...rows].sort((a, b) => {
    const av = a[sort.key]
    const bv = b[sort.key]
    return (typeof av === 'string' ? av.localeCompare(bv) : av - bv) * sort.dir
  })
  const toggle = (key) => setSort((s) => (s.key === key ? { key, dir: -s.dir } : { key, dir: key === 'name' ? 1 : -1 }))

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead>
          <tr className="border-b-2 border-brand">
            {COLUMNS.map((c, i) => (
              <th key={c.key} className={`py-2 pr-4 ${i ? 'text-right' : ''}`} aria-sort={sort.key === c.key ? (sort.dir > 0 ? 'ascending' : 'descending') : undefined}>
                <button
                  type="button"
                  onClick={() => toggle(c.key)}
                  className="text-xs font-bold uppercase tracking-wider text-brand hover:text-brand-dark"
                >
                  {c.label}
                  <span className="ml-1 inline-block w-2 text-ink-3">{sort.key === c.key ? (sort.dir > 0 ? '↑' : '↓') : ''}</span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.name} className="border-b border-black/5 hover:bg-black/[0.03]">
              {COLUMNS.map((c, i) => (
                <td key={c.key} className={`tabular py-2 pr-4 ${i ? 'text-right text-ink' : 'font-medium text-ink'}`}>
                  {c.format ? c.format(r[c.key]) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
