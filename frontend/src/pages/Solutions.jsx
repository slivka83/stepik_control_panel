import { memo, useState, useEffect, useRef, useLayoutEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import { parseMonthLabel } from '../utils/monthWindow';
import { STEPIK_URLS } from '../constants.jsx';
import api from '../api';

const ROW_HEIGHT = 35;

function calcRowsPerPage(node) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  const row = node.querySelector('tbody tr');
  const rowH = row?.offsetHeight || ROW_HEIGHT;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}
const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'hardest', label: 'Самые сложные' },
];

const MONTH_SORT_COLUMNS = {
  month: { numeric: true },
  students: { numeric: true },
  total: { numeric: true },
  correct: { numeric: true },
  wrong: { numeric: true },
  success: { numeric: true },
};

const YEARS_SORT_COLUMNS = {
  year: { numeric: true },
  students: { numeric: true },
  total: { numeric: true },
  correct: { numeric: true },
  wrong: { numeric: true },
  success: { numeric: true },
};

const COURSES_SORT_COLUMNS = {
  title: { numeric: false },
  students: { numeric: true },
  total: { numeric: true },
  correct: { numeric: true },
  wrong: { numeric: true },
  success: { numeric: true },
};

const HARDEST_SORT_COLUMNS = {
  step_id: { numeric: true },
  students: { numeric: true },
  title: { numeric: false },
  total: { numeric: true },
  correct: { numeric: true },
  wrong: { numeric: true },
  success: { numeric: true },
};

function successColor(pct) {
  if (pct < 33) return '#f43f5e';
  if (pct < 66) return '#f59e0b';
  return '#4ade80';
}

function getHardestSortValue(s, key) {
  if (key === 'step_id') return s.stepik_step_id;
  if (key === 'title') return s.course_title;
  if (key === 'success') return s.success_pct;
  return s[key];
}

function calcWrong(m) {
  return (m.total || 0) - (m.correct || 0);
}

function calcPct(m) {
  return m.total > 0 ? ((m.correct || 0) / m.total) * 100 : 0;
}

function getSortValue(m, key) {
  if (key === 'wrong') return calcWrong(m);
  if (key === 'success') return calcPct(m);
  return m[key];
}

const compareMonths = (a, b, key, dir) => {
  const cfg = MONTH_SORT_COLUMNS[key];
  let diff;
  if (key === 'month') {
    const pa = parseMonthLabel(a.month);
    const pb = parseMonthLabel(b.month);
    if (pa && pb) {
      diff = pa.year - pb.year || pa.month - pb.month;
    } else {
      diff = String(a.month)
        .toLowerCase()
        .localeCompare(String(b.month).toLowerCase(), 'ru');
    }
  } else if (cfg.numeric) {
    diff = (getSortValue(a, key) ?? 0) - (getSortValue(b, key) ?? 0);
  } else {
    diff = String(getSortValue(a, key) ?? '')
      .toLowerCase()
      .localeCompare(String(getSortValue(b, key) ?? '').toLowerCase(), 'ru');
  }
  return dir === 'asc' ? diff : -diff;
};

const compareYears = (a, b, key, dir) => {
  const diff = (getSortValue(a, key) ?? 0) - (getSortValue(b, key) ?? 0);
  return dir === 'asc' ? diff : -diff;
};

const compareCourseRows = (a, b, key, dir) => {
  const cfg = COURSES_SORT_COLUMNS[key];
  let diff;
  if (cfg.numeric) {
    diff = (getSortValue(a, key) ?? 0) - (getSortValue(b, key) ?? 0);
  } else {
    diff = String(a[key] ?? '')
      .toLowerCase()
      .localeCompare(String(b[key] ?? '').toLowerCase(), 'ru');
  }
  return dir === 'asc' ? diff : -diff;
};

const compareHardest = (a, b, key, dir) => {
  const cfg = HARDEST_SORT_COLUMNS[key];
  const va = getHardestSortValue(a, key);
  const vb = getHardestSortValue(b, key);
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

const NATURAL_DIR_BY_KEY = {
  month: 'asc',
  year: 'asc',
  step_id: 'asc',
  students: 'asc',
  total: 'asc',
  correct: 'asc',
  wrong: 'asc',
  success: 'asc',
  title: 'desc',
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

export default function Solutions() {
  const { data, error, refresh } = useSync();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
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
    setPage(1);
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
  }, [activeTab]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const submissions = data.submissions || {};
  const months = submissions.months || [];
  const byCourse = submissions.by_course || [];
  const years = submissions.years || [];

  const [hardestSteps, setHardestSteps] = useState([]);
  const [hardestLoading, setHardestLoading] = useState(false);
  const [hardestError, setHardestError] = useState(null);
  const [monthsSort, setMonthsSort] = useState({ key: 'month', dir: 'desc' });
  const [yearsSort, setYearsSort] = useState({ key: 'year', dir: 'desc' });
  const [coursesSort, setCoursesSort] = useState({ key: 'title', dir: 'asc' });
  const [hardestSort, setHardestSort] = useState({ key: 'success', dir: 'asc' });

  const onMonthsSort = makeSortHandler(setMonthsSort, MONTH_SORT_COLUMNS);
  const onYearsSort = makeSortHandler(setYearsSort, YEARS_SORT_COLUMNS);
  const onCoursesSort = makeSortHandler(setCoursesSort, COURSES_SORT_COLUMNS);
  const onHardestSort = makeSortHandler(setHardestSort, HARDEST_SORT_COLUMNS);

  useEffect(() => {
    if (activeTab !== 'hardest') return;
    setHardestLoading(true);
    setHardestError(null);
    api
      .get('/dashboard/hardest-steps?limit=200&min_submissions=1')
      .then((res) => setHardestSteps(res.data.steps || []))
      .catch(() => setHardestError('Не удалось загрузить данные'))
      .finally(() => setHardestLoading(false));
  }, [activeTab]);

  const totalSubmissions = months.reduce((s, m) => s + (m.total || 0), 0);
  const totalCorrect = months.reduce((s, m) => s + (m.correct || 0), 0);
  const totalWrong = totalSubmissions - totalCorrect;
  const avgSuccess = totalSubmissions > 0 ? Math.round((totalCorrect / totalSubmissions) * 100) : 0;

  const sortedMonths = [...months].sort((a, b) => compareMonths(a, b, monthsSort.key, monthsSort.dir));
  const monthsTotalPages = Math.ceil(sortedMonths.length / rowsPerPage);
  const paginatedMonths = sortedMonths.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  const sortedCourses = [...byCourse].sort((a, b) => compareCourseRows(a, b, coursesSort.key, coursesSort.dir));
  const coursesTotalPages = Math.ceil(sortedCourses.length / rowsPerPage);
  const paginatedCourses = sortedCourses.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  const sortedHardest = [...hardestSteps].sort((a, b) => compareHardest(a, b, hardestSort.key, hardestSort.dir));
  const hardestTotalPages = Math.ceil(sortedHardest.length / rowsPerPage);
  const paginatedHardest = sortedHardest.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  const sortedYears = [...years].sort((a, b) => compareYears(a, b, yearsSort.key, yearsSort.dir));
  const yearsTotalPages = Math.ceil(sortedYears.length / rowsPerPage);
  const paginatedYears = sortedYears.slice((page - 1) * rowsPerPage, page * rowsPerPage);

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Всего решений" value={totalSubmissions} color="white" />
        <KpiCard title="Правильных" value={totalCorrect} color="white" />
        <KpiCard title="Неправильных" value={totalWrong} color="white" />
        <KpiCard
          title="Успех"
          value={avgSuccess}
          suffix="%"
          color={avgSuccess < 33 ? 'crimson-alert' : avgSuccess < 66 ? 'amber-alert' : 'neon-green'}
        />
      </div>

      <div className="flex gap-2 border-b border-gray-700 pb-0 shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-cyber-blue text-cyber-blue'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'months' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Месяц" sortKey="month" sort={monthsSort} onSort={onMonthsSort} width="w-[22%]" />
                  <SortableTh label="Студенты" sortKey="students" sort={monthsSort} onSort={onMonthsSort} align="right" width="w-[14%]" />
                  <SortableTh label="Всего" sortKey="total" sort={monthsSort} onSort={onMonthsSort} align="right" width="w-[16%]" />
                  <SortableTh label="Правильно" sortKey="correct" sort={monthsSort} onSort={onMonthsSort} align="right" width="w-[20%]" />
                  <SortableTh label="Неверно" sortKey="wrong" sort={monthsSort} onSort={onMonthsSort} align="right" width="w-[18%]" />
                  <SortableTh label="Успех" sortKey="success" sort={monthsSort} onSort={onMonthsSort} align="right" width="w-[18%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedMonths.map((m) => {
                  const wrong = (m.total || 0) - (m.correct || 0);
                  const pct = m.total > 0 ? ((m.correct || 0) / m.total) * 100 : 0;
                  return (
                    <tr key={m.month} className="border-b border-gray-800">
                      <td className="text-white font-mono text-xs pl-1 truncate">{m.month}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(m.students || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(m.total || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                        {(m.correct || 0).toLocaleString('ru-RU')}
                      </td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{wrong.toLocaleString('ru-RU')}</td>
                      <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(pct) }}>
                        {pct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={monthsTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'years' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Год" sortKey="year" sort={yearsSort} onSort={onYearsSort} width="w-[22%]" />
                  <SortableTh label="Студенты" sortKey="students" sort={yearsSort} onSort={onYearsSort} align="right" width="w-[16%]" />
                  <SortableTh label="Всего" sortKey="total" sort={yearsSort} onSort={onYearsSort} align="right" width="w-[16%]" />
                  <SortableTh label="Правильно" sortKey="correct" sort={yearsSort} onSort={onYearsSort} align="right" width="w-[20%]" />
                  <SortableTh label="Неверно" sortKey="wrong" sort={yearsSort} onSort={onYearsSort} align="right" width="w-[18%]" />
                  <SortableTh label="Успех" sortKey="success" sort={yearsSort} onSort={onYearsSort} align="right" width="w-[18%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedYears.map((m) => {
                  const wrong = calcWrong(m);
                  const pct = calcPct(m);
                  return (
                    <tr key={m.year} className="border-b border-gray-800">
                      <td className="text-white font-mono text-xs pl-1 truncate">{m.year}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(m.students || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(m.total || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                        {(m.correct || 0).toLocaleString('ru-RU')}
                      </td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{wrong.toLocaleString('ru-RU')}</td>
                      <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(pct) }}>
                        {pct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={yearsTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'courses' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Курс" sortKey="title" sort={coursesSort} onSort={onCoursesSort} width="w-[30%]" />
                  <SortableTh label="Студенты" sortKey="students" sort={coursesSort} onSort={onCoursesSort} align="right" width="w-[14%]" />
                  <SortableTh label="Всего" sortKey="total" sort={coursesSort} onSort={onCoursesSort} align="right" width="w-[14%]" />
                  <SortableTh label="Правильно" sortKey="correct" sort={coursesSort} onSort={onCoursesSort} align="right" width="w-[18%]" />
                  <SortableTh label="Неверно" sortKey="wrong" sort={coursesSort} onSort={onCoursesSort} align="right" width="w-[16%]" />
                  <SortableTh label="Успех" sortKey="success" sort={coursesSort} onSort={onCoursesSort} align="right" width="w-[14%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedCourses.map((c) => {
                  const wrong = calcWrong(c);
                  const pct = calcPct(c);
                  return (
                    <tr key={c.course_id} className="border-b border-gray-800">
                      <td className="text-left pl-1 text-xs truncate">
                        {c.stepik_course_id ? (
                          <a
                            href={STEPIK_URLS.course(c.stepik_course_id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyber-blue font-mono text-xs hover:underline truncate block"
                          >
                            {c.title}
                          </a>
                        ) : (
                          <span className="text-white font-mono text-xs">{c.title}</span>
                        )}
                      </td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(c.students || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{(c.total || 0).toLocaleString('ru-RU')}</td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                        {(c.correct || 0).toLocaleString('ru-RU')}
                      </td>
                      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{wrong.toLocaleString('ru-RU')}</td>
                      <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(pct) }}>
                        {pct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} totalPages={coursesTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'hardest' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Step ID" sortKey="step_id" sort={hardestSort} onSort={onHardestSort} width="w-[10%]" />
                  <SortableTh label="Курс" sortKey="title" sort={hardestSort} onSort={onHardestSort} width="w-[30%]" />
                  <SortableTh label="Студенты" sortKey="students" sort={hardestSort} onSort={onHardestSort} align="right" width="w-[12%]" />
                  <SortableTh label="Всего" sortKey="total" sort={hardestSort} onSort={onHardestSort} align="right" width="w-[12%]" />
                  <SortableTh label="Правильно" sortKey="correct" sort={hardestSort} onSort={onHardestSort} align="right" width="w-[14%]" />
                  <SortableTh label="Неверно" sortKey="wrong" sort={hardestSort} onSort={onHardestSort} align="right" width="w-[14%]" />
                  <SortableTh label="Успех" sortKey="success" sort={hardestSort} onSort={onHardestSort} align="right" width="w-[14%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedHardest.map((s) => (
                  <tr key={s.stepik_step_id} className="border-b border-gray-800">
                    <td className="text-left pl-1 text-xs">
                      {s.lesson_id && s.step_number ? (
                        <a
                          href={STEPIK_URLS.step(s.lesson_id, s.step_number)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-cyber-blue font-mono text-xs hover:underline"
                        >
                          {s.stepik_step_id}
                        </a>
                      ) : (
                        <span className="text-cyber-blue font-mono text-xs">{s.stepik_step_id}</span>
                      )}
                    </td>
                    <td className="text-white font-mono text-xs pl-1 truncate">{s.course_title}</td>
                    <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                      {(s.students || 0).toLocaleString('ru-RU')}
                    </td>
                    <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                      {(s.total || 0).toLocaleString('ru-RU')}
                    </td>
                    <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                      {(s.correct || 0).toLocaleString('ru-RU')}
                    </td>
                    <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">
                      {(s.wrong || 0).toLocaleString('ru-RU')}
                    </td>
                    <td
                      className="text-right font-mono text-xs pl-1 pr-1"
                      style={{ color: successColor(s.success_pct) }}
                    >
                      {s.success_pct}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!hardestLoading && hardestError && (
              <div className="flex items-center justify-center h-full text-crimson-alert text-sm">{hardestError}</div>
            )}
            {!hardestLoading && !hardestError && hardestSteps.length === 0 && (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">Нет данных</div>
            )}
          </div>
          <Pagination page={page} totalPages={hardestTotalPages} setPage={setPage} />
        </div>
      )}
    </div>
  );
}
