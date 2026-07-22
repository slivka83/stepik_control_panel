import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { CHART_COLORS } from '../constants'
import { isCurrentMonth } from '../utils/isCurrentMonth'

const COLORS = {
  past: CHART_COLORS.cyberBlue,
  current: CHART_COLORS.neonGreen,
}

export default function RevenueChart({ data = [] }) {
  if (!data.length) {
    return (
      <div className="glass-panel p-4">
        <h3 className="text-white font-medium mb-3">Доход по месяцам</h3>
        <div className="h-48 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  const totalIncome = data.reduce((sum, d) => sum + (d.income || 0), 0)

  return (
    <figure role="img" aria-label="Диаграмма доходов по месяцам" className="glass-panel p-4">
      <figcaption className="sr-only">Доходы за {data.length} месяцев, всего {totalIncome.toLocaleString('ru-RU')} ₽</figcaption>
      <h3 className="text-white font-medium mb-3">Доход по месяцам</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
            <XAxis
              dataKey="month"
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
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
              tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: CHART_COLORS.panelBg,
                border: '1px solid rgba(56, 189, 248, 0.3)',
                borderRadius: '8px',
                fontFamily: 'JetBrains Mono',
              }}
              formatter={(value) => [`${(value ?? 0).toLocaleString('ru-RU')} ₽`, 'Доход']}
            />
            <Bar dataKey="income" radius={[4, 4, 0, 0]}>
              {data.map((entry) => (
                <Cell
                  key={`cell-${entry.month}-${entry.year}`}
                  fill={isCurrentMonth(entry.month) ? COLORS.current : COLORS.past}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}
