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
  sleeping: { text: 'text-crimson-alert', bg: 'bg-crimson-alert', hex: '#f43f5e' },
}

export const COHORT_LABELS = {
  active: 'Активные',
  passive: 'Пассивные',
  fading: 'Затухающие',
  sleeping: 'Спящие',
}

export const COHORT_DAYS = {
  active: '≤ 7 дней',
  passive: '8–30 дней',
  fading: '30–90 дней',
  sleeping: '> 90 дней',
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
  { to: '/', label: 'Дашборд', icon: '◈' },
  { to: '/courses', label: 'Курсы', icon: '◆' },
  { to: '/financials', label: 'Финансы', icon: '◉' },
  { to: '/cohorts', label: 'Когорты', icon: '◎' },
]

export const STEPIK_URLS = {
  course: (id) => `https://stepik.org/course/${id}`,
  courseEdit: (id) => `https://stepik.org/course/${id}/edit`,
  lessonEdit: (courseId, lessonId) => `https://stepik.org/lesson/${lessonId}/edit`,
  announcements: (courseId) => `https://stepik.org/course/${courseId}/announcements`,
  certificates: (courseId) => `https://stepik.org/course/${courseId}/certificates`,
  students: (courseId) => `https://stepik.org/course/${courseId}/students`,
}
