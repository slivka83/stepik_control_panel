import { createPortal } from 'react-dom';
import { formatRating } from '../../utils/format';
import { BLOCK_LABELS, fmtNum } from './stepVisuals';

export default function StepTooltip({ tooltip }) {
  if (!tooltip) return null;
  return createPortal(
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
        Модуль {tooltip.module.position}. {tooltip.module.title || '—'} — {tooltip.lesson.title || '—'}
      </div>
      <div className="text-cyber-blue text-xs mb-1">
        Шаг {tooltip.step.step_number ?? tooltip.step.step_id} ·{' '}
        {BLOCK_LABELS[tooltip.step.block] || tooltip.step.block || '—'}
      </div>
      <div className="text-gray-300 text-xs">
        <div>Просмотры: {fmtNum(tooltip.step.viewed_by)}</div>
        <div>Решений: {fmtNum(tooltip.step.total)} · Успешных: {fmtNum(tooltip.step.correct)}</div>
        <div>
          Успешность:{' '}
          {tooltip.step.total ? `${Math.round((tooltip.step.correct / tooltip.step.total) * 100)}%` : '—'}
        </div>
        <div>
          Оценка:{' '}
          {tooltip.step.grade != null
            ? `${formatRating(tooltip.step.grade)} · ${fmtNum(tooltip.step.grade_votes)} гол.`
            : '—'}
        </div>
      </div>
    </div>,
    document.body,
  );
}
