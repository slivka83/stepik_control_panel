import { useState, useEffect } from 'react'
import axios from 'axios'

export default function Courses() {
  const [courses, setCourses] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        const res = await axios.get('/api/courses')
        setCourses(res.data.courses || [])
      } catch (err) {
        console.error('Courses fetch error:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchCourses()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyber-blue font-mono animate-pulse">Загрузка курсов...</div>
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
