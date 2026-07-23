import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { CHART_COLORS } from '../constants'
import { isCurrentMonth } from '../utils/isCurrentMonth'

const COLORS = {
  past: CHART_COLORS.cyberBlue,
  current: CHART_COLORS.neonGreen,
  currentDim: '#22763d',
  pastDim: '#1a6a9e',
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const income = payload.find(p => p.dataKey === 'income')
  const turnover = payload.reduce((s, p) => s + (p.value || 0), 0)
  const isCur = income && isCurrentMonth(income.payload?.month)
  const dimColor = isCur ? COLORS.currentDim : COLORS.pastDim
  const brightColor = isCur ? COLORS.current : COLORS.past
  return (
    <div style={{
      backgroundColor: CHART_COLORS.panelBg,
      border: '1px solid rgba(56, 189, 248, 0.3)',
      borderRadius: '8px',
      fontFamily: 'JetBrains Mono',
      padding: '8px 12px',
    }}>
      <div style={{ color: '#ffffff', fontSize: 13, marginBottom: 4 }}>{label}</div>
      {income && (
        <div style={{ color: brightColor, fontSize: 12 }}>
          Доход: {(income.value ?? 0).toLocaleString('ru-RU')} ₽
        </div>
      )}
      <div style={{ color: dimColor, fontSize: 12 }}>
        Оборот: {turnover.toLocaleString('ru-RU')} ₽
      </div>
    </div>
  )
}

const ActiveBarShape = (props) => {
  const { x, y, width, height, fill } = props
  if (!height || height <= 0) return null
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      rx={2}
      ry={2}
      fill={fill}
      stroke="#ffffff"
      strokeWidth={1.5}
    />
  )
}

export default function RevenueChart({ data = [] }) {
  if (!data.length) {
    return (
      <div className="glass-panel p-4 flex flex-col min-h-0">
        <h3 className="text-white font-medium mb-3">Доход по месяцам</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  const chartData = data.map(d => ({
    ...d,
    commission: Math.max((d.turnover || 0) - (d.income || 0), 0),
  }))

  const totalIncome = data.reduce((sum, d) => sum + (d.income || 0), 0)

  return (
    <figure role="img" aria-label="Диаграмма доходов по месяцам" className="glass-panel p-4 flex flex-col min-h-0">
      <figcaption className="sr-only">Доходы за {data.length} месяцев, всего {totalIncome.toLocaleString('ru-RU')} ₽</figcaption>
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h3 className="text-white font-medium">Доход по месяцам</h3>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLORS.past }}></div>
            <span className="text-xs text-gray-400">Факт</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLORS.current }}></div>
            <span className="text-xs text-gray-400">Текущий месяц</span>
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 15, right: 10, left: 0, bottom: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
            <XAxis
              dataKey="month"
              stroke={CHART_COLORS.textSecondary}
              fontSize={11}
              fontFamily="JetBrains Mono"
              interval={0}
              angle={-90}
              textAnchor="end"
              height={50}
              tickMargin={0}
              tickFormatter={(value) => {
                if (!value) return ''
                const parts = value.split(' ')
                const month = parts[0] || ''
                return month.length > 3 ? month.substring(0, 3) + '.' : month
              }}
            />
            <YAxis
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
              width={45}
              tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              content={<CustomTooltip />}
              cursor={false}
            />
            <Bar
              dataKey="income"
              stackId="a"
              radius={[0, 0, 0, 0]}
              activeBar={<ActiveBarShape />}
            >
              {chartData.map((entry) => (
                <Cell
                  key={`cell-income-${entry.month}`}
                  fill={isCurrentMonth(entry.month) ? COLORS.current : COLORS.past}
                />
              ))}
            </Bar>
            <Bar
              dataKey="commission"
              stackId="a"
              radius={[4, 4, 0, 0]}
              activeBar={<ActiveBarShape />}
            >
              {chartData.map((entry) => (
                <Cell
                  key={`cell-comm-${entry.month}`}
                  fill={isCurrentMonth(entry.month) ? COLORS.currentDim : COLORS.pastDim}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
