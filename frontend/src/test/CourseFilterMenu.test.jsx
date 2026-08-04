import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TestRouter from './TestRouter';
import CourseFilterMenu from '../components/CourseFilterMenu';

const courses = [
  { id: 'c1', stepik_course_id: 101, title: 'Python' },
  { id: 'c2', stepik_course_id: 102, title: 'Алгоритмы' },
  { id: 'c3', stepik_course_id: 103, title: 'SQL' },
];

function makeSyncValue(overrides = {}) {
  return {
    syncStatus: { in_progress: false, last_sync: null },
    data: { kpi: null, cohorts: {}, revenue: { months: [] }, alerts: [], courses, financials: null },
    loading: false,
    error: null,
    refresh: vi.fn(),
    updateSyncStatus: vi.fn(),
    selectedCourseIds: null,
    isFilterActive: false,
    toggleCourse: vi.fn(),
    selectAllCourses: vi.fn(),
    ...overrides,
  };
}

function renderMenu(syncValue) {
  const onClose = vi.fn();
  const utils = render(
    <TestRouter syncValue={syncValue || makeSyncValue()}>
      <CourseFilterMenu onClose={onClose} />
    </TestRouter>,
  );
  return { onClose, ...utils };
}

describe('CourseFilterMenu', () => {
  it('renders all courses with checkboxes checked (all selected)', () => {
    renderMenu();
    for (const c of courses) {
      expect(screen.getByText(c.title)).toBeInTheDocument();
    }
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(3);
    checkboxes.forEach((cb) => expect(cb).toBeChecked());
    expect(screen.getByText('3 из 3')).toBeInTheDocument();
  });

  it('toggles course selection via checkbox', async () => {
    const user = userEvent.setup();
    const toggleCourse = vi.fn();
    renderMenu(makeSyncValue({ toggleCourse, selectedCourseIds: ['c2'], isFilterActive: true }));
    expect(screen.getByText('1 из 3')).toBeInTheDocument();

    await user.click(screen.getByText('Python'));
    expect(toggleCourse).toHaveBeenCalledWith('c1');
  });

  it('shows courses as unchecked when a subset is selected', () => {
    renderMenu(makeSyncValue({ selectedCourseIds: ['c2'], isFilterActive: true }));
    const [c1, c2, c3] = screen.getAllByRole('checkbox');
    expect(c1).not.toBeChecked();
    expect(c2).toBeChecked();
    expect(c3).not.toBeChecked();
  });

  it('select all button resets filter', async () => {
    const user = userEvent.setup();
    const selectAllCourses = vi.fn();
    renderMenu(makeSyncValue({ selectAllCourses, selectedCourseIds: ['c2'], isFilterActive: true }));
    await user.click(screen.getByText('Все'));
    expect(selectAllCourses).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape', () => {
    const { onClose } = renderMenu();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on outside click', () => {
    const { onClose } = renderMenu();
    fireEvent.mouseDown(document.body);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does not close on click inside the menu', () => {
    const { onClose } = renderMenu();
    fireEvent.mouseDown(screen.getByText('Python'));
    expect(onClose).not.toHaveBeenCalled();
  });

  it('shows placeholder when no courses', () => {
    renderMenu(makeSyncValue({ data: { courses: [] } }));
    expect(screen.getByText('Нет курсов')).toBeInTheDocument();
  });
});
