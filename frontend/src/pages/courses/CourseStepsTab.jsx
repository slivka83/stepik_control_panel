import { useEffect, useState } from 'react';
import CourseStructureMatrix from '../../components/CourseStructureMatrix';
import api from '../../api';
import EmptyCourses from './EmptyCourses';

export default function CourseStepsTab({ courses, courseId, metric }) {
  const [structure, setStructure] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [retryTick, setRetryTick] = useState(0);

  useEffect(() => {
    if (!courseId) {
      setStructure(null);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    api
      .get(`/courses/${courseId}/structure`)
      .then((res) => {
        if (!cancelled) setStructure(res.data);
      })
      .catch(() => {
        if (!cancelled) setLoadError('Не удалось загрузить структуру курса');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, retryTick]);

  if (courses.length === 0) {
    return <EmptyCourses />;
  }

  const modules = structure?.modules || [];

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-3">
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

      <div className="flex flex-col flex-1 min-h-0" style={loading ? { opacity: 0.6 } : undefined}>
        <CourseStructureMatrix modules={modules} metric={metric} loading={loading} />
      </div>
    </div>
  );
}
