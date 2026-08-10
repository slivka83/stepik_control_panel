import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import CourseStructureMatrix, { STEP_METRICS } from '../components/CourseStructureMatrix';

const modules = [
  {
    position: 1,
    title: 'Введение',
    lessons: [
      {
        lesson_id: 10,
        lesson_number: 1,
        title: 'Линейная регрессия',
        steps: [
          { step_id: 500, lesson_id: 10, step_number: 1, block: 'text', viewed_by: 100, total: 50, correct: 40, correct_ratio: 0.8 },
          { step_id: 501, lesson_id: 10, step_number: 2, block: 'code', viewed_by: 200, total: 60, correct: 30, correct_ratio: 0.5 },
        ],
      },
      {
        lesson_id: 11,
        lesson_number: 2,
        title: 'Логистика',
        steps: [{ step_id: 502, lesson_id: 11, step_number: 1, block: 'external-grader', viewed_by: null, total: 0, correct: 0, correct_ratio: null }],
      },
    ],
  },
  {
    position: 2,
    title: 'Практика',
    lessons: [{ lesson_id: 12, lesson_number: 3, title: 'Проект', steps: [] }],
  },
];

describe('CourseStructureMatrix', () => {
  it('renders module headers and lesson rows', () => {
    render(<CourseStructureMatrix modules={modules} metric="views" />);
    expect(screen.getByText('Модуль 1. Введение')).toBeInTheDocument();
    expect(screen.getByText('Модуль 2. Практика')).toBeInTheDocument();
    expect(screen.getByText('Линейная регрессия')).toBeInTheDocument();
    expect(screen.getByText('Логистика')).toBeInTheDocument();
  });

  it('renders empty state when no modules', () => {
    render(<CourseStructureMatrix modules={[]} metric="views" />);
    expect(screen.getByText('Нет данных о структуре')).toBeInTheDocument();
  });

  it('renders step cells with step numbers', () => {
    render(<CourseStructureMatrix modules={modules} metric="views" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link).toBeTruthy();
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.textContent).toBe('1');
  });

  it('shows deep link to stepik', () => {
    render(<CourseStructureMatrix modules={modules} metric="views" stepikCourseId={68260} />);
    const links = screen.getAllByRole('link');
    expect(links.some((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1')).toBe(true);
  });

  it('shows tooltip with step metrics on hover', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    const cell = screen.getByText('2').closest('a');
    fireEvent.mouseEnter(cell, { clientX: 10, clientY: 10 });
    expect(screen.getByText(/Шаг 2/)).toBeInTheDocument();
    expect(screen.getByText(/Просмотры: 200/)).toBeInTheDocument();
    expect(screen.getByText(/Решений: 60 · Успешных: 30/)).toBeInTheDocument();
    fireEvent.mouseLeave(cell);
    expect(screen.queryByText(/Просмотры: 200/)).not.toBeInTheDocument();
  });

  it('exposes STEP_METRICS with all five metrics', () => {
    expect(Object.keys(STEP_METRICS)).toEqual(['views', 'submitted', 'correct', 'grade', 'block']);
  });

  it('renders heat legend for sequential metric', () => {
    render(<CourseStructureMatrix modules={modules} metric="submitted" />);
    expect(screen.getByText('мало')).toBeInTheDocument();
    expect(screen.getByText('много')).toBeInTheDocument();
  });

  it('renders grade gradient legend', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    expect(screen.getByText('0%')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
  });

  it('renders block legend for block metric', () => {
    render(<CourseStructureMatrix modules={modules} metric="block" />);
    expect(screen.getByText('Текст')).toBeInTheDocument();
    expect(screen.getByText('Код')).toBeInTheDocument();
    expect(screen.getByText('Внешний')).toBeInTheDocument();
  });

  it('renders empty placeholder cells for shorter lessons', () => {
    const { container } = render(<CourseStructureMatrix modules={modules} metric="views" />);
    expect(container.querySelectorAll('a').length).toBe(3);
  });
});
