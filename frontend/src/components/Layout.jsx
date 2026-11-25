import { useEffect, useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useSync } from '../contexts/SyncContext';
import { NAV_GROUPS } from '../constants.jsx';
import CourseFilterMenu from './CourseFilterMenu';
import api from '../api';

function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h} ч ${m} мин`;
  if (m > 0) return `${m} мин ${sec} с`;
  return `${sec} с`;
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function Sidebar() {
  const { user, loading, authError, login, logout } = useAuth();
  const { syncStatus, updateSyncStatus, data, isFilterActive, selectedCourseIds, refresh } =
    useSync();
  const [syncing, setSyncing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [syncError, setSyncError] = useState(null);
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [filterOpen, setFilterOpen] = useState(false);
  const filterBtnRef = useRef(null);
  const startRef = useRef(null);
  const seenLastSyncRef = useRef(null);
  const progressSampleRef = useRef({ pct: null, at: null, rate: null });
  const [now, setNow] = useState(Date.now());

  const isSyncing = syncing || syncStatus.in_progress;
  const displayProgress = syncing ? progress : syncStatus.progress || 0;
  const lastError = !isSyncing ? syncError || syncStatus.last_error : null;

  useEffect(() => {
    if (!isSyncing) {
      startRef.current = null;
      progressSampleRef.current = { pct: null, at: null, rate: null };
      return;
    }
    if (startRef.current === null) startRef.current = Date.now();
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [isSyncing]);

  // ETA from OBSERVED progress change, not from page-open time: opening the
  // panel in the middle of a long sync must not claim "~0 s left".
  useEffect(() => {
    if (!isSyncing) return;
    const pct = displayProgress;
    const at = Date.now();
    const prev = progressSampleRef.current;
    if (prev.pct == null || pct < prev.pct) {
      progressSampleRef.current = { pct, at, rate: null };
      return;
    }
    const dp = pct - prev.pct;
    const dt = (at - prev.at) / 1000;
    if (dp > 0 && dt > 0) {
      const instant = dp / dt;
      progressSampleRef.current = {
        pct,
        at,
        rate: prev.rate ? prev.rate * 0.6 + instant * 0.4 : instant,
      };
    } else {
      progressSampleRef.current = { ...prev, pct, at };
    }
  }, [displayProgress, isSyncing]);

  useEffect(() => {
    if (cooldownLeft <= 0) return undefined;
    const t = setInterval(() => setCooldownLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldownLeft]);

  // The backend reports the remaining cooldown on every status poll; reflect
  // it immediately after a page reload instead of letting the button look ready.
  useEffect(() => {
    const remaining = syncStatus.cooldown_remaining_seconds || 0;
    if (!isSyncing && remaining > 0) setCooldownLeft(remaining);
  }, [syncStatus.cooldown_remaining_seconds, isSyncing]);

  // A status poll may have failed locally after the sync actually succeeded.
  // A new last_sync without a backend error is the source of truth.
  useEffect(() => {
    const last = syncStatus.last_sync;
    if (last && last !== seenLastSyncRef.current) {
      seenLastSyncRef.current = last;
      if (!syncStatus.last_error) setSyncError(null);
    }
  }, [syncStatus.last_sync, syncStatus.last_error]);

  const buildSyncTooltip = () => {
    if (lastError) return `Синхронизация не удалась:\n${lastError}`;
    if (cooldownLeft > 0) return `Синхронизация будет доступна через ${cooldownLeft} с`;
    if (!isSyncing) {
      if (syncStatus.last_sync) return `Обновить\nПоследняя синхронизация: ${formatDateTime(syncStatus.last_sync)}`;
      return 'Обновить';
    }
    const elapsed = startRef.current ? (now - startRef.current) / 1000 : 0;
    const pct = displayProgress;
    const rate = progressSampleRef.current.rate;
    const remaining = rate > 0 && pct < 100 ? (100 - pct) / rate : pct >= 100 ? 0 : null;
    return [
      `Завершено: ${Math.round(pct)}%`,
      `Наблюдаем: ${formatDuration(elapsed)}`,
      `Осталось: ${remaining !== null ? `~${formatDuration(remaining)}` : '…'}`,
    ].join('\n');
  };

  const handleSync = async () => {
    setSyncing(true);
    setProgress(0);
    setSyncError(null);

    let trigger;
    try {
      ({ data: trigger } = await api.post('/sync'));
    } catch (err) {
      // Only a failed launch is a launch error; status polling below is
      // retried separately.
      setSyncError(err.response?.data?.detail || 'Не удалось запустить синхронизацию');
      setSyncing(false);
      setProgress(0);
      return;
    }

    if (trigger.status === 'cooldown') {
      setCooldownLeft(trigger.cooldown_remaining_seconds || 60);
      setSyncing(false);
      return;
    }
    if (trigger.status === 'already_in_progress') {
      setSyncing(false);
      return;
    }

    let statusFailures = 0;
    let finished = false;
    try {
      while (true) {
        await new Promise((r) => setTimeout(r, 1000));
        let status;
        try {
          ({ data: status } = await api.get('/sync/status'));
          statusFailures = 0;
        } catch {
          // One flaky poll must not paint a successfully started sync as
          // failed forever; give the backend a few chances.
          statusFailures += 1;
          if (statusFailures >= 5) break;
          continue;
        }
        updateSyncStatus?.(status);
        setProgress(status.progress || 0);
        if (!status.in_progress) {
          finished = true;
          break;
        }
      }
      if (finished) {
        // Не ждём 30-секундного опроса контекста: сразу подтягиваем свежие KPI.
        refresh();
      } else {
        setSyncError('Не удалось получить статус синхронизации');
      }
    } finally {
      setSyncing(false);
      setProgress(0);
    }
  };

  return (
    <aside className="fixed top-0 left-0 h-screen w-16 bg-space-gray border-r border-cyber-blue/10 flex flex-col items-center pt-4 pb-6 z-40">
      <nav role="navigation" aria-label="Основная навигация" className="flex flex-col w-full">
        {NAV_GROUPS.map((group, groupIndex) => (
          <div key={groupIndex}>
            {groupIndex > 0 && <div className="w-full h-px bg-cyber-blue/10" aria-hidden="true" />}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                aria-label={item.label}
                title={item.label}
                className={({ isActive }) =>
                  `flex items-center justify-center gap-3 h-[50px] px-3 transition-all duration-200 border-l-2 ${
                    isActive
                      ? 'text-cyber-blue border-l-cyber-blue bg-cyber-blue/10'
                      : 'text-gray-400 border-l-transparent hover:text-gray-200 hover:bg-white/5'
                  }`
                }
              >
                <span
                  className="text-lg leading-none flex items-center"
                  aria-hidden="true"
                  style={
                    item.iconScale ? { transform: `scale(${item.iconScale})`, display: 'inline-block' } : undefined
                  }
                >
                  {item.icon}
                </span>
                <span className="hidden text-sm font-medium">{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="mt-auto px-2 w-full flex flex-col items-center gap-2">
        {loading ? null : user ? (
          <>
            <div className="relative">
              <button
                ref={filterBtnRef}
                onClick={() => setFilterOpen((o) => !o)}
                title={
                  isFilterActive
                    ? `Фильтр по курсам\nВыбрано: ${selectedCourseIds.length} из ${(data.courses || []).length}`
                    : 'Фильтр по курсам'
                }
                aria-haspopup="menu"
                aria-expanded={filterOpen}
                className={`w-10 h-10 flex items-center justify-center border rounded-lg transition-colors ${
                  isFilterActive
                    ? 'text-cyber-blue border-cyber-blue/40 bg-cyber-blue/10'
                    : 'text-gray-400 border-cyber-blue/30 hover:text-cyber-blue hover:bg-cyber-blue/10'
                }`}
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="w-5 h-5"
                  aria-hidden="true"
                >
                  <path d="M4 5h16l-6 7v5l-4 2v-7z" />
                </svg>
              </button>
              {filterOpen && <CourseFilterMenu onClose={() => setFilterOpen(false)} triggerRef={filterBtnRef} />}
            </div>
            <button
              onClick={handleSync}
              title={buildSyncTooltip()}
              className="relative w-10 h-10 flex items-center justify-center border border-cyber-blue/30 rounded-lg overflow-hidden text-lg group"
              disabled={isSyncing || cooldownLeft > 0}
            >
              {isSyncing && (
                <span
                  className="absolute bottom-0 left-0 w-full bg-cyber-blue/25"
                  style={{ height: `${displayProgress}%`, transition: 'height 1.5s ease-out' }}
                />
              )}
              {lastError && (
                <span className="absolute bottom-0 left-0 w-full bg-crimson-alert/30" style={{ height: '100%' }} />
              )}
              <span
                className={`relative z-10 inline-block text-cyber-blue transition-colors duration-300 ${isSyncing ? 'animate-spin' : 'group-hover:text-white'}`}
              >
                ↻
              </span>
            </button>
            <button
              onClick={logout}
              title="Выйти"
              className="w-10 h-10 flex items-center justify-center text-crimson-alert border border-crimson-alert/30 rounded-lg hover:bg-crimson-alert/10 transition-colors text-lg"
            >
              ⏻
            </button>
          </>
        ) : (
          <button
            onClick={login}
            title="Войти"
            className="w-10 h-10 flex items-center justify-center text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors text-lg"
          >
            →
          </button>
        )}
      </div>
    </aside>
  );
}

function AuthErrorBanner() {
  const { user, authError } = useAuth();
  if (user || !authError) return null;
  return (
    <div className="mb-3 px-4 py-3 rounded-lg bg-crimson-alert/10 border border-crimson-alert/30 text-crimson-alert text-sm">
      {authError}
    </div>
  );
}

export default function Layout({ children }) {
  return (
    <div className="h-screen overflow-hidden bg-space-black">
      <Sidebar />
      <main
        role="main"
        aria-label="Основной контент"
        className="ml-16 h-full min-h-0 overflow-y-auto p-4 flex flex-col"
      >
        <AuthErrorBanner />
        {children}
      </main>
    </div>
  );
}
