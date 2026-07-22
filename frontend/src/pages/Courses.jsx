import { useSync } from '../contexts/SyncContext'
import ErrorBanner from '../components/ErrorBanner'
import { STEPIK_URLS } from '../constants'
import { pluralize } from '../utils/pluralize'

export default function Courses() {
  const { data, loading, error, refresh } = useSync()
  const courses = data.courses

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-white">Курсы</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={`skeleton-course-${i}`} className="glass-panel p-4 animate-pulse">
              <div className="h-4 bg-gray-700 rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-gray-700 rounded w-1/2 mb-3"></div>
              <div className="h-6 bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Курсы</h1>
        <span className="text-xs text-gray-500 font-mono">
          {courses.length} {pluralize(courses.length, ['курс', 'курса', 'курсов'])}
        </span>
      </div>

      {error && <ErrorBanner message={error} onRetry={refresh} />}

      {courses.length === 0 ? (
        <div className="glass-panel p-8 text-center">
          <div className="text-3xl mb-3">◆</div>
          <h3 className="text-white text-lg mb-2">Нет курсов</h3>
          <p className="text-gray-400 text-sm">
            Подключите аккаунт Stepik для импорта курсов
          </p>
          <a
            href="/api/auth/login"
            className="inline-block mt-4 px-6 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium"
          >
            Подключить Stepik
          </a>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {courses.map((course) => {
            const isPublished = course.status?.toLowerCase() === 'published'
            return (
              <div key={course.id} className="glass-panel glass-panel-hover p-4 transition-all duration-300">
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-white font-medium text-sm">{course.title}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    isPublished
                      ? 'bg-neon-green/20 text-neon-green'
                      : 'bg-gray-500/20 text-gray-400'
                  }`}>
                    {course.status || 'Draft'}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span className="font-mono">
                    {course.enrollment_count || 0} {pluralize(course.enrollment_count || 0, ['студент', 'студента', 'студентов'])}
                  </span>
                  <span className="font-mono">Score: {course.health_score}</span>
                </div>
                <div className="mt-3 flex gap-2">
                  <a
                    href={STEPIK_URLS.course(course.stepik_course_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 text-center text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg py-2 hover:bg-cyber-blue/10 transition-colors"
                  >
                    Открыть на Stepik
                  </a>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
