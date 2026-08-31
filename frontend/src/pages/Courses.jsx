import { useEffect, useState } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import CourseStructureMatrix, { STEP_METRICS } from '../components/CourseStructureMatrix';
import CourseFunnel from '../components/CourseFunnel';
import { STEPIK_URLS } from '../constants.jsx';
import { yearMonthLabel, fmtDate, getRatingColor } from '../utils/format';
import { numCell } from '../components/NumericCell';
import api from '../api';

const TABS = [
  { key: 'courses', label: 'Курсы' },
  { key: 'steps', label: 'Шаги' },
  { key: 'funnel', label: 'Воронка' },
];

const FUNNEL_VIEWS = {
  modules: {
    label: 'Модули',
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
        <polygon points="12 2 2 7 12 12 22 7 12 2" />
        <polyline points="2 17 12 22 22 17" />
        <polyline points="2 12 12 17 22 12" />
      </svg>
    ),
  },
  lessons: {
    label: 'Уроки',
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
        <line x1="8" y1="6" x2="21" y2="6" />
        <line x1="8" y1="12" x2="21" y2="12" />
        <line x1="8" y1="18" x2="21" y2="18" />
        <line x1="3" y1="6" x2="3.01" y2="6" />
        <line x1="3" y1="12" x2="3.01" y2="12" />
        <line x1="3" y1="18" x2="3.01" y2="18" />
      </svg>
    ),
  },
};

const numCellLocal = (row, key) => numCell(row[key] || 0);

const COURSE_COLUMNS = [
  {
    key: 'title',
    label: 'Название',
    width: 'w-[25%]',
    render: (c) => (
      <td className="pl-1 pr-1 truncate">
        <a
          href={STEPIK_URLS.course(c.stepik_course_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue font-mono text-xs hover:underline truncate block"
          title={c.title}
        >
          {c.title}
        </a>
      </td>
    ),
  },
  {
    key: 'status',
    label: 'Статус',
    align: 'right',
    width: 'w-[9%]',
    render: (c) => {
      const isPublished = c.status?.toLowerCase() === 'published';
      return (
        <td className="pr-1 text-right">
          <span
            className={`inline-block px-2 rounded text-xs font-medium ${
              isPublished ? 'bg-neon-green/20 text-neon-green' : 'bg-gray-500/20 text-gray-400'
            }`}
          >
            {isPublished ? 'Опубликован' : 'Черновик'}
          </span>
        </td>
      );
    },
  },
  {
    key: 'enrollment_count',
    label: 'Студенты',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'enrollment_count'),
  },
  {
    key: 'certificates_count',
    label: 'Сертификаты',
    align: 'right',
    width: 'w-[10%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'certificates_count'),
  },
  {
    key: 'comments_count',
    label: 'Комментарии',
    align: 'right',
    width: 'w-[9%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'comments_count'),
  },
  {
    key: 'reviews_count',
    label: 'Отзывы',
    align: 'right',
    width: 'w-[6%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'reviews_count'),
  },
  {
    key: 'average_rating',
    label: 'Рейтинг',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) =>
      c.average_rating ? (
        <td className="text-right pr-1">
          <span className="font-mono font-bold" style={{ color: getRatingColor(c.average_rating) }}>
            {c.average_rating.toFixed(2)}
          </span>
        </td>
      ) : (
        <td className="text-right pr-1">
          <span className="text-gray-500">—</span>
        </td>
      ),
  },
  {
    key: 'price',
    label: 'Стоимость',
    align: 'right',
    width: 'w-[8%]',
    numeric: true,
    nullLast: true,
    render: (c) => (
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">
        {c.price != null ? `${c.price.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
    ),
  },
  {
    key: 'income',
    label: 'Доход',
    align: 'right',
    width: 'w-[10%]',
    numeric: true,
    nullLast: true,
    render: (c) => (
      <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">
        {c.income != null ? `${c.income.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
    ),
  },
  {
    key: 'published_at',
    label: 'Опубликован',
    align: 'right',
    width: 'w-[9%]',
    nullLast: true,
    naturalDir: 'asc',
    render: (c) => (
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1 truncate">{fmtDate(c.published_at)}</td>
    ),
  },
];

export default function Courses() {
  const { data, error, refresh } = useSync();
  const courses = data.courses || [];
  const [activeTab, setActiveTab] = useState('courses');
  const [courseId, setCourseId] = useState(null);
  const [metric, setMetric] = useState('grade');
  const [funnelView, setFunnelView] = useState('modules');

  useEffect(() => {
    if (courseId == null && courses.length > 0) {
      setCourseId(courses[0].id);
    }
  }, [courses, courseId]);

  const publishedCount = courses.filter((c) => c.status?.toLowerCase() === 'published').length;
  const totalStudents = courses.reduce((s, c) => s + (c.enrollment_count || 0), 0);
  const ratings = courses.map((c) => c.average_rating).filter((r) => r > 0);
  const averageRating = ratings.length > 0 ? ratings.reduce((s, r) => s + r, 0) / ratings.length : 0;
  const totalIncome = courses.reduce((s, c) => s + (c.income || 0), 0);

  const selectedCourseId = courses.find((c) => c.id === courseId)?.id ?? courses[0]?.id ?? null;
  const withCourseSelect = activeTab === 'steps' || activeTab === 'funnel';

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 shrink-0">
        <KpiCard title="Всего курсов" value={courses.length} color="white" />
        <KpiCard title="Опубликовано" value={publishedCount} color="white" />
        <KpiCard title="Черновиков" value={courses.length - publishedCount} color="white" />
        <KpiCard title="Всего студентов" value={totalStudents} color="white" />
        <KpiCard title="Доход" value={totalIncome} color="white" suffix={'\u200A₽'} />
        <KpiCard
          title="Средний рейтинг"
          value={averageRating}
          ratingColor
          fractionDigits={2}
          minimumFractionDigits={2}
        />
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center justify-between gap-3 shrink-0 flex-wrap">
          <Tabs items={TABS} active={activeTab} onChange={setActiveTab} />

          {withCourseSelect && selectedCourseId && (
            <div className="flex items-center gap-3">
              {activeTab === 'steps' && (
                <div className="flex items-center gap-1" role="group" aria-label="Метрика">
                  {Object.entries(STEP_METRICS).map(([key, m]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setMetric(key)}
                      title={m.label}
                      aria-label={m.label}
                      aria-pressed={metric === key}
                      className={`p-1 rounded transition-colors ${
                        metric === key
                          ? 'text-cyber-blue'
                          : 'text-white hover:text-cyber-blue hover:drop-shadow-[0_0_4px_rgba(56,189,248,0.8)]'
                      }`}
                    >
                      {m.icon}
                    </button>
                  ))}
                </div>
              )}
              {activeTab === 'funnel' && (
                <div className="flex items-center gap-1" role="group" aria-label="Вид воронки">
                  {Object.entries(FUNNEL_VIEWS).map(([key, v]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setFunnelView(key)}
                      title={v.label}
                      aria-label={v.label}
                      aria-pressed={funnelView === key}
                      className={`p-1 rounded transition-colors ${
                        funnelView === key
                          ? 'text-cyber-blue'
                          : 'text-white hover:text-cyber-blue hover:drop-shadow-[0_0_4px_rgba(56,189,248,0.8)]'
                      }`}
                    >
                      {v.icon}
                    </button>
                  ))}
                </div>
              )}
              <select
                value={selectedCourseId}
                onChange={(e) => setCourseId(e.target.value)}
                aria-label="Курс"
                className="bg-space-gray border border-gray-700 rounded px-2 py-1 text-sm text-white w-96 max-w-[480px] truncate"
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {activeTab === 'courses' &&
          (courses.length === 0 ? (
            <div className="glass-panel p-8 text-center">
              <div className="text-3xl mb-3">◆</div>
              <h3 className="text-white text-lg mb-2">Нет курсов</h3>
              <p className="text-gray-400 text-sm">Подключите аккаунт Stepik для импорта курсов</p>
              <a
                href="/api/auth/login"
                className="inline-block mt-4 px-6 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium"
              >
                Подключить Stepik
              </a>
            </div>
          ) : (
            <DataTable
              columns={COURSE_COLUMNS}
              rows={courses}
              initialSort={{ key: 'published_at', dir: 'desc' }}
              rowKey={(c) => c.id}
            />
          ))}

        {activeTab === 'steps' && (
          <CourseStepsTab courses={courses} courseId={selectedCourseId} metric={metric} />
        )}
        {activeTab === 'funnel' && (
          <CourseFunnel courses={courses} courseId={selectedCourseId} view={funnelView} />
        )}
      </div>
    </div>
  );
}

function CourseStepsTab({ courses, courseId, metric }) {
  const [structure, setStructure] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    if (!courseId) {
      setStructure(null);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api
      .get(`/courses/${courseId}/structure`)
      .then((res) => {
        if (!cancelled) setStructure(res.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError('Не удалось загрузить структуру курса');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, retryTick]);

  if (courses.length === 0) {
    return (
      <div className="glass-panel p-8 text-center">
        <div className="text-3xl mb-3">◆</div>
        <h3 className="text-white text-lg mb-2">Нет курсов</h3>
        <p className="text-gray-400 text-sm">Подключите аккаунт Stepik для импорта курсов</p>
        <a
          href="/api/auth/login"
          className="inline-block mt-4 px-6 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium"
        >
          Подключить Stepik
        </a>
      </div>
    );
  }

  const modules = structure?.modules || [];

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-3">
      {loadError && (
        <div className="flex items-center justify-between px-4 py-3 rounded-lg bg-crimson-alert/10 border border-crimson-alert/30">
          <span className="text-crimson-alert text-sm">{loadError}</span>
          <button
            onClick={() => setRetryTick((t) => t + 1)}
            className="px-3 py-1 text-xs rounded bg-crimson-alert/20 text-crimson-alert hover:bg-crimson-alert/30"
          >
            Повторить
          </button>
        </div>
      )}

      <div className="flex flex-col flex-1 min-h-0" style={loading ? { opacity: 0.6 } : undefined}>
        <CourseStructureMatrix modules={modules} metric={metric} loading={loading} />
      </div>
    </div>
  );
}
