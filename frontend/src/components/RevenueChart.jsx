import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';
import { CHART_COLORS } from '../constants.jsx';
import { chartCommission } from '../utils/financials';
import { buildMonthWindow, makeMonthsTick } from '../utils/monthWindow.js';
import { ChartBarShape, ChartTooltip, ChartTooltipRow, ChartTooltipTitle } from './chartKit';

const COLOR = '#4ade80';

export default function RevenueChart({ data = [] }) {
  const [activeMonth, setActiveMonth] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  if (!data.length) {
    return (
      <div className="glass-panel p-4 flex flex-col min-h-0">
        <h3 className="text-white font-medium mb-3">Доход по месяцам</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">Нет данных для отображения</div>
      </div>
    );
  }

  const windowed = buildMonthWindow(data);
  const monthTick = makeMonthsTick(windowed);

  const chartData = windowed.map((d) => ({
    ...d,
    commission: chartCommission(d),
  }));

  const totalIncome = windowed.reduce((sum, d) => sum + (d.income || 0), 0);
  const activeEntry = activeMonth ? chartData.find((d) => d.month === activeMonth) : null;

  const handleBarEnter = (month, cx, cy) => {
    setActiveMonth(month);
    setTooltipPos({ x: cx, y: cy });
  };

  const shapeProps = {
    activeKey: activeMonth,
    onEnter: handleBarEnter,
    onLeave: () => setActiveMonth(null),
    xKey: 'month',
  };

  return (
    <figure role="img" aria-label="Диаграмма доходов по месяцам" className="glass-panel p-4 flex flex-col min-h-0">
      <figcaption className="sr-only">
        Доходы за {windowed.length} месяцев, всего {totalIncome.toLocaleString('ru-RU')} ₽
      </figcaption>
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h3 className="text-white font-medium">Доход по месяцам</h3>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLOR }}></div>
            <span className="text-xs text-gray-400">Доход</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: COLOR, opacity: 0.4 }}></div>
            <span className="text-xs text-gray-400">Комиссия</span>
          </div>
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
          <BarChart data={chartData} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <pattern
                id="hatch-income"
                width="6"
                height="6"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <rect width="6" height="6" fill={COLOR} />
                <line x1="0" y1="0" x2="0" y2="6" stroke="#0b0f19" strokeWidth="2" />
              </pattern>
              <pattern
                id="hatch-commission"
                width="6"
                height="6"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <rect width="6" height="6" fill={COLOR} fillOpacity="0.35" />
                <line x1="0" y1="0" x2="0" y2="6" stroke={COLOR} strokeWidth="2" strokeOpacity="0.5" />
              </pattern>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
            <XAxis
              dataKey="month"
              stroke={CHART_COLORS.textSecondary}
              fontSize={11}
              fontFamily="JetBrains Mono"
              interval={0}
              tickMargin={8}
              tickFormatter={monthTick}
            />
            <YAxis
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
              width={50}
              tickCount={6}
              tickFormatter={(value) => (value >= 1000 ? `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k` : value)}
            />
            <Bar
              dataKey="income"
              stackId="a"
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-income-${entry.month}`}
                  fill={i === chartData.length - 1 ? 'url(#hatch-income)' : COLOR}
                />
              ))}
            </Bar>
            <Bar
              dataKey="commission"
              stackId="a"
              radius={[4, 4, 0, 0]}
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-comm-${entry.month}`}
                  fill={i === chartData.length - 1 ? 'url(#hatch-commission)' : COLOR}
                  fillOpacity={i === chartData.length - 1 ? 1 : 0.35}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activeEntry && (
        <ChartTooltip x={tooltipPos.x} y={tooltipPos.y} anchor="right">
          <ChartTooltipTitle>{activeEntry.month}</ChartTooltipTitle>
          <ChartTooltipRow label="Доход" value={`${(activeEntry.income ?? 0).toLocaleString('ru-RU')} ₽`} color={COLOR} />
          <ChartTooltipRow
            label="Оборот"
            value={`${(activeEntry.turnover ?? 0).toLocaleString('ru-RU')} ₽`}
            color={COLOR}
            dim
          />
        </ChartTooltip>
      )}
    </figure>
  );
}
