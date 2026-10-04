import { Delta, Panel } from '../../components/ui'
import { fmt } from '../../lib/format'
import { KPIS, kpiDelta, kpiValue, SCORECARD, topCategories } from '../../lib/kpis'

/** The one-page COO operating view: 15 KPIs in five rows of three. */
export default function Scorecard({ report, previous }) {
  return (
    <Panel eyebrow="COO Scorecard · 15 KPIs">
      <div className="divide-y divide-black/10">
        {SCORECARD.map((row) => (
          <div key={row.group} className="grid gap-4 py-4 first:pt-0 last:pb-0 md:grid-cols-[180px_1fr_1fr_1fr]">
            <div className="text-sm font-bold uppercase tracking-wider text-brand">{row.group}</div>
            {row.kpis.map((id) => (
              <ScoreCell key={id} id={id} report={report} previous={previous} />
            ))}
          </div>
        ))}
      </div>
    </Panel>
  )
}

function ScoreCell({ id, report, previous }) {
  if (id === 'topCategoryByRevenue' || id === 'topCategoryByMargin') {
    const key = id === 'topCategoryByRevenue' ? 'revenue' : 'margin'
    const top = topCategories(report, key, 3)
    return (
      <div>
        <div className="text-sm text-ink-2">Top Categories by {key === 'revenue' ? 'Revenue' : 'Margin'}</div>
        <ol className="mt-1 space-y-0.5 text-sm">
          {top.map((c, i) => (
            <li key={c.name} className="flex justify-between gap-3">
              <span className={i === 0 ? 'font-bold text-ink' : 'text-ink-2'}>
                {i + 1}. {c.name}
              </span>
              <span className="tabular text-ink-2">{fmt.currencyCompact(c[key])}</span>
            </li>
          ))}
        </ol>
        <a href="#categories" className="mt-1 inline-block text-xs text-brand hover:underline">
          Full top 10 ↓
        </a>
      </div>
    )
  }

  const kpi = KPIS[id]
  return (
    <div>
      <div className="text-sm text-ink-2">{kpi.label}</div>
      <div className="mt-0.5 text-2xl font-bold text-ink">{fmt[kpi.format](kpiValue(id, report))}</div>
      <Delta delta={kpiDelta(id, report, previous)} better={kpi.better} suffix="MoM" />
    </div>
  )
}
