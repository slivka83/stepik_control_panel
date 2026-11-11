import { createPortal } from 'react-dom';
import { CHART_COLORS } from '../constants.jsx';

/**
 * Столбик диаграммы: подсвечивается белой обводкой, когда на него наведён
 * курсор (activeKey совпал), и сообщает координаты курсора для подсказки.
 *
 * xKey — колонка строки, по которой сравниваются столбики («month» и т.п.).
 */
export function ChartBarShape({ activeKey, onEnter, onLeave, xKey = 'month', ...props }) {
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
      onMouseEnter={(e) => payload && onEnter(key, e.clientX, e.clientY)}
      onMouseMove={(e) => onEnter(key, e.clientX, e.clientY)}
      onMouseLeave={onLeave}
      style={{ pointerEvents: 'all' }}
    />
  );
}

/**
 * Всплывающая подсказка у курсора (рисуется поверх страницы, не обрезается
 * контейнером графика). anchor="right" — справа-сверху от курсора (иначе
 * слева-сверху).
 */
export function ChartTooltip({ x, y, anchor = 'right', children }) {
  const right = anchor === 'right';
  return createPortal(
    <div
      className="fixed z-[100] whitespace-nowrap px-3 py-2 rounded-lg pointer-events-none"
      style={{
        left: right ? `${x + 12}px` : `${x - 12}px`,
        top: right ? `${y - 12}px` : `${y}px`,
        transform: right ? 'translate(0, -100%)' : 'translate(-100%, -100%)',
        backgroundColor: CHART_COLORS.panelBg,
        border: '1px solid rgba(56, 189, 248, 0.3)',
        fontFamily: 'JetBrains Mono',
      }}
    >
      {children}
    </div>,
    document.body,
  );
}

/** Заголовок подсказки: белый, чуть крупнее строк. */
export function ChartTooltipTitle({ children }) {
  return <div style={{ color: '#ffffff', fontSize: 13, marginBottom: 4 }}>{children}</div>;
}

/** Строка подсказки: «Подпись: значение» цветом серии. */
export function ChartTooltipRow({ label, value, color = '#ffffff', dim = false }) {
  return (
    <div style={{ color, fontSize: 12, opacity: dim ? 0.6 : 1 }}>
      {label}: {value}
    </div>
  );
}
