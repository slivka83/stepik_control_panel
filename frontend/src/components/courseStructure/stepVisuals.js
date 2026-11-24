import { formatRating, getRatingColor } from '../../utils/format';
import { STEP_METRICS } from './stepMetrics';

const BLOCK_COLORS = {
  text: '#38bdf8',
  code: '#4ade80',
  'external-grader': '#f59e0b',
  choice: '#DB62C4',
};

export const BLOCK_LABELS = {
  text: 'Текст',
  code: 'Код',
  'external-grader': 'Внешний',
  choice: 'Выбор',
};

const BLOCK_LETTERS = {
  text: 'Т',
  code: 'К',
  'external-grader': 'В',
  choice: 'Вб',
};

const EMPTY_CELL = '#111a2b';

function fmtCompact(value) {
  if (value == null) return '—';
  const v = Number(value) || 0;
  if (v >= 1000) {
    const k = (v / 1000).toFixed(1).replace(/\.0$/, '');
    return `${k}k`;
  }
  return String(v);
}

function successColor(ratio) {
  const r = Math.max(0, Math.min(1, ratio));
  const stops = [
    [0.0, 255, 0, 0],
    [0.25, 255, 120, 0],
    [0.5, 255, 210, 0],
    [0.75, 160, 230, 0],
    [1.0, 0, 255, 0],
  ];
  let i = 0;
  while (i < stops.length - 1 && stops[i + 1][0] < r) i++;
  if (i >= stops.length - 1) {
    const [, cr, cg, cb] = stops[stops.length - 1];
    return `rgb(${cr}, ${cg}, ${cb})`;
  }
  const [r0, r1, g1, b1] = stops[i];
  const [r1v, r2, g2, b2] = stops[i + 1];
  const t = (r - r0) / (r1v - r0);
  return `rgb(${Math.round(r1 + (r2 - r1) * t)}, ${Math.round(g1 + (g2 - g1) * t)}, ${Math.round(b1 + (b2 - b1) * t)})`;
}

export function stepColor(step, metric, maxValue) {
  const m = STEP_METRICS[metric];
  if (metric === 'block') {
    return BLOCK_COLORS[step.block] || '#64748b';
  }
  if (metric === 'grade') {
    if (step.grade == null) return EMPTY_CELL;
    return getRatingColor(step.grade);
  }
  if (metric === 'correct') {
    const ratio = m.value(step);
    if (ratio == null) return EMPTY_CELL;
    return successColor(ratio);
  }
  const value = m.value(step);
  if (value == null || !maxValue) return EMPTY_CELL;
  const t = Math.max(0, Math.min(1, value / maxValue));
  return `rgba(56, 189, 248, ${(0.25 + 0.7 * t).toFixed(3)})`;
}

export function fmtNum(value) {
  return value == null ? '—' : Number(value).toLocaleString('ru-RU');
}

export function metricCellText(step, metric) {
  if (metric === 'block') {
    return BLOCK_LETTERS[step.block] || (step.block ? step.block[0].toUpperCase() : '—');
  }
  if (metric === 'grade') {
    return formatRating(step.grade);
  }
  if (metric === 'correct') {
    return step.total ? `${Math.round((step.correct / step.total) * 100)}%` : '—';
  }
  return fmtCompact(STEP_METRICS[metric].value(step));
}
