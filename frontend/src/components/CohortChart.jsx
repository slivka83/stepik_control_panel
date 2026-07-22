import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { COHORT_COLORS, COHORT_LABELS, CHART_COLORS } from '../constants'

export default function CohortChart({ data = {} }) {
  const chartData = Object.entries(data).map(([key, value]) => ({
    name: COHORT_LABELS[key] || key,
    value,
    color: COHORT_COLORS[key]?.hex,
  }))

  const total = chartData.reduce((sum, item) => sum + (item.value || 0), 0)

  if (!total) {
    return (
      <div className="glass-panel p-4">
        <h3 className="text-white font-medium mb-3">Когортная сегментация</h3>
        <div className="h-48 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  return (
    <figure role="img" aria-label="Диаграмма когортной сегментации студентов" className="glass-panel p-4">
      <figcaption className="sr-only">
        Всего студентов: {total}. Активные: {chartData[0]?.value || 0}, пассивные: {chartData[1]?.value || 0},
        затухающие: {chartData[2]?.value || 0}, спящие: {chartData[3]?.value || 0}.
      </figcaption>
      <h3 className="text-white font-medium mb-3">Когортная сегментация</h3>
      <div className="flex items-center gap-4">
        <div className="h-40 w-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
              >
                {chartData.map((entry) => (
                  <Cell key={`cell-${entry.name}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: CHART_COLORS.panelBg,
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  borderRadius: '8px',
                  fontFamily: 'JetBrains Mono',
                }}
                formatter={(value) => value.toLocaleString('ru-RU')}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-2">
          {chartData.map((item) => (
            <div key={item.name} className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }}></div>
              <span className="text-gray-400 text-sm">{item.name}</span>
              <span className="font-mono text-white text-sm ml-auto">{item.value}</span>
              <span className="text-gray-500 text-xs font-mono w-12 text-right">
                {((item.value / total) * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </figure>
  )
}
