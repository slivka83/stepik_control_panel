import { useState } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { COHORT_COLORS, COHORT_LABELS, CHART_COLORS } from '../constants'

export default function StudentsChart({ data = {} }) {
  const [hidden, setHidden] = useState(new Set())

  const chartData = Object.entries(data).map(([key, value]) => ({
    name: COHORT_LABELS[key] || key,
    value,
    color: COHORT_COLORS[key]?.hex,
    key,
  }))

  const visibleData = chartData.filter((d) => !hidden.has(d.key))
  const total = chartData.reduce((sum, item) => sum + (item.value || 0), 0)
  const visibleTotal = visibleData.reduce((sum, item) => sum + (item.value || 0), 0)

  const toggleKey = (key) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (!total) {
    return (
      <div className="glass-panel p-4">
        <h3 className="text-white font-medium mb-3">Студенты</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  return (
    <figure role="img" aria-label="Диаграмма когортной сегментации студентов" className="glass-panel p-4 flex flex-col min-h-0">
      <figcaption className="sr-only">
        Всего студентов: {total}. Активные: {chartData[0]?.value || 0}, пассивные: {chartData[1]?.value || 0},
        затухающие: {chartData[2]?.value || 0}, спящие: {chartData[3]?.value || 0}.
      </figcaption>
      <h3 className="text-white font-medium mb-3 shrink-0">Студенты</h3>
      <div className="flex-1 min-h-0 flex items-start gap-4">
        <div className="h-full flex-1 min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={visibleData.length ? visibleData : [{ name: '', value: 1, color: '#1e293b' }]}
                cx="50%"
                cy="50%"
                innerRadius="55%"
                outerRadius="85%"
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {(visibleData.length ? visibleData : [{ color: '#1e293b' }]).map((entry, i) => (
                  <Cell key={`cell-${i}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: CHART_COLORS.panelBg,
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  borderRadius: '8px',
                  fontFamily: 'JetBrains Mono',
                  color: '#ffffff',
                }}
                itemStyle={{ color: '#ffffff' }}
                formatter={(value, name) => [`${value.toLocaleString('ru-RU')} чел.`, name]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-col gap-2 shrink-0 pt-[7%]">
          {chartData.map((item) => {
            const isHidden = hidden.has(item.key)
            return (
              <div
                key={item.name}
                className="flex items-center gap-3 cursor-pointer select-none transition-opacity"
                style={{ opacity: isHidden ? 0.35 : 1 }}
                onClick={() => toggleKey(item.key)}
              >
                <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: item.color }}></div>
                <span className="text-gray-400 text-sm">{item.name}</span>
                <span className="font-mono text-white text-sm ml-auto">{item.value}</span>
                <span className="text-gray-500 text-xs font-mono w-12 text-right">
                  {((item.value / total) * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </figure>
  )
}
