import { useState } from 'react';
import { createPortal } from 'react-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell } from 'recharts';
import { CHART_COLORS } from '../constants.jsx';

function BarShape({ activeKey, onBarEnter, onBarLeave, xKey, ...props }) {
  const { x, y, width, height, fill, fillOpacity, payload } = props;
  if (!height || height <= 0) return null;
  const key = payload?.[xKey];
  const isActive = payload && activeKey != null && key != null && activeKey === key;
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
      onMouseEnter={(e) => payload && onBarEnter(payload, e.clientX, e.clientY)}
      onMouseMove={(e) => onBarEnter(payload, e.clientX, e.clientY)}
      onMouseLeave={onBarLeave}
      style={{ pointerEvents: 'all' }}
    />
  );
}

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
  const [active, setActive] = useState(null);
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

  const handleBarEnter = (payload, cx, cy) => {
    setActive(payload);
    setTooltipPos({ x: cx, y: cy });
  };

  const shapeProps = {
    activeKey: active?.[xKey],
    onBarEnter: handleBarEnter,
    onBarLeave: () => setActive(null),
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
                shape={(props) => <BarShape {...shapeProps} {...props} />}
              >
                {rows.map((entry) => (
                  <Cell key={`${bar.dataKey}-${entry[xKey]}`} fill={bar.color} fillOpacity={bar.fillOpacity} />
                ))}
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {active &&
        cfg.tooltip &&
        createPortal(
          <div
            className="fixed z-[100] whitespace-nowrap px-3 py-2 rounded-lg pointer-events-none"
            style={{
              left: `${tooltipPos.x + 12}px`,
              top: `${tooltipPos.y - 12}px`,
              transform: 'translateY(-100%)',
              backgroundColor: CHART_COLORS.panelBg,
              border: '1px solid rgba(56, 189, 248, 0.3)',
              fontFamily: 'JetBrains Mono',
            }}
          >
            <div style={{ color: '#ffffff', fontSize: 13, marginBottom: 4 }}>
              {periodLabel ? periodLabel(active) : active[xKey]}
            </div>
            {cfg.tooltip(active).map((line, i) => (
              <div key={i} style={{ color: line.color || '#ffffff', fontSize: 12, opacity: line.dim ? 0.6 : 1 }}>
                {line.label}: {fmtValue(line.value, format)}
              </div>
            ))}
          </div>,
          document.body,
        )}
    </figure>
  );
}
