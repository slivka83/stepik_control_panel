import { useEffect, useState } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import CourseStructureMatrix, { STEP_METRICS } from '../components/CourseStructureMatrix';
import { STEPIK_URLS } from '../constants.jsx';
import { fmtDate } from '../utils/format';
import api from '../api';

const TABS = [
  { key: 'courses', label: 'Курсы' },
  { key: 'steps', label: 'Шаги' },
];

function getRatingColor(rating) {
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

const numCell = (row, key) => <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{row[key] || 0}</td>;

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
    render: (c) => numCell(c, 'enrollment_count'),
  },
  {
    key: 'certificates_count',
    label: 'Сертификаты',
    align: 'right',
    width: 'w-[10%]',
    numeric: true,
    render: (c) => numCell(c, 'certificates_count'),
  },
  {
    key: 'comments_count',
    label: 'Комментарии',
    align: 'right',
    width: 'w-[9%]',
    numeric: true,
    render: (c) => numCell(c, 'comments_count'),
  },
  {
    key: 'reviews_count',
    label: 'Отзывы',
    align: 'right',
    width: 'w-[6%]',
    numeric: true,
    render: (c) => numCell(c, 'reviews_count'),
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

  const publishedCount = courses.filter((c) => c.status?.toLowerCase() === 'published').length;
  const totalStudents = courses.reduce((s, c) => s + (c.enrollment_count || 0), 0);
  const ratings = courses.map((c) => c.average_rating).filter((r) => r > 0);
  const averageRating = ratings.length > 0 ? ratings.reduce((s, r) => s + r, 0) / ratings.length : 0;
  const totalIncome = courses.reduce((s, c) => s + (c.income || 0), 0);

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

      <Tabs items={TABS} active={activeTab} onChange={setActiveTab} />

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
            panelClassName="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden"
          />
        ))}

      {activeTab === 'steps' && <CourseStepsTab courses={courses} />}
    </div>
  );
}

function CourseStepsTab({ courses }) {
  const [courseId, setCourseId] = useState(courses[0]?.id || null);
  const [metric, setMetric] = useState('grade');
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

  const selectedCourse = courses.find((c) => c.id === courseId) || courses[0];
  const modules = structure?.modules || [];

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-3">
      <div className="flex items-center gap-4 shrink-0 flex-wrap">
        <label className="flex items-center gap-2 text-sm text-gray-300">
          <span className="text-gray-500">Курс</span>
          <select
            value={selectedCourse.id}
            onChange={(e) => setCourseId(e.target.value)}
            className="bg-space-gray border border-gray-700 rounded px-2 py-1 text-sm text-white"
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>

        <div className="flex items-center gap-2">
          {Object.entries(STEP_METRICS).map(([key, m]) => (
            <button
              key={key}
              onClick={() => setMetric(key)}
              className={`px-3 py-1 text-xs font-medium rounded-lg border transition-colors ${
                metric === key
                  ? 'bg-cyber-blue/20 text-cyber-blue border-cyber-blue/40'
                  : 'bg-transparent text-gray-400 border-gray-700 hover:text-gray-300'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

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

      <div className="flex-1 min-h-0" style={loading ? { opacity: 0.6 } : undefined}>
        <CourseStructureMatrix modules={modules} metric={metric} loading={loading} />
      </div>
    </div>
  );
}
