import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

const COHORT_COLORS = {
  active: '#4ade80',
  passive: '#38bdf8',
  fading: '#f59e0b',
  sleeping: '#f43f5e',
}

const COHORT_LABELS = {
  active: 'Активные',
  passive: 'Пассивные',
  fading: 'Затухающие',
  sleeping: 'Спящие',
}

export default function CohortChart({ data = {} }) {
  const chartData = Object.entries(data).map(([key, value]) => ({
    name: COHORT_LABELS[key] || key,
    value,
    color: COHORT_COLORS[key],
  }))

  const total = chartData.reduce((sum, item) => sum + item.value, 0)

  if (!total) {
    return (
      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Когортная сегментация</h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  return (
    <div className="glass-panel p-6">
      <h3 className="text-white font-medium mb-4">Когортная сегментация</h3>
      <div className="flex items-center gap-6">
        <div className="h-48 w-48">
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
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: '#162032',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  borderRadius: '8px',
                  fontFamily: 'JetBrains Mono',
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-3">
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
    </div>
  )
}
