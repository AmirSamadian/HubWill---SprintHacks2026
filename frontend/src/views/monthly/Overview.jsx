import { useState } from 'react'
import { Card, DeltaPill } from '../../components/ui'
import { resolveChannels, SEGMENT_COLORS } from '../../config/channels'
import { addMonths, formatMonth } from '../../lib/dates'
import { change, fmt } from '../../lib/format'
import { KPI_NOTES, KPIS, kpiDelta, kpiValue, SCORECARD, topCategories } from '../../lib/kpis'
import { watchItems } from '../../lib/watchlist'
import { SplitBar } from './shared'

/** The COO operating view, most important first. */
export default function Overview({ report, previous }) {
  return (
    <div className="space-y-4">
      <HeadlineRow report={report} previous={previous} />
      <WatchList report={report} previous={previous} />
      <CategoryCustomerCard report={report} previous={previous} />
    </div>
  )
}

// ---------- headline: revenue (with marketplace split), growth, margin, price ----------

function HeadlineRow({ report, previous }) {
  const vsPrev = `vs. ${formatMonth(previous.month, 'short')}`
  return (
    <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-[1.7fr_1fr_1fr_1fr]">
      <RevenueTile report={report} previous={previous} vsPrev={vsPrev} />
      <KpiTile
        id="revenueGrowthYoY"
        report={report}
        previous={previous}
        context={`${formatMonth(addMonths(report.month, -12), 'short')}: ${fmt.currencyCompact(report.financial.revenuePriorYear)}`}
      />
      <KpiTile id="netMarginPct" report={report} previous={previous} context={vsPrev} />
      <KpiTile
        id="avgSellingPrice"
        report={report}
        previous={previous}
        context={`${fmt.number(report.sales.unitsSold)} units · median ${fmt.currencyCents(report.sales.medianSalePrice)}`}
      />
    </div>
  )
}

// Marketplace segments inside the blue tile use white at stepped opacities;
// each is labeled by name, so identity never rests on the shade alone.
const SHADES = [1, 0.62, 0.34, 0.2, 0.12]

function RevenueTile({ report, previous, vsPrev }) {
  const total = report.channels.reduce((s, c) => s + c.revenue, 0) || 1
  const prevById = new Map(previous.channels.map((c) => [c.id, c]))
  const rows = resolveChannels(report.channels).map((ch, i) => {
    const revenue = report.channels.find((c) => c.id === ch.id)?.revenue ?? 0
    const delta = report.isPartial ? null : change(revenue, prevById.get(ch.id)?.revenue)
    return { ...ch, revenue, share: revenue / total, delta, shade: SHADES[i] ?? 0.1 }
  })

  return (
    <div className="rounded-lg bg-brand p-5 text-white shadow-sm md:col-span-3 xl:col-span-1">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="text-sm font-medium text-white/80">{KPIS.revenue.label}</div>
        <div className="flex items-center gap-2 text-xs text-white/75">
          <DeltaPill delta={kpiDelta('revenue', report, previous)} better="up" inverted />
          <span>{report.isPartial ? 'Month to date' : vsPrev}</span>
        </div>
      </div>
      <div className="tabular mt-1 text-4xl font-bold tracking-tight">{fmt.currency(kpiValue('revenue', report))}</div>

      <div className="mt-4 flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {rows.map((r) => (
          <div key={r.id} style={{ width: `${r.share * 100}%`, backgroundColor: `rgba(255,255,255,${r.shade})` }} />
        ))}
      </div>
      <ul
        className="mt-3 grid gap-2 text-xs"
        style={{ gridTemplateColumns: `repeat(${Math.min(rows.length, 4)}, minmax(0, 1fr))` }}
      >
        {rows.map((r) => (
          <li key={r.id}>
            <div className="flex items-center gap-1.5 text-white/75">
              <span className="size-2 rounded-full" style={{ backgroundColor: `rgba(255,255,255,${r.shade})` }} />
              {r.name}
            </div>
            <div className="tabular mt-0.5 text-sm font-semibold">{fmt.currencyCompact(r.revenue)}</div>
            <div className="tabular text-white/70">
              {fmt.pct(r.share)}
              {r.delta !== null && ` · ${fmt.signedPct(r.delta)}`}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function KpiTile({ id, report, previous, context }) {
  const kpi = KPIS[id]
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-medium text-ink-2">{kpi.label}</span>
        <DeltaPill delta={kpiDelta(id, report, previous)} better={kpi.better} />
      </div>
      <div className="tabular mt-1 text-3xl font-bold tracking-tight text-ink">{fmt[kpi.format](kpiValue(id, report))}</div>
      <div className="mt-1 text-xs text-ink-3">{context}</div>
      <p className="mt-auto pt-3 text-xs text-ink-3">{KPI_NOTES[id].why}</p>
    </Card>
  )
}

// ---------- early warnings ----------

function WatchList({ report, previous }) {
  const items = watchItems(report, previous)
  if (!items.length) return null
  const shown = items.slice(0, 4)

  return (
    <div className="flex gap-3 rounded-lg bg-critical/5 px-4 py-3 ring-1 ring-critical/15" role="status">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-critical text-xs font-bold text-white" aria-hidden="true">
        !
      </span>
      <div className="text-sm">
        <span className="font-semibold text-ink">Watch list</span>
        <ul className="mt-1 space-y-0.5 text-ink-2">
          {shown.map((item) => (
            <li key={item.id}>
              <span className="font-medium text-ink">{item.label}</span>{' '}
              <span className="tabular text-critical">{item.change}</span>
              {item.note && <span> · {item.note}</span>}
            </li>
          ))}
        </ul>
        {items.length > shown.length && (
          <div className="mt-1 text-xs text-ink-3">+{items.length - shown.length} more moved the wrong way</div>
        )}
      </div>
    </div>
  )
}

// ---------- category + customer ----------

function CategoryCustomerCard({ report, previous }) {
  const g = SCORECARD.find((s) => s.id === 'categoryCustomer')
  const c = report.customers
  const kpi = KPIS.repeatBuyerRate
  return (
    <Card>
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-black/5 px-5 pb-3 pt-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-brand">{g.eyebrow}</div>
          <h3 className="mt-0.5 text-base font-bold tracking-tight text-ink">{g.title}</h3>
        </div>
        <p className="text-sm text-ink-3">{g.blurb}</p>
      </div>
      <div className="grid divide-y divide-black/5 lg:grid-cols-[1fr_1fr_0.8fr] lg:divide-x lg:divide-y-0">
        <TopList title="Top categories by revenue" rows={topCategories(report, 'revenue')} valueKey="revenue" />
        <TopList title="Top categories by margin" rows={topCategories(report, 'margin')} valueKey="margin" />
        <div className="p-5">
          <div className="flex items-start justify-between gap-2">
            <span className="text-sm font-medium text-ink-2">{kpi.label}</span>
            <DeltaPill delta={kpiDelta('repeatBuyerRate', report, previous)} better={kpi.better} />
          </div>
          <div className="tabular mt-1 text-3xl font-bold tracking-tight text-ink">{fmt.pct(kpiValue('repeatBuyerRate', report))}</div>
          <p className="mt-1 text-xs text-ink-3">{KPI_NOTES.repeatBuyerRate.why}</p>
          <div className="mt-4">
            <SplitBar
              segments={[
                { name: 'Repeat buyers', value: c.repeatBuyers, color: SEGMENT_COLORS.primary },
                { name: 'First-time buyers', value: c.newBuyers, color: SEGMENT_COLORS.secondary, textColor: '#111111' },
              ]}
            />
          </div>
        </div>
      </div>
    </Card>
  )
}

/** Ranked list showing the top 5, expandable to the full top 10. */
function TopList({ title, rows, valueKey }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? rows : rows.slice(0, 5)
  const max = rows[0]?.[valueKey] || 1
  return (
    <div className="p-5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-ink-2">{title}</span>
        {rows.length > 5 && (
          <button type="button" onClick={() => setExpanded((e) => !e)} className="text-xs font-medium text-brand hover:underline">
            {expanded ? 'Show top 5' : `Show top ${rows.length}`}
          </button>
        )}
      </div>
      <ol className="mt-3 space-y-2">
        {shown.map((r, i) => (
          <li key={r.name} className="grid grid-cols-[1.1rem_1fr_4rem] items-center gap-2 text-sm">
            <span className="tabular text-xs text-ink-3">{i + 1}</span>
            <div className="min-w-0">
              <div className={`truncate text-ink ${i === 0 ? 'font-semibold' : ''}`} title={r.name}>
                {r.name}
              </div>
              <div className="mt-1 h-1 rounded-full bg-black/5">
                <div className="h-1 rounded-full bg-brand" style={{ width: `${(r[valueKey] / max) * 100}%` }} />
              </div>
            </div>
            <span className="tabular text-right text-ink">{fmt.currencyCompact(r[valueKey])}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
