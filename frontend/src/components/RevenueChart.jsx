import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const COLORS = {
  past: '#38bdf8',
  current: '#4ade80',
  forecast: '#1e293b',
}

export default function RevenueChart({ data = [] }) {
  if (!data.length) {
    return (
      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Доход по месяцам</h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  const now = new Date()
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

  return (
    <div className="glass-panel p-6">
      <h3 className="text-white font-medium mb-4">Доход по месяцам</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="month"
              stroke="#64748b"
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
              stroke="#64748b"
              fontSize={12}
              fontFamily="JetBrains Mono"
              tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#162032',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                borderRadius: '8px',
                fontFamily: 'JetBrains Mono',
              }}
              formatter={(value) => [`${value.toLocaleString('ru-RU')} ₽`, 'Доход']}
            />
            <Bar dataKey="income" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.month?.startsWith(currentMonth) ? COLORS.current : COLORS.past}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
