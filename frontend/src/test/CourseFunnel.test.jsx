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

describe('CourseFunnel', () => {
  it('shows empty state when no courses', () => {
    render(<CourseFunnel courses={[]} />);
    expect(screen.getByText('Нет курсов')).toBeInTheDocument();
    expect(screen.getByText('Подключить Stepik')).toBeInTheDocument();
  });

  it('fetches funnel for the first course', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} />);
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/courses/1/funnel'));
    expect(await screen.findByText('Воронка прохождения')).toBeInTheDocument();
  });

  it('renders stage labels and values', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} />);
    expect(await screen.findByText('Записались')).toBeInTheDocument();
    expect(screen.getByText('Модуль 1. Введение')).toBeInTheDocument();
    expect(screen.getByText('Модуль 2. Основы')).toBeInTheDocument();
    expect(screen.getByText('Получили сертификат')).toBeInTheDocument();
    expect(screen.getAllByText('100').length).toBeGreaterThanOrEqual(1);
  });

  it('renders conversion and dropoff columns', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} />);
    expect(await screen.findByText('Записались')).toBeInTheDocument();
    expect(screen.getAllByText('% от записи').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('60%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('−40 (40%)').length).toBeGreaterThanOrEqual(1);
  });

  it('refetches on course change', async () => {
    api.get.mockResolvedValue(funnelResponse);
    render(<CourseFunnel courses={courses} />);
    await screen.findByText('Записались');
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '2' } });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/courses/2/funnel'));
  });

  it('shows error banner with retry', async () => {
    api.get.mockRejectedValue(new Error('fail'));
    render(<CourseFunnel courses={courses} />);
    expect(await screen.findByText('Не удалось загрузить воронку курса')).toBeInTheDocument();
    api.get.mockResolvedValue(funnelResponse);
    fireEvent.click(screen.getByText('Повторить'));
    await waitFor(() => expect(screen.getByText('Записались')).toBeInTheDocument());
  });
});
