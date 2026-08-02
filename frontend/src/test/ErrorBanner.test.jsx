import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBanner from '../components/ErrorBanner';

describe('ErrorBanner', () => {
  it('renders error message', () => {
    render(<ErrorBanner message="API is down" />);
    expect(screen.getByText('Ошибка загрузки данных')).toBeInTheDocument();
    expect(screen.getByText('API is down')).toBeInTheDocument();
  });

  it('renders retry button when onRetry provided', () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Failed" onRetry={onRetry} />);
    expect(screen.getByText('Повторить')).toBeInTheDocument();
  });

  it('does not render retry button when onRetry not provided', () => {
    render(<ErrorBanner message="Failed" />);
    expect(screen.queryByText('Повторить')).not.toBeInTheDocument();
  });

  it('calls onRetry on button click', () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="Failed" onRetry={onRetry} />);
    fireEvent.click(screen.getByText('Повторить'));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('renders with crimson border class', () => {
    const { container } = render(<ErrorBanner message="Error" />);
    expect(container.querySelector('.border-crimson-alert\\/30')).toBeInTheDocument();
  });

  it('renders glass-panel container', () => {
    const { container } = render(<ErrorBanner message="Error" />);
    expect(container.querySelector('.glass-panel')).toBeInTheDocument();
  });
});
