import { useState, useId } from 'react'
import { createPortal } from 'react-dom'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts'
import { CHART_COLORS } from '../constants.jsx'
import { buildMonthWindow } from '../utils/monthWindow.js'

const COLOR_BRIGHT = '#dc2626'
const COLOR_DIM = '#8b2040'

function BarShape({ activeMonth, onBarEnter, onBarLeave, ...props }) {
  const { x, y, width, height, fill, fillOpacity, payload } = props
  if (!height || height <= 0) return null
  const isActive = payload && activeMonth === payload.month
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      rx={2}
      ry={2}
      fill={fill}
      fillOpacity={fillOpacity ?? 1}
      stroke={isActive ? '#ffffff' : 'none'}
      strokeWidth={isActive ? 1.5 : 0}
      onMouseEnter={(e) => payload && onBarEnter(payload.month, e.clientX, e.clientY)}
      onMouseMove={(e) => onBarEnter(payload.month, e.clientX, e.clientY)}
      onMouseLeave={onBarLeave}
      style={{ pointerEvents: 'all' }}
    />
  )
}

export default function ActiveStudentsChart({
  data = {},
  title = 'Активные студенты',
  showTitle = true,
  hatched,
  primaryColor,
  secondaryColor,
  hideLightLegend,
  hideDarkLegend,
  lightLabel,
  tooltipRight,
}) {
  const [activeMonth, setActiveMonth] = useState(null)
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 })
  const uid = useId()

  const bright = primaryColor || COLOR_BRIGHT
  const dim = secondaryColor || COLOR_DIM

  const months = buildMonthWindow(data.months || [])

  if (!months.length) {
    return (
      <div className="glass-panel p-4 flex flex-col min-h-0">
        <h3 className="text-white font-medium mb-3">{title}</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          Нет данных для отображения
        </div>
      </div>
    )
  }

  const chartData = months.map(d => ({
    ...d,
    overlap: Math.max((d.dark || 0) - (d.light || 0), 0),
  }))

  const maxVal = Math.max(...chartData.map(d => Math.max(d.dark || 0, d.light || 0)))
  const yAxisCompact = maxVal >= 1000

  const handleBarEnter = (month, cx, cy) => {
    setActiveMonth(month)
    setTooltipPos({ x: cx, y: cy })
  }

  const activeEntry = activeMonth ? chartData.find(d => d.month === activeMonth) : null

  return (
    <figure role="img" aria-label={`Диаграмма ${title}`} className="glass-panel p-4 flex flex-col min-h-0">
      <figcaption className="sr-only">{title} за {months.length} месяцев</figcaption>
      <div className="flex items-center justify-between mb-2 shrink-0">
        {showTitle && <h3 className="text-white font-medium">{title}</h3>}
        <div className="flex items-center gap-4">
          {!hideLightLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: bright }}></div>
              <span className="text-xs text-gray-400">Уникальные</span>
            </div>
          )}
          {!hideDarkLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: dim }}></div>
              <span className="text-xs text-gray-400">Уникальные по курсам</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <svg className="w-3 h-3" viewBox="0 0 12 12">
              <line x1="0" y1="6" x2="6" y2="12" stroke="#94a3b8" strokeWidth="1.5" />
              <line x1="0" y1="0" x2="12" y2="12" stroke="#94a3b8" strokeWidth="1.5" />
              <line x1="6" y1="0" x2="12" y2="6" stroke="#94a3b8" strokeWidth="1.5" />
            </svg>
            <span className="text-xs text-gray-400">не завершён</span>
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 15, right: 10, left: 0, bottom: 0 }}
          >
            {hatched && (
            <defs>
              <pattern id={`ha-${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill={dim} fillOpacity="0.5" />
                <line x1="0" y1="0" x2="0" y2="6" stroke={bright} strokeWidth="2" />
              </pattern>
              <pattern id={`hl-${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill={bright} />
                <line x1="0" y1="0" x2="0" y2="6" stroke={dim} strokeWidth="2" strokeOpacity="0.4" />
              </pattern>
            </defs>
            )}
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
            <XAxis
              dataKey="month"
              stroke={CHART_COLORS.textSecondary}
              fontSize={11}
              fontFamily="JetBrains Mono"
              interval={0}
              tickMargin={8}
              tickFormatter={(value) => {
                if (!value) return ''
                const parts = value.split(' ')
                const month = parts[0] || ''
                return month.length > 3 ? month.substring(0, 3) : month
              }}
            />
            <YAxis
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
              width={50}
              tickCount={6}
              tickFormatter={(value) => {
                if (value === 0) return '0'
                if (yAxisCompact) return `${(value / 1000).toFixed(1)}k`
                return value.toLocaleString('ru-RU')
              }}
            />
            <Bar
              dataKey="light"
              stackId="a"
              shape={(props) => (
                <BarShape
                  activeMonth={activeMonth}
                  onBarEnter={handleBarEnter}
                  onBarLeave={() => setActiveMonth(null)}
                  {...props}
                />
              )}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-light-${entry.month}`}
                  fill={hatched && i === chartData.length - 1 ? `url(#hl-${uid})` : bright}
                />
              ))}
            </Bar>
            <Bar
              dataKey="overlap"
              stackId="a"
              radius={[4, 4, 0, 0]}
              shape={(props) => (
                <BarShape
                  activeMonth={activeMonth}
                  onBarEnter={handleBarEnter}
                  onBarLeave={() => setActiveMonth(null)}
                  {...props}
                />
              )}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-overlap-${entry.month}`}
                  fill={hatched && i === chartData.length - 1 ? `url(#ha-${uid})` : dim}
                  fillOpacity={hatched && i === chartData.length - 1 ? 1 : 0.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activeEntry && createPortal(
        <div
          className="fixed z-[100] whitespace-nowrap px-3 py-2 rounded-lg pointer-events-none"
          style={{
            left: tooltipRight ? `${tooltipPos.x + 12}px` : `${tooltipPos.x - 12}px`,
            top: tooltipRight ? `${tooltipPos.y - 12}px` : `${tooltipPos.y}px`,
            transform: tooltipRight ? 'translate(0, -100%)' : 'translate(-100%, -100%)',
            backgroundColor: CHART_COLORS.panelBg,
            border: '1px solid rgba(56, 189, 248, 0.3)',
            fontFamily: 'JetBrains Mono',
          }}
        >
          <div style={{ color: '#ffffff', fontSize: 13, marginBottom: 4 }}>{activeEntry.month}</div>
          <div style={{ color: bright, fontSize: 12 }}>
            {lightLabel || title || 'Уникальные'}: {(activeEntry.light ?? 0).toLocaleString('ru-RU')}
          </div>
          {!hideDarkLegend && (
            <div style={{ color: dim, fontSize: 12 }}>
              Уникальные по курсам: {(activeEntry.dark ?? 0).toLocaleString('ru-RU')}
            </div>
          )}
        </div>,
        document.body
      )}
    </figure>
  )
}
