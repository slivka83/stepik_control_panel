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
          { step_id: 500, lesson_id: 10, step_number: 1, block: 'text', viewed_by: 100, total: 50, correct: 40, correct_ratio: 0.8, grade: 4.86, grade_votes: 14 },
          { step_id: 501, lesson_id: 10, step_number: 2, block: 'code', viewed_by: 200, total: 60, correct: 30, correct_ratio: 0.5, grade: 3.5, grade_votes: 4 },
        ],
      },
      {
        lesson_id: 11,
        lesson_number: 2,
        title: 'Логистика',
        steps: [{ step_id: 502, lesson_id: 11, step_number: 1, block: 'external-grader', viewed_by: null, total: 0, correct: 0, correct_ratio: null, grade: null, grade_votes: 0 }],
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

  it('renders step cells with metric values', () => {
    render(<CourseStructureMatrix modules={modules} metric="views" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link).toBeTruthy();
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.textContent).toBe('100');
  });

  it('renders compact metric values for large numbers', () => {
    const big = [
      {
        position: 1,
        title: 'Модуль',
        lessons: [
          {
            lesson_id: 10,
            lesson_number: 1,
            title: 'Урок',
            steps: [{ step_id: 500, lesson_id: 10, step_number: 1, block: 'text', viewed_by: 1200, total: 20000, correct: 1500, correct_ratio: 0.8, grade: 4.0, grade_votes: 2 }],
          },
        ],
      },
    ];
    const { container } = render(<CourseStructureMatrix modules={big} metric="views" />);
    expect(container.querySelectorAll('a')[0].textContent).toBe('1.2k');
  });

  it('renders average user grade in cells', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link.textContent).toBe('4.86');
  });

  it('renders dash in grade cell when no votes', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1');
    expect(link.textContent).toBe('—');
  });

  it('renders success percentage in cells', () => {
    render(<CourseStructureMatrix modules={modules} metric="correct" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link.textContent).toBe('80%');
    const empty = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1');
    expect(empty.textContent).toBe('—');
  });

  it('renders dash in success cell when no submissions', () => {
    render(<CourseStructureMatrix modules={modules} metric="correct" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1');
    expect(link.textContent).toBe('—');
  });

  it('renders submitted count cells', () => {
    render(<CourseStructureMatrix modules={modules} metric="submitted" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link.textContent).toBe('50');
  });

  it('STEP_METRICS correct value is a success ratio', () => {
    const step = { total: 200, correct: 150 };
    expect(STEP_METRICS.correct.value(step)).toBeCloseTo(0.75);
    expect(STEP_METRICS.correct.value({ total: 0, correct: 0 })).toBeNull();
  });

  it('renders correct cells green at 100% and red at 0%', () => {
    const m = [
      {
        position: 1,
        title: 'Модуль',
        lessons: [
          {
            lesson_id: 10,
            lesson_number: 1,
            title: 'Урок',
            steps: [
              { step_id: 500, lesson_id: 10, step_number: 1, block: 'text', total: 10, correct: 10 },
              { step_id: 501, lesson_id: 10, step_number: 2, block: 'text', total: 10, correct: 0 },
            ],
          },
        ],
      },
    ];
    const { container } = render(<CourseStructureMatrix modules={m} metric="correct" />);
    const links = container.querySelectorAll('a');
    expect(links[0].style.backgroundColor).toBe('rgb(0, 255, 0)');
    expect(links[1].style.backgroundColor).toBe('rgb(255, 0, 0)');
  });

  it('STEP_METRICS grade value is the average user grade', () => {
    expect(STEP_METRICS.grade.value({ grade: 4.86 })).toBe(4.86);
  });

  it('renders block letter in cells', () => {
    render(<CourseStructureMatrix modules={modules} metric="block" />);
    const link = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/1');
    expect(link.textContent).toBe('Т');
  });

  it('shows deep link to stepik', () => {
    render(<CourseStructureMatrix modules={modules} metric="views" stepikCourseId={68260} />);
    const links = screen.getAllByRole('link');
    expect(links.some((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1')).toBe(true);
  });

  it('shows tooltip with step metrics on hover', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    const cell = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/10/step/2');
    fireEvent.mouseEnter(cell, { clientX: 10, clientY: 10 });
    expect(screen.getByText(/Шаг 2/)).toBeInTheDocument();
    expect(screen.getByText(/Просмотры: 200/)).toBeInTheDocument();
    expect(screen.getByText(/Решений: 60 · Успешных: 30/)).toBeInTheDocument();
    expect(screen.getByText(/Успешность: 50%/)).toBeInTheDocument();
    expect(screen.getByText(/Оценка: 3.50 · 4 гол\./)).toBeInTheDocument();
    fireEvent.mouseLeave(cell);
    expect(screen.queryByText(/Просмотры: 200/)).not.toBeInTheDocument();
  });

  it('shows tooltip with dash grade and success rate for a step without votes', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    const cell = screen.getAllByRole('link').find((l) => l.getAttribute('href') === 'https://stepik.org/lesson/11/step/1');
    fireEvent.mouseEnter(cell, { clientX: 10, clientY: 10 });
    expect(screen.getByText(/Успешность: —/)).toBeInTheDocument();
    expect(screen.getByText(/Оценка: —/)).toBeInTheDocument();
  });

  it('exposes STEP_METRICS with all five metrics', () => {
    expect(Object.keys(STEP_METRICS)).toEqual(['views', 'submitted', 'correct', 'grade', 'block']);
  });

  it('does not render title or legend', () => {
    render(<CourseStructureMatrix modules={modules} metric="grade" />);
    expect(screen.queryByText('Оценка')).not.toBeInTheDocument();
    expect(screen.queryByText('0%')).not.toBeInTheDocument();
    expect(screen.queryByText('100%')).not.toBeInTheDocument();
    expect(screen.queryByText('мало')).not.toBeInTheDocument();
    expect(screen.queryByText('много')).not.toBeInTheDocument();
  });

  it('does not render block legend labels', () => {
    render(<CourseStructureMatrix modules={modules} metric="block" />);
    expect(screen.queryByText('Текст')).not.toBeInTheDocument();
    expect(screen.queryByText('Код')).not.toBeInTheDocument();
    expect(screen.queryByText('Внешний')).not.toBeInTheDocument();
  });

  it('renders empty placeholder cells for shorter lessons', () => {
    const { container } = render(<CourseStructureMatrix modules={modules} metric="views" />);
    expect(container.querySelectorAll('a').length).toBe(3);
  });
});
