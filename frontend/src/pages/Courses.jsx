import { memo, useState, useEffect, useRef, useLayoutEffect } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import { STEPIK_URLS } from '../constants.jsx';

const ROW_HEIGHT = 35;

function calcRowsPerPage(node) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  const row = node.querySelector('tbody tr');
  const rowH = row?.offsetHeight || ROW_HEIGHT;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}

const SORT_COLUMNS = {
  title: { numeric: false },
  status: { numeric: false },
  enrollment_count: { numeric: true },
  certificates_count: { numeric: true },
  comments_count: { numeric: true },
  reviews_count: { numeric: true },
  average_rating: { numeric: true },
  price: { numeric: true, nullLast: true },
  income: { numeric: true, nullLast: true },
  published_at: { numeric: false, nullLast: true },
};

const NATURAL_DIR_BY_KEY = {
  title: 'desc',
  status: 'desc',
  enrollment_count: 'asc',
  certificates_count: 'asc',
  comments_count: 'asc',
  reviews_count: 'asc',
  average_rating: 'asc',
  price: 'asc',
  income: 'asc',
  published_at: 'asc',
};

const compareCourses = (a, b, key, dir) => {
  const cfg = SORT_COLUMNS[key];
  const va = a[key];
  const vb = b[key];
  if (cfg.nullLast) {
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
  }
  let diff;
  if (cfg.numeric) {
    diff = (va ?? 0) - (vb ?? 0);
  } else {
    diff = String(va ?? '')
      .toLowerCase()
      .localeCompare(String(vb ?? '').toLowerCase(), 'ru');
  }
  return dir === 'asc' ? diff : -diff;
};

const makeSortHandler = (setter, config) => (key) => {
  setter((state) =>
    state.key === key
      ? { key, dir: state.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: config[key].numeric ? 'desc' : 'asc' },
  );
};

const SortableTh = memo(function SortableTh({ label, sortKey, sort, onSort, align = 'left', width }) {
  const active = sort.key === sortKey;
  const arrow = (
    <span className={`shrink-0 ${active ? 'text-cyber-blue' : 'invisible'}`}>{sort.dir === NATURAL_DIR_BY_KEY[sortKey] ? '↓' : '↑'}</span>
  );
  return (
    <th
      className={`pb-2 pl-1 pr-1 font-normal text-gray-400 cursor-pointer select-none hover:text-gray-300 transition-colors ${align === 'right' ? 'text-right' : 'text-left'} ${width || ''}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {align === 'right' && arrow}
        <span>{label}</span>
        {align === 'left' && arrow}
      </span>
    </th>
  );
});

function Pagination({ page, totalPages, setPage }) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-3 pl-1 pr-1 shrink-0">
      <span className="text-xs text-gray-500">
        Страница {page} из {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          ← Назад
        </button>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}

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

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

const RatingCell = memo(function RatingCell({ rating }) {
  if (!rating) return <span className="text-gray-500">—</span>;
  return (
    <span className="font-mono font-bold" style={{ color: getRatingColor(rating) }}>
      {rating.toFixed(2)}
    </span>
  );
});

const CourseRow = memo(function CourseRow({ course }) {
  const isPublished = course.status?.toLowerCase() === 'published';
  const price = course.price;
  return (
    <tr className="border-b border-gray-800">
      <td className="pl-1 pr-1 truncate">
        <a
          href={STEPIK_URLS.course(course.stepik_course_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue font-mono text-xs hover:underline truncate block"
          title={course.title}
        >
          {course.title}
        </a>
      </td>
      <td className="pr-1 text-right">
        <span
          className={`inline-block px-2 rounded text-xs font-medium ${
            isPublished ? 'bg-neon-green/20 text-neon-green' : 'bg-gray-500/20 text-gray-400'
          }`}
        >
          {isPublished ? 'Опубликован' : 'Черновик'}
        </span>
      </td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{course.enrollment_count || 0}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{course.certificates_count || 0}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{course.comments_count || 0}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{course.reviews_count || 0}</td>
      <td className="text-right pr-1">
        <RatingCell rating={course.average_rating} />
      </td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">
        {price != null ? `${price.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
      <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">
        {course.income != null ? `${course.income.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1 truncate">
        {fmtDate(course.published_at)}
      </td>
    </tr>
  );
});

export default function Courses() {
  const { data, error, refresh } = useSync();
  const courses = data.courses || [];
  const [sort, setSort] = useState({ key: 'published_at', dir: 'desc' });
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const tableRef = useRef(null);
  const prevRows = useRef(0);
  const resizeRef = useRef(null);

  useLayoutEffect(() => {
    const node = tableRef.current;
    if (!node) return;
    const calc = calcRowsPerPage(node);
    if (calc !== prevRows.current) {
      prevRows.current = calc;
      setRowsPerPage(calc);
    }
  });

  useEffect(() => {
    prevRows.current = 0;
    const node = tableRef.current;
    if (!node) return;
    const ro = new ResizeObserver(() => {
      const calc = calcRowsPerPage(node);
      if (calc !== prevRows.current) {
        prevRows.current = calc;
        setRowsPerPage(calc);
      }
    });
    resizeRef.current = ro;
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const publishedCount = courses.filter((c) => c.status?.toLowerCase() === 'published').length;
  const totalStudents = courses.reduce((s, c) => s + (c.enrollment_count || 0), 0);
  const ratings = courses.map((c) => c.average_rating).filter((r) => r > 0);
  const averageRating = ratings.length > 0 ? ratings.reduce((s, r) => s + r, 0) / ratings.length : 0;
  const totalIncome = courses.reduce((s, c) => s + (c.income || 0), 0);

  const onSort = makeSortHandler(setSort, SORT_COLUMNS);

  const sortedCourses = [...courses].sort((a, b) => compareCourses(a, b, sort.key, sort.dir));
  const totalPages = Math.max(1, Math.ceil(sortedCourses.length / rowsPerPage));
  const safePage = Math.min(page, totalPages);
  const paginatedCourses = sortedCourses.slice((safePage - 1) * rowsPerPage, safePage * rowsPerPage);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
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

      {courses.length === 0 ? (
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
        <div className="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Название" sortKey="title" sort={sort} onSort={onSort} width="w-[25%]" />
                  <SortableTh label="Статус" sortKey="status" sort={sort} onSort={onSort} align="right" width="w-[9%]" />
                  <SortableTh label="Студенты" sortKey="enrollment_count" sort={sort} onSort={onSort} align="right" width="w-[7%]" />
                  <SortableTh label="Сертификаты" sortKey="certificates_count" sort={sort} onSort={onSort} align="right" width="w-[10%]" />
                  <SortableTh label="Комментарии" sortKey="comments_count" sort={sort} onSort={onSort} align="right" width="w-[9%]" />
                  <SortableTh label="Отзывы" sortKey="reviews_count" sort={sort} onSort={onSort} align="right" width="w-[6%]" />
                  <SortableTh label="Рейтинг" sortKey="average_rating" sort={sort} onSort={onSort} align="right" width="w-[7%]" />
                  <SortableTh label="Стоимость" sortKey="price" sort={sort} onSort={onSort} align="right" width="w-[8%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sort} onSort={onSort} align="right" width="w-[10%]" />
                  <SortableTh label="Опубликован" sortKey="published_at" sort={sort} onSort={onSort} align="right" width="w-[9%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedCourses.map((course) => (
                  <CourseRow key={course.id} course={course} />
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={safePage} totalPages={totalPages} setPage={setPage} />
        </div>
      )}
    </div>
  );
}
