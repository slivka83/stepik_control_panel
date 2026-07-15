import { useState, useEffect } from 'react'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

export default function Financials() {
  const [revenue, setRevenue] = useState({ months: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchRevenue = async () => {
      try {
        const res = await axios.get('/api/dashboard/revenue')
        setRevenue(res.data)
      } catch (err) {
        console.error('Revenue fetch error:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchRevenue()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyber-blue font-mono animate-pulse">Загрузка данных...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Финансовая аналитика</h1>
      </div>

      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Доход по месяцам</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={revenue.months} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="month"
                stroke="#64748b"
                fontSize={12}
                fontFamily="JetBrains Mono"
                tickFormatter={(value) => {
                  const date = new Date(value)
                  return date.toLocaleDateString('ru-RU', { month: 'short', year: '2-digit' })
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
              <Legend />
              <Bar dataKey="revenue" name="Доход" fill="#38bdf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-panel p-6">
          <h3 className="text-white font-medium mb-4">Налоговый дашборд</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-2 border-b border-gray-700">
              <span className="text-gray-400 text-sm">ИНН</span>
              <span className="font-mono text-white text-sm">Не указан</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-700">
              <span className="text-gray-400 text-sm">БИК</span>
              <span className="font-mono text-white text-sm">Не указан</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-700">
              <span className="text-gray-400 text-sm">Система налогообложения</span>
              <span className="font-mono text-white text-sm">Не указана</span>
            </div>
            <div className="mt-4 p-3 bg-amber-alert/10 border border-amber-alert/20 rounded-lg">
              <span className="text-amber-alert text-sm">⚠ Заполните реквизиты для корректного отображения налогового дашборда</span>
            </div>
          </div>
        </div>

        <div className="glass-panel p-6">
          <h3 className="text-white font-medium mb-4">B2B-Менеджер</h3>
          <div className="space-y-4">
            <div className="border-2 border-dashed border-gray-700 rounded-lg p-6 text-center">
              <div className="text-2xl mb-2">📁</div>
              <p className="text-gray-400 text-sm mb-3">
                Импортируйте CSV-файл с email-адресами корпоративных клиентов
              </p>
              <label className="inline-block px-4 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium cursor-pointer">
                Выбрать файл
                <input type="file" accept=".csv" className="hidden" />
              </label>
            </div>
            <div className="text-xs text-gray-500">
              Формат: CSV с колонкой "email" в первой строке
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
