import { useState } from 'react'
import { Card, DeltaPill } from '../../components/ui'
import { resolveChannels } from '../../config/channels'
import { addMonths, formatMonth } from '../../lib/dates'
import { fmt } from '../../lib/format'
import { KPIS, kpiDelta, kpiValue, SCORECARD, topCategories } from '../../lib/kpis'
import { watchItems } from '../../lib/watchlist'

/** The COO operating view, most important first. */
export default function Overview({ report, previous }) {
  return (
    <div className="space-y-4">
      <HeadlineRow report={report} previous={previous} />
      <WatchList report={report} previous={previous} />
      <CategoryCard report={report} />
    </div>
  )
}

// ---------- headline: revenue (with marketplace split), growth, margin, price ----------

function HeadlineRow({ report, previous }) {
  const comparison = `vs. ${formatMonth(previous.month, 'short')}`
  return (
    <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-[1.7fr_1fr_1fr_1fr]">
      <RevenueTile report={report} previous={previous} comparison={comparison} />
      <KpiTile
        id="revenueGrowthYoY"
        label="Revenue Growth (YoY)"
        report={report}
        previous={previous}
        comparison={comparison}
        detail={`${formatMonth(addMonths(report.month, -12), 'short')}: ${fmt.currencyCompact(report.financial.revenuePriorYear)}`}
      />
      <KpiTile id="netMarginPct" label="Net Margin" report={report} previous={previous} comparison={comparison} />
      <KpiTile
        id="avgSellingPrice"
        label="Avg. Selling Price"
        report={report}
        previous={previous}
        comparison={comparison}
        detail={`${fmt.number(report.sales.unitsSold)} units · median ${fmt.currencyCents(report.sales.medianSalePrice)}`}
      />
    </div>
  )
}

// Every headline tile uses the same rows — label, value, change, detail — so
// values and pills line up across the row regardless of label length.
const LABEL = 'truncate text-sm font-medium'
const VALUE = 'tabular mt-2 text-3xl font-bold leading-none tracking-tight'
const CHANGE = 'mt-3 flex h-6 items-center gap-2 text-xs'

// Marketplace segments inside the blue tile use white at stepped opacities;
// each is labeled by name, so identity never rests on the shade alone.
const SHADES = [1, 0.62, 0.34, 0.2, 0.12]

function RevenueTile({ report, previous, comparison }) {
  const total = report.channels.reduce((s, c) => s + c.revenue, 0) || 1
  const rows = resolveChannels(report.channels).map((ch, i) => {
    const revenue = report.channels.find((c) => c.id === ch.id)?.revenue ?? 0
    return { ...ch, revenue, share: revenue / total, shade: SHADES[i] ?? 0.1 }
  })

  return (
    <div className="rounded-lg bg-brand p-5 text-white shadow-sm md:col-span-3 xl:col-span-1">
      <div className={`${LABEL} text-white/80`}>{KPIS.revenue.label}</div>
      <div className={VALUE}>{fmt.currency(kpiValue('revenue', report))}</div>
      <div className={`${CHANGE} text-white/75`}>
        <DeltaPill delta={kpiDelta('revenue', report, previous)} better="up" inverted />
        <span>{report.isPartial ? 'Month to date' : comparison}</span>
      </div>

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
          </li>
        ))}
      </ul>
    </div>
  )
}

function KpiTile({ id, label, report, previous, comparison, detail }) {
  const kpi = KPIS[id]
  return (
    <Card className="p-5">
      <div className={`${LABEL} text-ink-2`} title={kpi.label}>
        {label}
      </div>
      <div className={`${VALUE} text-ink`}>{fmt[kpi.format](kpiValue(id, report))}</div>
      <div className={`${CHANGE} text-ink-3`}>
        <DeltaPill delta={kpiDelta(id, report, previous)} better={kpi.better} />
        <span>{comparison}</span>
      </div>
      {detail && <div className="mt-4 border-t border-black/5 pt-3 text-xs text-ink-3">{detail}</div>}
    </Card>
  )
}

// ---------- early warnings ----------

// Watch list items shown before "Show all".
const WATCH_PREVIEW = 2

function WatchList({ report, previous }) {
  const [showAll, setShowAll] = useState(false)
  const items = watchItems(report, previous)
  if (!items.length) return null
  const shown = showAll ? items : items.slice(0, WATCH_PREVIEW)

  return (
    <div className="flex gap-3 rounded-lg bg-critical/5 px-4 py-3 ring-1 ring-critical/15" role="status">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-critical text-xs font-bold text-white" aria-hidden="true">
        !
      </span>
      <div className="min-w-0 flex-1 text-sm">
        <span className="font-semibold text-ink">Watch list</span>
        <ul className="mt-1 space-y-1 text-ink-2">
          {shown.map((i) => (
            <li key={i.id} className="flex flex-wrap items-baseline justify-between gap-x-4">
              <span>
                <strong className="font-semibold text-ink">{i.item}</strong> sales in the{' '}
                <strong className="font-semibold text-ink">{i.category}</strong> category have gone down by{' '}
                <strong className="tabular font-semibold text-critical">{fmt.pct(-i.change)}</strong> since last month
              </span>
              <span className="tabular text-xs text-ink-3">
                {fmt.currency(i.previousRevenue)} → {fmt.currency(i.revenue)}
              </span>
            </li>
          ))}
        </ul>
        {items.length > WATCH_PREVIEW && (
          <button type="button" onClick={() => setShowAll((s) => !s)} className="mt-1 text-xs font-medium text-brand hover:underline">
            {showAll ? 'Show fewer' : `Show all ${items.length}`}
          </button>
        )}
      </div>
    </div>
  )
}

// ---------- top categories ----------

function CategoryCard({ report }) {
  const g = SCORECARD.find((s) => s.id === 'categories')
  return (
    <Card>
      <div className="border-b border-black/5 px-5 pb-3 pt-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-brand">{g.eyebrow}</h3>
      </div>
      <div className="grid divide-y divide-black/5 lg:grid-cols-2 lg:divide-x lg:divide-y-0">
        <TopList title="By revenue" rows={topCategories(report, 'revenue')} valueKey="revenue" empty="No sales recorded this month." />
        <TopList
          title="By margin"
          rows={topCategories(report, 'margin')}
          valueKey="margin"
          empty="Unavailable: the database has no cost-of-goods data to calculate margin."
        />
      </div>
    </Card>
  )
}

/** Ranked list showing the top 5, expandable to the full top 10. */
function TopList({ title, rows, valueKey, empty }) {
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
      {rows.length === 0 && <p className="mt-3 text-sm text-ink-3">{empty}</p>}
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
