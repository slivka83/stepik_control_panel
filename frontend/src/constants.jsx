export const CHART_COLORS = {
  cyberBlue: '#38bdf8',
  neonGreen: '#4ade80',
  gridLine: '#1e293b',
  textSecondary: '#64748b',
  panelBg: '#162032',
};


export const COHORT_COLORS = {
  active: { text: 'text-neon-green', bg: 'bg-neon-green', hex: '#4ade80' },
  passive: { text: 'text-cyber-blue', bg: 'bg-cyber-blue', hex: '#38bdf8' },
  fading: { text: 'text-amber-alert', bg: 'bg-amber-alert', hex: '#f59e0b' },
  sleeping: { text: 'text-gray-400', bg: 'bg-gray-400', hex: '#6b7280' },
  zombie: { text: 'text-gray-400', bg: 'bg-gray-400', hex: '#6b7280' },
};

export const COHORT_ORDER = ['active', 'passive', 'fading', 'sleeping', 'zombie'];

export const COHORT_LABELS = {
  zombie: 'Зомби',
  active: 'Активные',
  passive: 'Пассивные',
  fading: 'Затухающие',
  sleeping: 'Спящие',
};

export const COHORT_DAYS = {
  zombie: 'Спящие, которые открыли курс в первые дни после записи и пропали',
  active: 'Активность ≤ 7 дней назад',
  passive: 'Активность 8–30 дней назад',
  fading: 'Активность 30–90 дней назад',
  sleeping: 'Активность > 90 дней назад',
};


export const NAV_GROUPS = [
  {
    items: [
      { to: '/', label: 'Дашборд', icon: '⊞' },
      {
        to: '/activities',
        label: 'Активности',
        icon: (
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
        ),
      },
      { to: '/courses', label: 'Курсы', icon: '📖︎', iconScale: 0.75 },
    ],
  },
  {
    items: [
      { to: '/financials', label: 'Финансы', icon: '$' },
      { to: '/solutions', label: 'Решения', icon: '☑' },
      { to: '/comments', label: 'Комментарии', icon: '🗨', iconScale: 0.85 },
      {
        to: '/certificates',
        label: 'Сертификаты',
        icon: (
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="8" r="6" />
            <path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11" />
          </svg>
        ),
      },
      {
        to: '/reviews',
        label: 'Отзывы',
        icon: (
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        ),
      },
    ],
  },
  {
    items: [
      {
        to: '/students',
        label: 'Студенты',
        icon: (
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        ),
      },
    ],
  },
];

export const STEPIK_URLS = {
  course: (id) => `https://stepik.org/course/${id}`,
  step: (lessonId, stepId) => `https://stepik.org/lesson/${lessonId}/step/${stepId}`,
  courseEdit: (id) => `https://stepik.org/course/${id}/edit`,
  lessonEdit: (courseId, lessonId) => `https://stepik.org/lesson/${lessonId}/edit`,
  announcements: (courseId) => `https://stepik.org/course/${courseId}/announcements`,
  certificates: (courseId) => `https://stepik.org/course/${courseId}/certificates`,
  students: (courseId) => `https://stepik.org/course/${courseId}/students`,
  comment: (lessonId, commentId) => `https://stepik.org/lesson/${lessonId}?discussion=${commentId}`,
};
