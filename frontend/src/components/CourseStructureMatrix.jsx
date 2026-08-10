import { useState, useId } from 'react';
import { createPortal } from 'react-dom';
import { STEPIK_URLS } from '../constants.jsx';

export const STEP_METRICS = {
  views: { label: 'Просмотры', type: 'heat', value: (s) => s.viewed_by },
  submitted: { label: 'Отправлено', type: 'heat', value: (s) => s.total },
  correct: { label: 'Успешных', type: 'heat', value: (s) => s.correct },
  grade: { label: 'Оценка', type: 'grade', value: (s) => s.correct_ratio },
  block: { label: 'Тип блока', type: 'block', value: (s) => s.block },
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

const EMPTY_CELL = '#111a2b';

function ratingColor(rating) {
  const r = Math.max(1, Math.min(5, rating));
  const stops = [
    [1.0, 239, 68, 68],
    [2.0, 249, 115, 22],
    [3.0, 234, 179, 8],
    [4.0, 132, 204, 22],
    [4.5, 100, 214, 81],
    [4.9, 74, 222, 128],
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

function stepColor(step, metric, maxValue) {
  const m = STEP_METRICS[metric];
  if (metric === 'block') {
    return BLOCK_COLORS[step.block] || '#64748b';
  }
  if (metric === 'grade') {
    const ratio = step.correct_ratio;
    if (ratio == null) return EMPTY_CELL;
    return ratingColor(1 + Math.max(0, Math.min(1, ratio)) * 4);
  }
  const value = m.value(step);
  if (!value || !maxValue) return EMPTY_CELL;
  const t = Math.max(0, Math.min(1, value / maxValue));
  const alpha = 0.25 + 0.7 * t;
  return `rgba(56, 189, 248, ${alpha.toFixed(3)})`;
}

function fmtNum(value) {
  return value == null ? '—' : Number(value).toLocaleString('ru-RU');
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

  const legend = (() => {
    if (metric === 'block') {
      const used = new Set();
      modules.forEach((mod) =>
        (mod.lessons || []).forEach((l) => (l.steps || []).forEach((s) => s.block && used.add(s.block))),
      );
      return [...used].map((b) => ({ color: BLOCK_COLORS[b] || '#64748b', label: BLOCK_LABELS[b] || b }));
    }
    if (metric === 'grade') {
      return [
        { color: ratingColor(1), label: '0%' },
        { color: ratingColor(3), label: '50%' },
        { color: ratingColor(5), label: '100%' },
      ];
    }
    return [
      { color: 'rgba(56, 189, 248, 0.25)', label: 'мало' },
      { color: 'rgba(56, 189, 248, 0.95)', label: 'много' },
    ];
  })();

  return (
    <figure
      role="img"
      aria-label="Тепловая карта структуры курса"
      className="glass-panel p-4 flex flex-col min-h-0 overflow-hidden"
    >
      <div className="flex items-center justify-between mb-3 shrink-0">
        <h3 className="text-white font-medium">{m.label}</h3>
        <div className="flex items-center gap-4">
          {legend.map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: item.color }}></div>
              <span className="text-xs text-gray-400">{item.label}</span>
            </div>
          ))}
          {metric === 'block' && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: EMPTY_CELL }}></div>
              <span className="text-xs text-gray-500">нет данных</span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <div
          className="grid gap-px"
          style={{ gridTemplateColumns: `minmax(150px, 0.9fr) repeat(${maxSteps}, minmax(30px, 1fr))` }}
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
                  className="flex items-center justify-end pr-2 text-right text-xs text-gray-300 truncate"
                  title={`Модуль ${mod.position}. ${mod.title} — ${lesson.title}`}
                >
                  <span className="font-mono text-gray-500 mr-1">{mod.position}.{lesson.lesson_number}</span>
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
                      {step.step_number}
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
                Оценка:{' '}
                {tooltip.step.correct_ratio != null
                  ? `${(tooltip.step.correct_ratio * 100).toFixed(1)}%`
                  : '—'}
              </div>
            </div>
          </div>,
          document.body,
        )}
    </figure>
  );
}
