import { useSync } from '../contexts/SyncContext'

export default function Courses() {
  const { data, loading } = useSync()
  const courses = data.courses

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Курсы</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="glass-panel p-5 animate-pulse">
              <div className="h-5 bg-gray-700 rounded w-3/4 mb-3"></div>
              <div className="h-4 bg-gray-700 rounded w-1/2 mb-4"></div>
              <div className="h-8 bg-gray-700 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Курсы</h1>
        <span className="text-xs text-gray-500 font-mono">{courses.length} курсов</span>
      </div>

      {courses.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <div className="text-4xl mb-4">◆</div>
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {courses.map((course) => (
            <div key={course.id} className="glass-panel glass-panel-hover p-5 transition-all duration-300">
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-white font-medium">{course.title}</h3>
                <span className={`text-xs px-2 py-1 rounded ${
                  course.status === 'Published'
                    ? 'bg-neon-green/20 text-neon-green'
                    : 'bg-gray-500/20 text-gray-400'
                }`}>
                  {course.status || 'Draft'}
                </span>
              </div>
              <div className="flex items-center gap-4 text-sm text-gray-400">
                <span className="font-mono">{course.enrollment_count || 0} студентов</span>
                <span className="font-mono">Score: {course.health_score}</span>
              </div>
              <div className="mt-4 flex gap-2">
                <a
                  href={`https://stepik.org/course/${course.stepik_course_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 text-center text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg py-2 hover:bg-cyber-blue/10 transition-colors"
                >
                  Открыть на Stepik
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
