import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import StudentsBar from '../components/StudentsBar';

const COHORT_COLORS = {
  Active: '#4ade80',
  Passive: '#38bdf8',
  Fading: '#f59e0b',
  Sleeping: '#f43f5e',
  Zombie: '#a855f7',
};

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function Students() {
  const { data, error, refresh } = useSync();
  const cohorts = data.cohorts;
  const students = data.students?.students || [];

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <StudentsBar data={cohorts} />

      <div className="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="overflow-auto flex-1 min-h-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-space-gray/50">
                <th className="pb-2 pr-2 font-medium">Имя</th>
                <th className="pb-2 pr-2 font-medium">Статус</th>
                <th className="pb-2 pr-2 font-medium text-right">Курсы</th>
                <th className="pb-2 pr-2 font-medium text-right">Сертификаты</th>
                <th className="pb-2 pr-2 font-medium text-right">Решения</th>
                <th className="pb-2 pr-2 font-medium text-right">Комментарии</th>
                <th className="pb-2 font-medium text-right">Активность</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr
                  key={s.student_id}
                  className="border-b border-space-gray/30 hover:bg-space-gray/40 transition-colors"
                >
                  <td className="py-2 pr-2 max-w-[220px]">
                    <a
                      href={s.profile_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyber-blue text-sm font-medium hover:underline truncate block"
                      title={s.name || `Студент ${s.student_id}`}
                    >
                      {s.name || `Студент ${s.student_id}`}
                    </a>
                  </td>
                  <td className="py-2 pr-2">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                      style={{
                        backgroundColor: `${COHORT_COLORS[s.cohort_status] || '#6b7280'}20`,
                        color: COHORT_COLORS[s.cohort_status] || '#6b7280',
                      }}
                    >
                      {s.cohort_status}
                    </span>
                  </td>
                  <td className="py-2 pr-2 text-right font-mono text-xs text-gray-300">{s.courses_count}</td>
                  <td className="py-2 pr-2 text-right font-mono text-xs text-gray-300">{s.certificates}</td>
                  <td className="py-2 pr-2 text-right font-mono text-xs text-gray-300">
                    {s.submissions_count > 0
                      ? `${s.submissions_count} (${Math.round(((s.submissions_successful || 0) / s.submissions_count) * 100)}%)`
                      : '0'}
                  </td>
                  <td className="py-2 pr-2 text-right font-mono text-xs text-gray-300">{s.comments_count}</td>
                  <td className="py-2 text-right text-xs text-gray-400 whitespace-nowrap">
                    {formatDate(s.last_activity)}
                  </td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500 text-sm">
                    Нет данных о студентах
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
