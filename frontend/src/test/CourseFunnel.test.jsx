import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CourseFunnel from '../components/CourseFunnel';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}));

const courses = [
  { id: '1', title: 'Python', status: 'Published' },
  { id: '2', title: 'JS', status: 'Published' },
];

const funnelResponse = {
  data: {
    course: { id: '1', stepik_course_id: 100, title: 'Python' },
    stages: [
      { key: 'enrolled', label: 'Записались', value: 100 },
      { key: 'module', module_number: 1, label: 'Модуль 1. Введение', value: 60 },
      { key: 'module', module_number: 2, label: 'Модуль 2. Основы', value: 30 },
      { key: 'certificate', label: 'Получили сертификат', value: 10 },
    ],
  },
};

const lessonsResponse = {
  data: {
    course: { id: '1', stepik_course_id: 100, title: 'Python' },
    stages: [
      { key: 'enrolled', label: 'Записались', value: 100 },
      { key: 'lesson', lesson_number: 1, label: 'Урок 1. Введение', value: 70 },
      { key: 'lesson', lesson_number: 2, label: 'Урок 2. Основы', value: 40 },
      { key: 'certificate', label: 'Получили сертификат', value: 10 },
    ],
  },
};

describe('CourseFunnel', () => {
  it('shows empty state when no courses', () => {
    render(<CourseFunnel courses={[]} />);
    expect(screen.getByText('Нет курсов')).toBeInTheDocument();
    expect(screen.getByText('Подключить Stepik')).toBeInTheDocument();
  });

  it('fetches funnel for the first course', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} courseId="1" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/courses/1/funnel', { params: { view: 'modules' } }));
    expect(await screen.findByText('Записались')).toBeInTheDocument();
  });

  it('renders stage labels and values', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} courseId="1" />);
    expect(await screen.findByText('Записались')).toBeInTheDocument();
    expect(screen.getByText('Модуль 1. Введение')).toBeInTheDocument();
    expect(screen.getByText('Модуль 2. Основы')).toBeInTheDocument();
    expect(screen.getByText('Получили сертификат')).toBeInTheDocument();
    expect(screen.getAllByText('100').length).toBeGreaterThanOrEqual(1);
  });

  it('renders funnel segments as rectangles, not slanted trapezoids', async () => {
    api.get.mockResolvedValue(funnelResponse);
    const { container } = render(<CourseFunnel courses={courses} courseId="1" />);
    await screen.findByText('Записались');
    const rects = container.querySelectorAll('svg rect');
    expect(rects.length).toBeGreaterThanOrEqual(4);
    rects.forEach((r) => {
      expect(parseFloat(r.getAttribute('height'))).toBeGreaterThan(0);
      // min-width: даже нулевые этапы не должны схлопываться в невидимую полоску 0
      expect(parseFloat(r.getAttribute('width'))).toBeGreaterThanOrEqual(4);
    });
  });

  it('renders conversion and dropoff columns', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} courseId="1" />);
    expect(await screen.findByText('Записались')).toBeInTheDocument();
    expect(screen.getAllByText('% от записи').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('60%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('−40 (40%)').length).toBeGreaterThanOrEqual(1);
  });

  it('refetches on course change', async () => {
    api.get.mockResolvedValue(funnelResponse);
    const { rerender } = render(<CourseFunnel courses={courses} courseId="1" />);
    await screen.findByText('Записались');
    rerender(<CourseFunnel courses={courses} courseId="2" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/courses/2/funnel', { params: { view: 'modules' } }));
  });

  it('fetches lesson-based funnel when view=lessons', async () => {
    api.get.mockResolvedValue(lessonsResponse);
    render(<CourseFunnel courses={courses} courseId="1" view="lessons" />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/courses/1/funnel', { params: { view: 'lessons' } }));
    expect(await screen.findByText('Урок 1. Введение')).toBeInTheDocument();
    expect(screen.getByText('Урок 2. Основы')).toBeInTheDocument();
  });

  it('refetches when view changes', async () => {
    api.get.mockResolvedValueOnce(funnelResponse).mockResolvedValueOnce(lessonsResponse);
    const { rerender } = render(<CourseFunnel courses={courses} courseId="1" view="modules" />);
    await screen.findByText('Модуль 1. Введение');
    rerender(<CourseFunnel courses={courses} courseId="1" view="lessons" />);
    await waitFor(() => expect(api.get).toHaveBeenLastCalledWith('/courses/1/funnel', { params: { view: 'lessons' } }));
    expect(await screen.findByText('Урок 1. Введение')).toBeInTheDocument();
  });

  it('shows error banner with retry', async () => {
    api.get.mockRejectedValue(new Error('fail'));
    render(<CourseFunnel courses={courses} courseId="1" />);
    expect(await screen.findByText('Не удалось загрузить воронку курса')).toBeInTheDocument();
    api.get.mockResolvedValue(funnelResponse);
    fireEvent.click(screen.getByText('Повторить'));
    await waitFor(() => expect(screen.getByText('Записались')).toBeInTheDocument());
  });

  it('does not render its own course selector or headings (moved to parent)', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} courseId="1" />);
    await screen.findByText('Записались');
    expect(screen.queryByText('Курс')).not.toBeInTheDocument();
    expect(screen.queryByText('Воронка прохождения')).not.toBeInTheDocument();
    expect(screen.queryByText('Этапы')).not.toBeInTheDocument();
  });
});
