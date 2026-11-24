import { useState, useId } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';
import { CHART_COLORS } from '../constants.jsx';
import { buildMonthWindow, makeMonthsTick } from '../utils/monthWindow.js';
import { ChartBarShape, ChartTooltip, ChartTooltipRow, ChartTooltipTitle } from './chartKit';

const COLOR_BRIGHT = '#38bdf8';
const COLOR_DIM = '#1a6a9e';

function mixColors(a, b) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const r = Math.round((((pa >> 16) & 0xff) + ((pb >> 16) & 0xff)) / 2);
  const g = Math.round((((pa >> 8) & 0xff) + ((pb >> 8) & 0xff)) / 2);
  const b2 = Math.round(((pa & 0xff) + (pb & 0xff)) / 2);
  return `#${((r << 16) | (g << 8) | b2).toString(16).padStart(6, '0')}`;
}

export default function SubmissionsChart({
  data = {},
  title,
  primaryColor,
  secondaryColor,
  hideCorrectLegend,
  hideTotalLegend,
  tooltipRight,
}) {
  const [activeMonth, setActiveMonth] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const uid = useId();

  const months = buildMonthWindow(data.months || []);
  const monthTick = makeMonthsTick(months);

  if (!months.length) {
    return (
      <div className="glass-panel p-4 flex flex-col min-h-0">
        <h3 className="text-white font-medium mb-3">{title || 'Решения'}</h3>
        <div className="flex-1 flex items-center justify-center text-gray-500">Нет данных для отображения</div>
      </div>
    );
  }

  const bright = primaryColor || COLOR_BRIGHT;
  const dim = secondaryColor || COLOR_DIM;
  const publishedColor = mixColors(bright, dim);
  const hasPublished = (data.months || []).some((m) => 'published' in m);

  const chartData = months.map((d) => {
    const correct = d.correct || 0;
    const published = d.published ?? 0;
    // Сегмент «Опубликованные» не может быть больше «Правильных» в этом
    // месяце (публикация и решение считаются по разным датам). Полное
    // значение остаётся в publishedTotal для тултипа/KPI.
    const publishedSegment = Math.min(published, correct);
    return {
      ...d,
      published: publishedSegment,
      correct: Math.max(correct - publishedSegment, 0),
      correctTotal: correct,
      publishedTotal: published,
      wrong: Math.max((d.total || 0) - correct, 0),
    };
  });

  const maxVal = Math.max(...chartData.map((d) => Math.max(d.total || 0, d.correct || 0)));
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
    <figure
      role="img"
      aria-label={title ? `Диаграмма ${title}` : 'Диаграмма решений по месяцам'}
      className="glass-panel p-4 flex flex-col min-h-0"
    >
      <figcaption className="sr-only">
        {title || 'Решения'} за {months.length} месяцев
      </figcaption>
      <div className="flex items-center justify-between mb-2 shrink-0">
        <h3 className="text-white font-medium">{title || 'Решения'}</h3>
        <div className="flex items-center gap-4">
          {!hideCorrectLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: bright }}></div>
              <span className="text-xs text-gray-400">Правильные</span>
            </div>
          )}
          {hasPublished && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: publishedColor }}></div>
              <span className="text-xs text-gray-400">Опубликованные</span>
            </div>
          )}
          {!hideTotalLegend && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: dim }}></div>
              <span className="text-xs text-gray-400">Не завершён</span>
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
            <defs>
              <pattern
                id={`hc-${uid}`}
                width="6"
                height="6"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <rect width="6" height="6" fill={bright} />
                <line x1="0" y1="0" x2="0" y2="6" stroke={dim} strokeWidth="2" />
              </pattern>
              <pattern
                id={`hw-${uid}`}
                width="6"
                height="6"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <rect width="6" height="6" fill={dim} fillOpacity="0.5" />
                <line x1="0" y1="0" x2="0" y2="6" stroke={bright} strokeWidth="2" strokeOpacity="0.4" />
              </pattern>
              {hasPublished && (
                <pattern
                  id={`hp-${uid}`}
                  width="6"
                  height="6"
                  patternUnits="userSpaceOnUse"
                  patternTransform="rotate(45)"
                >
                  <rect width="6" height="6" fill={publishedColor} />
                  <line x1="0" y1="0" x2="0" y2="6" stroke={bright} strokeWidth="2" />
                </pattern>
              )}
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
              tickFormatter={(value) => {
                if (value === 0) return '0';
                if (yAxisCompact) return `${(value / 1000).toFixed(1)}k`;
                return value.toLocaleString('ru-RU');
              }}
            />
            <Bar
              dataKey="correct"
              stackId="a"
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-correct-${entry.month}`}
                  fill={i === chartData.length - 1 ? `url(#hc-${uid})` : bright}
                />
              ))}
            </Bar>
            {hasPublished && (
              <Bar
                dataKey="published"
                stackId="a"
                shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
              >
                {chartData.map((entry, i) => (
                  <Cell
                    key={`cell-published-${entry.month}`}
                    fill={i === chartData.length - 1 ? `url(#hp-${uid})` : publishedColor}
                  />
                ))}
              </Bar>
            )}
            <Bar
              dataKey="wrong"
              stackId="a"
              radius={[4, 4, 0, 0]}
              shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
            >
              {chartData.map((entry, i) => (
                <Cell
                  key={`cell-wrong-${entry.month}`}
                  fill={i === chartData.length - 1 ? `url(#hw-${uid})` : dim}
                  fillOpacity={i === chartData.length - 1 ? 1 : 0.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activeEntry && (
        <ChartTooltip x={tooltipPos.x} y={tooltipPos.y} anchor={tooltipRight ? 'right' : 'left'}>
          <ChartTooltipTitle>{activeEntry.month}</ChartTooltipTitle>
          <ChartTooltipRow
            label={title || 'Правильные'}
            value={(activeEntry.correctTotal ?? activeEntry.correct ?? 0).toLocaleString('ru-RU')}
            color={bright}
          />
          {hasPublished && activeEntry.publishedTotal != null && (
            <ChartTooltipRow
              label="Опубликованные"
              value={(activeEntry.publishedTotal ?? 0).toLocaleString('ru-RU')}
              color={publishedColor}
            />
          )}
          {!hideTotalLegend && (
            <ChartTooltipRow
              label={title ? 'Комментариев' : 'Всего'}
              value={(activeEntry.total ?? 0).toLocaleString('ru-RU')}
              color={dim}
            />
          )}
        </ChartTooltip>
      )}
    </figure>
  );
}
