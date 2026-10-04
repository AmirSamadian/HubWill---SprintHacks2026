import { useState } from 'react'
import { availableMonths, fetchMonthlyReport } from '../api'
import { MonthPicker } from '../components/pickers'
import { Disclosure, LoadState, Tabs } from '../components/ui'
import { formatShortDate } from '../lib/dates'
import { useAsync } from '../lib/useAsync'
import CategorySection from './monthly/CategorySection'
import CustomerSection from './monthly/CustomerSection'
import FinancialSection from './monthly/FinancialSection'
import Overview from './monthly/Overview'

const DETAIL_TABS = [
  { id: 'financial', label: 'Financial', Section: FinancialSection },
  { id: 'categories', label: 'Categories', Section: CategorySection },
  { id: 'customers', label: 'Customers', Section: CustomerSection },
]

export default function MonthlyView() {
  const months = availableMonths() // newest first
  // Default to the last complete month; the current month is still in progress.
  const [month, setMonth] = useState(months[1])
  const { data, loading, error } = useAsync(() => fetchMonthlyReport(month), [month])
  const report = data?.report

  return (
    <section className="scale-up">
      <div className="mb-6">
        <MonthPicker
          months={months}
          value={month}
          onChange={setMonth}
          note={month === months[0] && report?.isPartial ? `Through ${formatShortDate(report.through)}` : undefined}
        />
      </div>

      <LoadState loading={loading} error={error}>
        {report && (
          <>
            <Overview report={report} previous={data.previous} />
            <DetailedPerformance report={report} previous={data.previous} history={data.history} />
          </>
        )}
      </LoadState>
    </section>
  )
}

/** Supporting charts, collapsed by default so the scorecard stays the focus. */
function DetailedPerformance({ report, previous, history }) {
  const [tab, setTab] = useState(DETAIL_TABS[0].id)
  const { Section } = DETAIL_TABS.find((t) => t.id === tab)

  return (
    <Disclosure
      className="mt-4"
      title="Detailed performance"
      summary="Revenue trends, all categories and customer retention"
      actions={<Tabs tabs={DETAIL_TABS} value={tab} onChange={setTab} />}
    >
      <Section report={report} previous={previous} history={history} />
    </Disclosure>
  )
}
