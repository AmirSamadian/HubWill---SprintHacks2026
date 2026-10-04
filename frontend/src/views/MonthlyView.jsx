import { useState } from 'react'
import { availableMonths, fetchMonthlyReport } from '../api'
import { Badge, Field, inputClass, LoadState, SectionHeader } from '../components/ui'
import { formatMonth, formatShortDate } from '../lib/dates'
import { useAsync } from '../lib/useAsync'
import CategorySection from './monthly/CategorySection'
import CustomerSection from './monthly/CustomerSection'
import FinancialSection from './monthly/FinancialSection'
import ProductionSection from './monthly/ProductionSection'
import SalesSection from './monthly/SalesSection'
import Scorecard from './monthly/Scorecard'

export default function MonthlyView() {
  const months = availableMonths()
  // Default to the last complete month; the current month is still in progress.
  const [month, setMonth] = useState(months[1])
  const { data, loading, error } = useAsync(() => fetchMonthlyReport(month), [month])
  const report = data?.report

  return (
    <section>
      <SectionHeader
        eyebrow="COO Scorecard"
        title="Monthly Operating View"
        subtitle="Outcomes, operating drivers and early warning indicators for the month."
      >
        <Field label="Month">
          <select className={`${inputClass} min-w-48`} value={month} onChange={(e) => setMonth(e.target.value)}>
            {months.map((m, i) => (
              <option key={m} value={m}>
                {formatMonth(m)}
                {i === 0 ? ' (month to date)' : ''}
              </option>
            ))}
          </select>
        </Field>
      </SectionHeader>

      <LoadState loading={loading} error={error}>
        {report && (
          <div className="space-y-12">
            <div className="flex flex-wrap items-center gap-3 text-sm text-ink-2">
              <span className="text-lg font-semibold text-ink">{formatMonth(report.month)}</span>
              {report.isPartial ? (
                <Badge>Month to date · through {formatShortDate(report.through)}</Badge>
              ) : (
                <span>{report.daysReported} days reported</span>
              )}
              <span className="text-ink-3">
                Deltas compare to {formatMonth(data.previous.month)}
                {report.isPartial ? '; totals are not compared until the month closes.' : '.'}
              </span>
            </div>

            <Scorecard report={report} previous={data.previous} />
            <FinancialSection report={report} previous={data.previous} history={data.history} />
            <ProductionSection report={report} previous={data.previous} />
            <SalesSection report={report} previous={data.previous} />
            <CategorySection report={report} />
            <CustomerSection report={report} previous={data.previous} history={data.history} />
          </div>
        )}
      </LoadState>
    </section>
  )
}
