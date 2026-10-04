import { useState } from 'react'
import { fetchDailyReport, latestReportDate } from '../api'
import { DatePicker } from '../components/pickers'
import { Card, LoadState, Swatch } from '../components/ui'
import { resolveChannels } from '../config/channels'
import { fmt } from '../lib/format'
import { useAsync } from '../lib/useAsync'

export default function DailyView() {
  const latest = latestReportDate()
  const [date, setDate] = useState(latest)
  const { data, loading, error } = useAsync(() => fetchDailyReport(date), [date])

  return (
    <section className="scale-up">
      <div className="mb-6">
        <DatePicker value={date} onChange={setDate} max={latest} />
      </div>

      <LoadState loading={loading} error={error}>
        {data && <NightlyReport report={data} />}
      </LoadState>
    </section>
  )
}

/** The nightly channel breakdown for one day: each marketplace, then the enterprise total. */
function NightlyReport({ report }) {
  // One row per configured or reported marketplace, zero-filled if missing.
  const byId = new Map(report.channels.map((c) => [c.id, c]))
  const rows = resolveChannels(report.channels).map((c) => ({
    ...c,
    revenue: byId.get(c.id)?.revenue ?? 0,
    customers: byId.get(c.id)?.customers ?? 0,
  }))
  const total = {
    revenue: rows.reduce((s, r) => s + r.revenue, 0),
    customers: rows.reduce((s, r) => s + r.customers, 0),
  }

  return (
    <Card className="overflow-hidden">
      <div className="px-6 pb-3 pt-5">
        <div className="text-xs font-bold uppercase tracking-wider text-brand">Nightly channel breakdown</div>
        <h2 className="mt-0.5 text-lg font-bold tracking-tight text-ink">Revenue and customers by marketplace</h2>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left">
          <thead>
            <tr className="border-y border-black/5 bg-page/70 text-xs font-bold uppercase tracking-wider text-ink-3">
              <th className="px-6 py-2.5">Revenue source</th>
              <th className="px-6 py-2.5 text-right">Daily revenue</th>
              <th className="px-6 py-2.5 text-right">Daily customers</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {rows.map((r) => {
              const share = total.revenue ? r.revenue / total.revenue : 0
              return (
                <tr key={r.id}>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2.5 text-lg font-bold uppercase tracking-tight text-ink">
                      <Swatch color={r.color} />
                      {r.name}
                    </div>
                    <div className="mt-2 flex max-w-56 items-center gap-2 pl-5">
                      <div className="h-1.5 flex-1 rounded-full bg-black/5">
                        <div className="h-1.5 rounded-full" style={{ width: `${share * 100}%`, backgroundColor: r.color }} />
                      </div>
                      <span className="tabular text-xs text-ink-3">{fmt.pct(share)}</span>
                    </div>
                  </td>
                  <td className="tabular px-6 py-4 text-right text-2xl font-bold tracking-tight text-ink">{fmt.currency(r.revenue)}</td>
                  <td className="tabular px-6 py-4 text-right text-2xl font-bold tracking-tight text-ink">{fmt.number(r.customers)}</td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr className="bg-brand text-white">
              <td className="px-6 py-5 text-lg font-extrabold uppercase tracking-tight">Total E-Commerce</td>
              <td className="tabular px-6 py-5 text-right text-3xl font-bold tracking-tight">{fmt.currency(total.revenue)}</td>
              <td className="tabular px-6 py-5 text-right text-3xl font-bold tracking-tight">{fmt.number(total.customers)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="px-6 py-3 text-xs text-ink-3">Other marketplaces appear as separate rows as the channel mix evolves.</p>
    </Card>
  )
}
