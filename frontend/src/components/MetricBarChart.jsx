import { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';
import { CHART_COLORS } from '../constants.jsx';
import { ChartBarShape, ChartTooltip, ChartTooltipRow, ChartTooltipTitle } from './chartKit';

function moneyTick(value) {
  if (value === 0) return '0';
  if (value >= 1000) return `${(value / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  return value.toLocaleString('ru-RU');
}

function countTick(value) {
  if (value === 0) return '0';
  return value.toLocaleString('ru-RU');
}

function ratingTick(value) {
  return Number.isFinite(value) ? value.toFixed(1) : String(value ?? '');
}

function fmtValue(value, format) {
  if (format === 'money') return `${(value ?? 0).toLocaleString('ru-RU')} ₽`;
  if (format === 'rating') return (value ?? 0).toFixed(2);
  return (value ?? 0).toLocaleString('ru-RU');
}

const Y_TICKS = {
  money: moneyTick,
  rating: ratingTick,
  count: countTick,
};

export default function MetricBarChart({ rows = [], xKey = 'month', metric, metrics = {}, xTick, periodLabel }) {
  const cfg = metrics[metric] || {};
  const [activeKey, setActiveKey] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  if (!rows.length) {
    return (
      <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
        <div className="flex-1 flex items-center justify-center text-gray-500">Нет данных для отображения</div>
      </div>
    );
  }

  const format = cfg.format || 'count';
  const bars = cfg.bars || [];
  const yTick = Y_TICKS[format] || countTick;

  const handleBarEnter = (key, cx, cy) => {
    setActiveKey(key);
    setTooltipPos({ x: cx, y: cy });
  };

  const activeEntry = activeKey != null ? rows.find((r) => r[xKey] === activeKey) : null;

  const shapeProps = {
    activeKey,
    onEnter: handleBarEnter,
    onLeave: () => setActiveKey(null),
    xKey,
  };

  return (
    <figure
      role="img"
      aria-label={`Диаграмма ${cfg.label || ''}`}
      className="glass-panel p-4 flex flex-col flex-1 min-h-0"
    >
      <figcaption className="sr-only">
        {cfg.label || ''} за {rows.length} периодов
      </figcaption>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 15, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
            <XAxis
              dataKey={xKey}
              stroke={CHART_COLORS.textSecondary}
              fontSize={11}
              fontFamily="JetBrains Mono"
              interval={0}
              tickMargin={8}
              tickFormatter={xTick}
            />
            <YAxis
              stroke={CHART_COLORS.textSecondary}
              fontSize={12}
              fontFamily="JetBrains Mono"
              width={50}
              tickCount={6}
              tickFormatter={yTick}
            />
            {bars.map((bar, i) => (
              <Bar
                key={bar.dataKey}
                dataKey={bar.dataKey}
                stackId="a"
                radius={i === bars.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                shape={(props) => <ChartBarShape {...shapeProps} {...props} />}
              >
                {rows.map((entry) => (
                  <Cell key={`${bar.dataKey}-${entry[xKey]}`} fill={bar.color} fillOpacity={bar.fillOpacity} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {activeEntry && cfg.tooltip && (
        <ChartTooltip x={tooltipPos.x} y={tooltipPos.y} anchor="right">
          <ChartTooltipTitle>{periodLabel ? periodLabel(activeEntry) : activeEntry[xKey]}</ChartTooltipTitle>
          {cfg.tooltip(activeEntry).map((line, i) => (
            <ChartTooltipRow
              key={i}
              label={line.label}
              value={fmtValue(line.value, format)}
              color={line.color}
              dim={line.dim}
            />
          ))}
        </ChartTooltip>
      )}
    </figure>
  );
}
