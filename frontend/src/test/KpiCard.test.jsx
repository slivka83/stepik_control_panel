import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import KpiCard from '../components/KpiCard';

describe('KpiCard', () => {
  it('renders title text', () => {
    render(<KpiCard title="Доход за месяц" value={50000} />);
    expect(screen.getByText('Доход за месяц')).toBeInTheDocument();
  });

  it('renders numeric value with CountUp', () => {
    render(<KpiCard title="Студенты" value={150} />);
    expect(screen.getByText('Студенты')).toBeInTheDocument();
  });

  it('renders prefix', () => {
    render(<KpiCard title="Revenue" value={5000} prefix="$" />);
    expect(screen.getByText('$')).toBeInTheDocument();
  });

  it('renders suffix', () => {
    render(<KpiCard title="Revenue" value={5000} suffix=" ₽" />);
    expect(screen.getByText('₽')).toBeInTheDocument();
  });

  it('applies glass-panel class', () => {
    const { container } = render(<KpiCard title="Test" value={100} />);
    expect(container.firstChild).toHaveClass('glass-panel');
  });

  it('renders trend up indicator', () => {
    const { container } = render(<KpiCard title="Growth" value={100} trend={12} />);
    expect(container.textContent).toContain('12%');
  });

  it('renders trend down indicator', () => {
    const { container } = render(<KpiCard title="Decline" value={100} trend={-5} />);
    expect(container.textContent).toContain('5%');
  });

  it.each([
    [5, 'text-neon-green'],
    [0, 'text-crimson-alert'],
    [-5, 'text-crimson-alert'],
  ])('default trend %s: above zero green, zero and below red', (trend, expectedClass) => {
    const { container } = render(<KpiCard title="T" value={100} trend={trend} />);
    expect(container.querySelector('span.text-xs.font-mono')).toHaveClass(expectedClass);
  });

  it.each([
    [5, 'text-crimson-alert'],
    [0, 'text-neon-green'],
    [-5, 'text-neon-green'],
  ])('inverted trend %s: above zero red, zero and below green', (trend, expectedClass) => {
    const { container } = render(<KpiCard title="T" value={100} trend={trend} trendInverted />);
    expect(container.querySelector('span.text-xs.font-mono')).toHaveClass(expectedClass);
  });

  it('renders zero value', () => {
    render(<KpiCard title="Empty" value={0} />);
    expect(screen.getByText('Empty')).toBeInTheDocument();
  });

  it('renders large numbers', () => {
    render(<KpiCard title="Big" value={1000000} />);
    expect(screen.getByText('Big')).toBeInTheDocument();
  });

  it('does not render trend when trend prop is absent', () => {
    const { container } = render(<KpiCard title="No trend" value={100} />);
    expect(container.textContent).not.toContain('%');
  });

  it.each([
    [1.0, 'rgb(255, 0, 0)'],
    [1.99, 'rgb(255, 0, 0)'],
    [2.0, 'rgb(255, 120, 0)'],
    [3.0, 'rgb(255, 210, 0)'],
    [3.99, 'rgb(255, 210, 0)'],
    [4.0, 'rgb(160, 230, 0)'],
    [4.49, 'rgb(160, 230, 0)'],
    [4.5, 'rgb(0, 180, 0)'],
    [4.7, 'rgb(0, 180, 0)'],
    [4.89, 'rgb(0, 180, 0)'],
    [4.9, 'rgb(0, 255, 0)'],
  ])('rating value %s uses step color %s (no interpolation)', (val, expected) => {
    const { container } = render(<KpiCard title="R" value={val} ratingColor />);
    expect(container.querySelector('.font-mono')).toHaveStyle({ color: expected });
  });

  it.each([
    ['cyber-blue', 'text-cyber-blue'],
    ['neon-green', 'text-neon-green'],
    ['amber-alert', 'text-amber-alert'],
    ['crimson-alert', 'text-crimson-alert'],
  ])('renders with color %s', (color, expectedClass) => {
    const { container } = render(<KpiCard title="Test" value={100} color={color} />);
    expect(container.querySelector('.font-mono')).toHaveClass(expectedClass);
  });
});
