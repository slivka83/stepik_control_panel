export const CHART_COLORS = {
  cyberBlue: '#38bdf8',
  neonGreen: '#4ade80',
  gridLine: '#1e293b',
  textSecondary: '#64748b',
  panelBg: '#162032',
}

export const APP_VERSION = '0.2.0'

export const COHORT_COLORS = {
  active: { text: 'text-neon-green', bg: 'bg-neon-green', hex: '#4ade80' },
  passive: { text: 'text-cyber-blue', bg: 'bg-cyber-blue', hex: '#38bdf8' },
  fading: { text: 'text-amber-alert', bg: 'bg-amber-alert', hex: '#f59e0b' },
  sleeping: { text: 'text-gray-400', bg: 'bg-gray-400', hex: '#6b7280' },
  zombie: { text: 'text-gray-400', bg: 'bg-gray-400', hex: '#6b7280' },
}

export const COHORT_ORDER = ['active', 'passive', 'fading', 'sleeping', 'zombie']

export const COHORT_LABELS = {
  zombie: 'Зомби',
  active: 'Активные',
  passive: 'Пассивные',
  fading: 'Затухающие',
  sleeping: 'Спящие',
}

export const COHORT_DAYS = {
  zombie: 'Никогда не открывали курс',
  active: 'Активность ≤ 7 дней назад',
  passive: 'Активность 8–30 дней назад',
  fading: 'Активность 30–90 дней назад',
  sleeping: 'Активность > 90 дней назад',
}

export const STATUS_LABELS = {
  debited: 'Зачислен',
  refunded: 'Возврат',
  pending: 'Ожидание',
}

export const STATUS_COLORS = {
  debited: 'text-neon-green',
  refunded: 'text-crimson-alert',
  pending: 'text-amber-alert',
}

export const NAV_ITEMS = [
  { to: '/', label: 'Дашборд', icon: '⊞' },
  { to: '/courses', label: 'Курсы', icon: '📖︎', iconScale: 0.75 },
  { to: '/solutions', label: 'Решения', icon: '☑' },
  { to: '/financials', label: 'Финансы', icon: '$' },
  { to: '/students', label: 'Студенты', icon: '🎓︎', iconScale: 0.85 },
  { to: '/activities', label: 'Активности', icon: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
    </svg>
  )},
]

export const STEPIK_URLS = {
  course: (id) => `https://stepik.org/course/${id}`,
  courseEdit: (id) => `https://stepik.org/course/${id}/edit`,
  lessonEdit: (courseId, lessonId) => `https://stepik.org/lesson/${lessonId}/edit`,
  announcements: (courseId) => `https://stepik.org/course/${courseId}/announcements`,
  certificates: (courseId) => `https://stepik.org/course/${courseId}/certificates`,
  students: (courseId) => `https://stepik.org/course/${courseId}/students`,
}
