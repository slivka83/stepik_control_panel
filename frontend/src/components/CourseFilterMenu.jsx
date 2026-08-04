import { useEffect, useRef } from 'react';
import { useSync } from '../contexts/SyncContext';

export default function CourseFilterMenu({ onClose, triggerRef }) {
  const { data, selectedCourseIds, toggleCourse, selectAllCourses, selectNoneCourses } = useSync();
  const ref = useRef(null);
  const masterRef = useRef(null);
  const courses = data.courses || [];
  const isAll = !selectedCourseIds;
  const selectedCount = isAll ? courses.length : selectedCourseIds.length;
  const isPartial = !isAll && selectedCount > 0;

  useEffect(() => {
    const onMouseDown = (e) => {
      const inMenu = ref.current && ref.current.contains(e.target);
      const inTrigger = triggerRef && triggerRef.current && triggerRef.current.contains(e.target);
      if (!inMenu && !inTrigger) onClose();
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose, triggerRef]);

  useEffect(() => {
    if (masterRef.current) masterRef.current.indeterminate = isPartial;
  }, [isPartial]);

  const label = (c) => c.title || `#${c.stepik_course_id}`;

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="Фильтр по курсам"
      className="fixed left-[76px] bottom-3 z-50 w-80 glass-panel rounded-xl border border-cyber-blue/20 shadow-2xl flex flex-col overflow-hidden"
      style={{ maxHeight: 'min(70vh, 480px)' }}
    >
      <div className="flex items-center gap-2.5 px-3 py-2 border-b border-space-gray/60">
        <input
          ref={masterRef}
          type="checkbox"
          checked={isAll}
          onChange={(e) => (e.target.checked ? selectAllCourses() : selectNoneCourses())}
          aria-label="Выбрать все курсы"
          disabled={courses.length === 0}
          className="accent-cyber-blue w-4 h-4 shrink-0"
        />
        <span className="text-xs uppercase text-gray-300 font-medium flex-1">Курсы</span>
        <span className="text-xs text-cyber-blue font-mono">
          {selectedCount} из {courses.length}
        </span>
      </div>
      <div className="overflow-y-auto min-h-0 flex-1 py-1">
        {courses.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-500 text-center">Нет курсов</div>
        ) : (
          courses.map((c) => {
            const checked = isAll || selectedCourseIds.includes(c.id);
            return (
              <label
                key={c.id}
                className="flex items-center gap-2.5 px-3 py-1.5 rounded hover:bg-cyber-blue/10 cursor-pointer select-none"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCourse(c.id)}
                  className="accent-cyber-blue w-4 h-4 shrink-0"
                />
                <span className="text-sm text-gray-200 truncate">{label(c)}</span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}
