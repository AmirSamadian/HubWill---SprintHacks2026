import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartTooltip } from '../../components/charts'
import { Card, Swatch } from '../../components/ui'
import { SEGMENT_COLORS } from '../../config/channels'
import { formatMonth } from '../../lib/dates'
import { fmt } from '../../lib/format'
import { KpiTiles } from './shared'

const NEW = { name: 'First-time buyers', color: SEGMENT_COLORS.primary }
const REPEAT = { name: 'Repeat buyers', color: SEGMENT_COLORS.secondary }

// Percentage drawn inside each slice; `textColor` keeps it readable on light fills.
const RADIAN = Math.PI / 180
function sliceLabel({ cx, cy, midAngle, outerRadius, percent, payload }) {
  const r = outerRadius * 0.6
  return (
    <text
      x={cx + r * Math.cos(-midAngle * RADIAN)}
      y={cy + r * Math.sin(-midAngle * RADIAN)}
      fill={payload.textColor}
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={15}
      fontWeight={700}
    >
      {fmt.pct(percent)}
    </text>
  )
}

export default function CustomerSection({ report, previous }) {
  return (
    <section>
      <KpiTiles
        report={report}
        previous={previous}
        cols="sm:grid-cols-3 lg:grid-cols-5"
        ids={['buyers', 'newBuyers', 'repeatBuyerRate', 'satisfaction', 'listingsCreated']}
      />
      <BuyerSplit report={report} />
    </section>
  )
}

function BuyerSplit({ report }) {
  const c = report.customers
  const slices = [
    { ...NEW, value: c.newBuyers, fill: NEW.color, textColor: '#ffffff' },
    { ...REPEAT, value: c.repeatBuyers, fill: REPEAT.color, textColor: '#111111' },
  ]
  const total = c.newBuyers + c.repeatBuyers || 1

  return (
    <Card className="mt-5 p-5">
      <h3 className="text-sm font-semibold text-ink">Buyer split · {formatMonth(report.month)}</h3>
      <div className="mt-2 flex flex-col items-center gap-6 sm:flex-row sm:gap-10">
        <div className="size-56 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="name"
                outerRadius="95%"
                startAngle={90}
                endAngle={-270}
                stroke="#ffffff"
                strokeWidth={2}
                label={sliceLabel}
                labelLine={false}
              >
                {slices.map((s) => (
                  <Cell key={s.name} fill={s.fill} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip labelFormatter={() => 'Buyers'} valueFormatter={fmt.number} />} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="w-full max-w-sm space-y-3">
          {slices.map((s) => (
            <li key={s.name} className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-2 text-ink-2">
                <Swatch color={s.color} />
                {s.name}
              </span>
              <span className="tabular text-ink">
                <strong className="font-semibold">{fmt.number(s.value)}</strong>
                <span className="text-ink-3"> · {fmt.pct(s.value / total)}</span>
              </span>
            </li>
          ))}
          <li className="flex items-center justify-between gap-4 border-t border-black/5 pt-3">
            <span className="text-ink-2">Total buyers</span>
            <strong className="tabular font-semibold text-ink">{fmt.number(c.buyers)}</strong>
          </li>
        </ul>
      </div>
    </Card>
  )
}
