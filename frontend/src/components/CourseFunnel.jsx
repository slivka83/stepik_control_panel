import { useEffect, useState } from 'react';
import { FunnelChart, Funnel, Cell, LabelList, Tooltip, ResponsiveContainer } from 'recharts';
import api from '../api';

const COLOR_BRIGHT = '#38bdf8';
const COLOR_DIM = '#1a6a9e';
const COLOR_CERT = '#4ade80';

function mixHex(a, b, t) {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const r = Math.round(((pa >> 16) & 0xff) + (((pb >> 16) & 0xff) - ((pa >> 16) & 0xff)) * t);
  const g = Math.round(((pa >> 8) & 0xff) + (((pb >> 8) & 0xff) - ((pa >> 8) & 0xff)) * t);
  const bl = Math.round((pa & 0xff) + ((pb & 0xff) - (pa & 0xff)) * t);
  return `#${((r << 16) | (g << 8) | bl).toString(16).padStart(6, '0')}`;
}

const fmtNum = (v) => Number(v || 0).toLocaleString('ru-RU');
const fmtPct = (v) => `${v.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%`;

function buildRows(stages) {
  const list = stages || [];
  const first = list[0]?.value || 0;
  const nonCertCount = list.filter((s) => s.key !== 'certificate').length;
  let nonCertIdx = -1;
  return list.map((s, i) => {
    const value = s.value || 0;
    const prev = i > 0 ? list[i - 1].value || 0 : value;
    const dropoff = prev - value;
    let color;
    if (s.key === 'certificate') {
      color = COLOR_CERT;
    } else {
      nonCertIdx += 1;
      color = mixHex(COLOR_BRIGHT, COLOR_DIM, nonCertCount > 1 ? nonCertIdx / (nonCertCount - 1) : 0);
    }
    return {
      ...s,
      value,
      color,
      pctOfFirst: first ? (value / first) * 100 : 0,
      dropoff,
      dropoffPct: prev ? (dropoff / prev) * 100 : 0,
    };
  });
}

function FunnelTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0].payload;
  return (
    <div
      className="px-3 py-2 rounded-lg pointer-events-none"
      style={{
        backgroundColor: '#162032',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        fontFamily: 'JetBrains Mono',
        maxWidth: 320,
      }}
    >
      <div className="text-white text-[13px] mb-1">{row.label}</div>
      <div className="text-cyber-blue text-xs mb-1">Студентов: {fmtNum(row.value)}</div>
      <div className="text-gray-300 text-xs">
        <div>% от записавшихся: {fmtPct(row.pctOfFirst)}</div>
        <div>
          Отсев с этапа:{' '}
          {row.key !== 'enrolled' && row.dropoff > 0 ? `−${fmtNum(row.dropoff)} (${fmtPct(row.dropoffPct)})` : '—'}
        </div>
      </div>
    </div>
  );
}

export default function CourseFunnel({ courses = [] }) {
  const [courseId, setCourseId] = useState(courses[0]?.id || null);
  const [funnel, setFunnel] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    if (!courseId) {
      setFunnel(null);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api
      .get(`/courses/${courseId}/funnel`)
      .then((res) => {
        if (!cancelled) setFunnel(res.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError('Не удалось загрузить воронку курса');
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
  const rows = buildRows(funnel?.stages || []);

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

      <div className="flex flex-1 min-h-0 flex-col lg:flex-row gap-3" style={loading ? { opacity: 0.6 } : undefined}>
        <figure
          role="img"
          aria-label="Воронка прохождения курса"
          className="glass-panel p-4 flex flex-col min-h-0 flex-1"
        >
          <figcaption className="sr-only">Воронка прохождения курса {selectedCourse.title}</figcaption>
          <h3 className="text-white font-medium mb-2 shrink-0">Воронка прохождения</h3>
          <div className="flex-1 min-h-0">
            {rows.length === 0 ? (
              <div className="flex-1 h-full flex items-center justify-center text-gray-500 text-sm">
                Нет данных о прохождении
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <FunnelChart margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <Tooltip content={FunnelTooltip} />
                  <Funnel
                    dataKey="value"
                    data={rows}
                    nameKey="label"
                    isAnimationActive={false}
                    label={{
                      dataKey: 'value',
                      fill: '#ffffff',
                      fontSize: 11,
                      fontFamily: 'JetBrains Mono',
                      formatter: (v) => fmtNum(v),
                    }}
                  >
                    {rows.map((row, i) => (
                      <Cell
                        key={`${row.key}-${row.module_number ?? i}`}
                        fill={row.color}
                        stroke="#0b0f19"
                        strokeWidth={2}
                      />
                    ))}
                  </Funnel>
                </FunnelChart>
              </ResponsiveContainer>
            )}
          </div>
        </figure>

        <div className="glass-panel p-4 lg:w-[400px] shrink-0 overflow-auto min-h-0">
          <h3 className="text-white font-medium mb-2 shrink-0">Этапы</h3>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-500">
                <th className="pb-2 font-medium">Этап</th>
                <th className="pb-2 font-medium text-right">Студентов</th>
                <th className="pb-2 font-medium text-right">% от записи</th>
                <th className="pb-2 font-medium text-right">Отсев</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={`${row.key}-${row.module_number ?? i}`} className="border-t border-gray-800">
                  <td className="py-1.5 pr-2 truncate max-w-[180px]" title={row.label}>
                    <span
                      className="inline-block w-2 h-2 rounded-sm mr-2 align-middle"
                      style={{ backgroundColor: row.color }}
                    ></span>
                    {row.label}
                  </td>
                  <td className="py-1.5 text-right font-mono text-gray-300 pl-2">{fmtNum(row.value)}</td>
                  <td className="py-1.5 text-right font-mono text-gray-400 pl-2">{fmtPct(row.pctOfFirst)}</td>
                  <td className="py-1.5 text-right font-mono pl-2">
                    {i > 0 && row.dropoff > 0 ? (
                      <span className="text-crimson-alert">
                        −{fmtNum(row.dropoff)} ({fmtPct(row.dropoffPct)})
                      </span>
                    ) : (
                      <span className="text-gray-500">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
