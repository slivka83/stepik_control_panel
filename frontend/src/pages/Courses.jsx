import { useEffect, useState } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import CourseFunnel from '../components/CourseFunnel';
import CourseStepsTab from './courses/CourseStepsTab';
import EmptyCourses from './courses/EmptyCourses';
import { COURSE_COLUMNS } from './courses/columns';
import { STEP_METRICS } from '../components/CourseStructureMatrix';

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

function MetricToggle({ items, active, onChange, ariaLabel }) {
  return (
    <div className="flex items-center gap-1" role="group" aria-label={ariaLabel}>
      {Object.entries(items).map(([key, item]) => (
        <button
          key={key}
          type="button"
          onClick={() => onChange(key)}
          title={item.label}
          aria-label={item.label}
          aria-pressed={active === key}
          className={`p-1 rounded transition-colors ${
            active === key
              ? 'text-cyber-blue'
              : 'text-white hover:text-cyber-blue hover:drop-shadow-[0_0_4px_rgba(56,189,248,0.8)]'
          }`}
        >
          {item.icon}
        </button>
      ))}
    </div>
  );
}

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
                <MetricToggle items={STEP_METRICS} active={metric} onChange={setMetric} ariaLabel="Метрика" />
              )}
              {activeTab === 'funnel' && (
                <MetricToggle
                  items={FUNNEL_VIEWS}
                  active={funnelView}
                  onChange={setFunnelView}
                  ariaLabel="Вид воронки"
                />
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
            <EmptyCourses />
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
