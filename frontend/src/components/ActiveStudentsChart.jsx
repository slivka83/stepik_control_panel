import { useState, useId } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';
import { CHART_COLORS } from '../constants.jsx';
import { buildMonthWindow } from '../utils/monthWindow.js';
import { ChartBarShape, ChartTooltip, ChartTooltipRow, ChartTooltipTitle } from './chartKit';

const COLOR_BRIGHT = '#dc2626';
const COLOR_DIM = '#8b2040';

export function darkTooltipValue(entry, useOverlap) {
  if (useOverlap) return Math.max((entry.dark || 0) - (entry.light || 0), 0);
  return entry.dark || 0;
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
  darkLabel,
  darkTooltipOverlap,
  tooltipRight,
}) {
  const [activeMonth, setActiveMonth] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const uid = useId();

  const bright = primaryColor || COLOR_BRIGHT;
  const dim = secondaryColor || COLOR_DIM;

  const months = buildMonthWindow(data.months || []);

  if (!months.length) {
    return (
      <div className="glass-panel p-4 flex flex-col min-h-0">
        <h3 className="text-white font-medium mb-3">{title}</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">Нет данных для отображения</div>
      </div>
    );
  }

  const chartData = months.map((d) => ({
    ...d,
    overlap: Math.max((d.dark || 0) - (d.light || 0), 0),
  }));

  const maxVal = Math.max(...chartData.map((d) => Math.max(d.dark || 0, d.light || 0)));
  const yAxisCompact = maxVal >= 1000;

  const handleBarEnter = (month, cx, cy) => {
    setActiveMonth(month);
    setTooltipPos({ x: cx, y: cy });
  };

  const activeEntry = activeMonth ? chartData.find((d) => d.month === activeMonth) : null;

  const shapeProps = {
    activeKey: activeMonth,
    onEnter: handleBarEnter,
    onLeave: () => setActiveMonth(null),
    xKey: 'month',
  };

  return (
    <figure role="img" aria-label={`Диаграмма ${title}`} className="glass-panel p-4 flex flex-col min-h-0">
      <figcaption className="sr-only">
        {title} за {months.length} месяцев
      </figcaption>
      <div className="flex items-center justify-between mb-2 shrink-0">
        {showTitle && <h3 className="text-white font-medium">{title}</h3>}
        <div className="flex items-center gap-4">
          {!hideLightLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: bright }}></div>
              <span className="text-xs text-gray-400">{lightLabel || 'Уникальные'}</span>
            </div>
          )}
          {!hideDarkLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: dim }}></div>
              <span className="text-xs text-gray-400">{darkLabel || 'Уникальные по курсам'}</span>
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
          <BarChart data={chartData} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            {hatched && (
              <defs>
                <pattern
                  id={`ha-${uid}`}
                  width="6"
                  height="6"
                  patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)"
                >
                  <rect width="6" height="6" fill={dim} />
                  <line x1="0" y1="0" x2="0" y2="6" stroke={bright} strokeWidth="2" />
                </pattern>
                <pattern
                  id={`hl-${uid}`}
                  width="6"
                  height="6"
                  patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)"
                >
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
                if (!value) return '';
                const parts = value.split(' ');
                const month = parts[0] || '';
                return month.length > 3 ? month.substring(0, 3) : month;
              }}
            />
            <YAxis
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
              width={50}
              tickCount={6}
              tickFormatter={(value) => {
                if (value === 0) return '0';
                if (yAxisCompact) return `${(value / 1000).toFixed(1)}k`;
                return value.toLocaleString('ru-RU');
              }}
            />
            <Bar
              dataKey="light"
              stackId="a"
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
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
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-overlap-${entry.month}`}
                  fill={hatched && i === chartData.length - 1 ? `url(#ha-${uid})` : dim}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activeEntry && (
        <ChartTooltip x={tooltipPos.x} y={tooltipPos.y} anchor={tooltipRight ? 'right' : 'left'}>
          <ChartTooltipTitle>{activeEntry.month}</ChartTooltipTitle>
          {!hideDarkLegend && (
            <ChartTooltipRow
              label={darkLabel || 'Уникальные по курсам'}
              value={darkTooltipValue(activeEntry, darkTooltipOverlap).toLocaleString('ru-RU')}
              color={dim}
            />
          )}
          <ChartTooltipRow
            label={lightLabel || title || 'Уникальные'}
            value={(activeEntry.light ?? 0).toLocaleString('ru-RU')}
            color={bright}
          />
        </ChartTooltip>
      )}
    </figure>
  );
}
