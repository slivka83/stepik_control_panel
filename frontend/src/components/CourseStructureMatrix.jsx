import { useState, useId } from 'react';
import { createPortal } from 'react-dom';
import { STEPIK_URLS } from '../constants.jsx';
import { getRatingColor } from '../utils/format';

export const STEP_METRICS = {
  views: {
    label: 'Просмотры',
    type: 'heat',
    value: (s) => s.viewed_by,
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="w-3.5 h-3.5"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  submitted: {
    label: 'Отправлено',
    type: 'heat',
    value: (s) => s.total,
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="w-3.5 h-3.5"
      >
        <path d="M22 2L11 13" />
        <path d="M22 2l-7 20-4-9-9-4 20-7z" />
      </svg>
    ),
  },
  correct: {
    label: 'Успешных',
    type: 'heat',
    value: (s) => (s.total ? s.correct / s.total : null),
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="w-3.5 h-3.5"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
    ),
  },
  grade: {
    label: 'Оценка',
    type: 'grade',
    value: (s) => s.grade,
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="w-3.5 h-3.5"
      >
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
      </svg>
    ),
  },
  block: {
    label: 'Тип блока',
    type: 'block',
    value: (s) => s.block,
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="w-3.5 h-3.5"
      >
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
      </svg>
    ),
  },
};

const BLOCK_COLORS = {
  text: '#38bdf8',
  code: '#4ade80',
  'external-grader': '#f59e0b',
  choice: '#DB62C4',
};

const BLOCK_LABELS = {
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

function ratingColor(rating) {
  return getRatingColor(rating);
}

function stepColor(step, metric, maxValue) {
  const m = STEP_METRICS[metric];
  if (metric === 'block') {
    return BLOCK_COLORS[step.block] || '#64748b';
  }
  if (metric === 'grade') {
    const grade = step.grade;
    if (grade == null) return EMPTY_CELL;
    return ratingColor(grade);
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

function fmtNum(value) {
  return value == null ? '—' : Number(value).toLocaleString('ru-RU');
}

function metricCellText(step, metric) {
  if (metric === 'block') {
    return BLOCK_LETTERS[step.block] || (step.block ? step.block[0].toUpperCase() : '—');
  }
  if (metric === 'grade') {
    return step.grade != null ? step.grade.toFixed(2) : '—';
  }
  if (metric === 'correct') {
    return step.total ? `${Math.round((step.correct / step.total) * 100)}%` : '—';
  }
  return fmtCompact(STEP_METRICS[metric].value(step));
}

export default function CourseStructureMatrix({ modules = [], metric = 'views', loading = false }) {
  const [tooltip, setTooltip] = useState(null);
  const uid = useId();

  if (!modules.length && !loading) {
    return (
      <div className="glass-panel p-8 text-center">
        <div className="text-3xl mb-3">◆</div>
        <h3 className="text-white text-lg mb-2">Нет данных о структуре</h3>
        <p className="text-gray-400 text-sm">Синхронизируйте курс, чтобы увидеть его модули и шаги</p>
      </div>
    );
  }

  const m = STEP_METRICS[metric];
  let maxValue = 0;
  for (const mod of modules) {
    for (const lesson of mod.lessons || []) {
      for (const step of lesson.steps || []) {
        if (metric !== 'block' && metric !== 'grade') {
          const v = m.value(step) || 0;
          if (v > maxValue) maxValue = v;
        }
      }
    }
  }
  const maxSteps = Math.max(0, ...modules.flatMap((mod) => (mod.lessons || []).map((l) => (l.steps || []).length)));

  const rows = [];
  modules.forEach((mod) => {
    rows.push({ kind: 'module', module: mod });
    (mod.lessons || []).forEach((lesson) => {
      rows.push({ kind: 'lesson', module: mod, lesson });
    });
  });

  const showTooltip = (e, module, lesson, step) => {
    if (!step) return;
    setTooltip({
      x: e.clientX,
      y: e.clientY,
      module,
      lesson,
      step,
    });
  };

  return (
    <figure
      role="img"
      aria-label="Тепловая карта структуры курса"
      className="glass-panel p-4 flex flex-col flex-1 min-h-0 overflow-hidden"
    >
      <div className="flex-1 min-h-0 overflow-auto">
        <div
          className="grid gap-px"
          style={{ gridTemplateColumns: `minmax(225px, 1.35fr) repeat(${maxSteps}, minmax(30px, 1fr))` }}
        >
          {rows.map((row, ri) => {
            if (row.kind === 'module') {
              return (
                <div
                  key={`m-${ri}`}
                  className="col-span-full flex items-center px-2 py-1 rounded bg-cyber-blue/10 text-cyber-blue text-xs font-medium"
                >
                  Модуль {row.module.position}. {row.module.title}
                </div>
              );
            }
            const { lesson, module: mod } = row;
            const steps = lesson.steps || [];
            return (
              <div key={`r-${ri}`} className="contents">
                <div
                  className="flex items-center justify-start pl-2 text-left text-xs text-gray-300"
                  title={`Модуль ${mod.position}. ${mod.title} — ${lesson.title}`}
                >
                  <span className="font-mono text-gray-500 w-10 shrink-0 text-left">{mod.position}.{lesson.lesson_number}</span>
                  <span className="truncate">{lesson.title}</span>
                </div>
                {Array.from({ length: maxSteps }, (_, ci) => {
                  const step = steps[ci];
                  if (!step) {
                    return <div key={`e-${ci}`} className="rounded-sm bg-[#0d1524]" style={{ minHeight: 26 }} />;
                  }
                  return (
                    <a
                      key={`s-${step.step_id}`}
                      href={STEPIK_URLS.step(step.lesson_id, step.step_number)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center rounded-sm font-mono text-[10px] text-space-black hover:ring-1 hover:ring-white/60 transition-shadow"
                      style={{ backgroundColor: stepColor(step, metric, maxValue), minHeight: 26 }}
                      onMouseEnter={(e) => showTooltip(e, mod, lesson, step)}
                      onMouseMove={(e) => setTooltip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t))}
                      onMouseLeave={() => setTooltip(null)}
                    >
                      {metricCellText(step, metric)}
                    </a>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {tooltip &&
        createPortal(
          <div
            className="fixed z-[100] pointer-events-none px-3 py-2 rounded-lg"
            style={{
              left: tooltip.x + 12,
              top: tooltip.y - 12,
              transform: 'translate(0, -100%)',
              backgroundColor: '#162032',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              fontFamily: 'JetBrains Mono',
              maxWidth: 320,
            }}
          >
            <div className="text-white text-[13px] mb-1">
              Модуль {tooltip.module.position}. {tooltip.module.title} — {tooltip.lesson.title}
            </div>
            <div className="text-cyber-blue text-xs mb-1">
              Шаг {tooltip.step.step_number} · {BLOCK_LABELS[tooltip.step.block] || tooltip.step.block || '—'}
            </div>
              <div className="text-gray-300 text-xs">
                <div>Просмотры: {fmtNum(tooltip.step.viewed_by)}</div>
                <div>Решений: {fmtNum(tooltip.step.total)} · Успешных: {fmtNum(tooltip.step.correct)}</div>
                <div>
                  Успешность:{' '}
                  {tooltip.step.total
                    ? `${Math.round((tooltip.step.correct / tooltip.step.total) * 100)}%`
                    : '—'}
                </div>
                <div>
                  Оценка:{' '}
                  {tooltip.step.grade != null
                    ? `${tooltip.step.grade.toFixed(2)} · ${fmtNum(tooltip.step.grade_votes)} гол.`
                    : '—'}
                </div>
              </div>
          </div>,
          document.body,
        )}
    </figure>
  );
}
