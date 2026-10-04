import { StatTile } from '../../components/ui'
import { fmt } from '../../lib/format'
import { KPIS, kpiDelta, kpiValue } from '../../lib/kpis'

/** A grid of KPI tiles with month-over-month deltas. */
export function KpiTiles({ ids, report, previous, cols = 'sm:grid-cols-2 lg:grid-cols-3', emphasis = [] }) {
  return (
    <div className={`grid grid-cols-1 gap-4 ${cols}`}>
      {ids.map((id) => {
        const kpi = KPIS[id]
        return (
          <StatTile
            key={id}
            label={kpi.label}
            value={fmt[kpi.format](kpiValue(id, report))}
            delta={kpiDelta(id, report, previous)}
            better={kpi.better}
            emphasis={emphasis.includes(id)}
          />
        )
      })}
    </div>
  )
}
