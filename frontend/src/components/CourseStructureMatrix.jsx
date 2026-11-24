import { useState } from 'react';
import { STEPIK_URLS } from '../constants.jsx';
import StepTooltip from './courseStructure/StepTooltip';
import { STEP_METRICS } from './courseStructure/stepMetrics';
import { metricCellText, stepColor } from './courseStructure/stepVisuals';

export { STEP_METRICS };

export default function CourseStructureMatrix({ modules = [], metric = 'views', loading = false }) {
  const [tooltip, setTooltip] = useState(null);

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
  const maxSteps = Math.max(
    1,
    ...modules.flatMap((mod) => (mod.lessons || []).map((l) => (l.steps || []).length)),
  );

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
                  <span className="font-mono text-gray-500 w-10 shrink-0 text-left">
                    {mod.position}.{lesson.lesson_number}
                  </span>
                  <span className="truncate">{lesson.title}</span>
                </div>
                {Array.from({ length: maxSteps }, (_, ci) => {
                  const step = steps[ci];
                  if (!step) {
                    return <div key={`e-${ci}`} className="rounded-sm bg-[#0d1524]" style={{ minHeight: 26 }} />;
                  }
                  const hasLink = step.lesson_id != null && step.step_number != null;
                  const cellClass =
                    'flex items-center justify-center rounded-sm font-mono text-[10px] text-space-black transition-shadow';
                  const cellStyle = { backgroundColor: stepColor(step, metric, maxValue), minHeight: 26 };
                  const cellHandlers = {
                    onMouseEnter: (e) => showTooltip(e, mod, lesson, step),
                    onMouseMove: (e) => setTooltip((t) => (t ? { ...t, x: e.clientX, y: e.clientY } : t)),
                    onMouseLeave: () => setTooltip(null),
                  };
                  return hasLink ? (
                    <a
                      key={`s-${step.step_id}`}
                      href={STEPIK_URLS.step(step.lesson_id, step.step_number)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`${cellClass} hover:ring-1 hover:ring-white/60`}
                      style={cellStyle}
                      {...cellHandlers}
                    >
                      {metricCellText(step, metric)}
                    </a>
                  ) : (
                    <div key={`s-${step.step_id}`} className={cellClass} style={cellStyle} {...cellHandlers}>
                      {metricCellText(step, metric)}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      <StepTooltip tooltip={tooltip} />
    </figure>
  );
}
