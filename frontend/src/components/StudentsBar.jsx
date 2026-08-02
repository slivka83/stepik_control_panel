import { COHORT_COLORS, COHORT_LABELS, COHORT_DAYS, COHORT_ORDER, CHART_COLORS } from '../constants.jsx';
import { useState, useRef } from 'react';
import { createPortal } from 'react-dom';

export default function StudentsBar({ data = {} }) {
  const allEntries = Object.entries(data).filter(([, v]) => v > 0);
  const orderIndex = (key) => {
    const idx = COHORT_ORDER.indexOf(key);
    return idx >= 0 ? idx : 99;
  };
  const entries = allEntries.sort(([a], [b]) => orderIndex(a) - orderIndex(b));
  const total = entries.reduce((s, [, v]) => s + v, 0);
  const [hovered, setHovered] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [hidden, setHidden] = useState(new Set());

  if (!total) {
    return (
      <div className="glass-panel p-4 relative z-20" style={{ height: '7.25rem' }}>
        <div className="flex items-end justify-between mb-5">
          <h3 className="text-white font-medium">Студенты</h3>
        </div>
        <div className="flex items-center justify-center h-5 text-gray-500 text-xs">Нет данных для отображения</div>
      </div>
    );
  }

  const visibleEntries = entries.filter(([k]) => !hidden.has(k));
  const visibleTotal = visibleEntries.reduce((s, [, v]) => s + v, 0);

  const toggleKey = (key) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const hoveredEntry = hovered !== null ? entries.find(([k]) => k === hovered) : null;
  const hoveredPct = hoveredEntry ? ((hoveredEntry[1] / (visibleTotal || 1)) * 100).toFixed(1) : 0;

  const sleepingHex = COHORT_COLORS.sleeping?.hex || '#6b7280';

  return (
    <div className="glass-panel p-4 pb-5 relative z-20" style={{ height: '7.25rem' }}>
      <div className="flex items-end justify-between mb-5">
        <h3 className="text-white font-medium">Студенты</h3>
        <span className="text-gray-500 text-xs font-mono">{visibleTotal.toLocaleString('ru-RU')} студентов</span>
      </div>
      <div
        className="relative"
        onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
        onMouseLeave={() => setHovered(null)}
      >
        <div className="flex gap-1 h-5 rounded-lg overflow-hidden">
          {visibleEntries.map(([key, value]) => {
            const pct = (value / (visibleTotal || 1)) * 100;
            const isZombie = key === 'zombie';
            const color = COHORT_COLORS[key]?.hex || '#64748b';
            return (
              <div
                key={key}
                className="h-full transition-all duration-300 cursor-pointer"
                style={{
                  width: `${pct}%`,
                  backgroundColor: isZombie ? 'transparent' : color,
                  border: isZombie ? `1px solid ${sleepingHex}` : 'none',
                  boxSizing: 'border-box',
                  minWidth: pct > 0 ? '4px' : '0',
                  outline: hovered === key ? '2px solid #ffffff' : 'none',
                  outlineOffset: '-1px',
                }}
                onMouseEnter={() => setHovered(key)}
              />
            );
          })}
        </div>
      </div>
      {hoveredEntry &&
        createPortal(
          <div
            className="fixed z-[100] whitespace-nowrap px-3 py-2 rounded-lg pointer-events-none"
            style={{
              left: `${mousePos.x}px`,
              top: `${mousePos.y - 12}px`,
              transform: 'translate(-50%, -100%)',
              backgroundColor: CHART_COLORS.panelBg,
              border: '1px solid rgba(56, 189, 248, 0.3)',
              fontFamily: 'JetBrains Mono',
            }}
          >
            <div className="text-white text-xs font-medium mb-1">{COHORT_LABELS[hoveredEntry[0]]}</div>
            <div className="text-gray-300 text-xs">
              {hoveredEntry[1].toLocaleString('ru-RU')} чел. <span className="text-gray-500">({hoveredPct}%)</span>
            </div>
            <div className="text-gray-500 text-[10px] mt-0.5">{COHORT_DAYS[hoveredEntry[0]]}</div>
          </div>,
          document.body,
        )}
      <div className="flex gap-3 mt-1.5">
        {entries.map(([key, value]) => {
          const isZombie = key === 'zombie';
          const color = COHORT_COLORS[key]?.hex || '#64748b';
          const pct = ((value / (visibleTotal || 1)) * 100).toFixed(0);
          const isHidden = hidden.has(key);
          return (
            <div
              key={key}
              className="flex items-center gap-1.5 cursor-pointer select-none transition-opacity"
              style={{ opacity: isHidden ? 0.35 : 1 }}
              onClick={() => toggleKey(key)}
            >
              <div
                className="w-2 h-2 rounded-full"
                style={
                  isZombie
                    ? { backgroundColor: 'transparent', border: `1px solid ${sleepingHex}` }
                    : { backgroundColor: color }
                }
              />
              <span className="text-gray-500 text-[10px]">{COHORT_LABELS[key]}</span>
              <span className="text-gray-400 text-[10px] font-mono">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
