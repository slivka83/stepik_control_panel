import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthProvider } from '../contexts/AuthContext';
import { SyncProvider } from '../contexts/SyncContext';
import App from '../App.jsx';

function renderApp() {
  return render(
    <AuthProvider>
      <SyncProvider>
        <App />
      </SyncProvider>
    </AuthProvider>,
  );
}

describe('App', () => {
  it('renders without crashing', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'));
    const { container } = renderApp();
    expect(container).toBeTruthy();
    expect(await screen.findByRole('navigation', { name: 'Основная навигация' })).toBeInTheDocument();
  });

  it('renders layout wrapper with main content', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'));
    renderApp();
    expect(await screen.findByRole('main', { name: 'Основной контент' })).toBeInTheDocument();
  });

  it('renders sidebar nav links', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'));
    renderApp();
    await screen.findByRole('navigation', { name: 'Основная навигация' });
    expect(screen.getByRole('link', { name: 'Дашборд' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Курсы' })).toHaveAttribute('href', '/courses');
    expect(screen.getByRole('link', { name: 'Решения' })).toHaveAttribute('href', '/solutions');
    expect(screen.getByRole('link', { name: 'Комментарии' })).toHaveAttribute('href', '/comments');
    expect(screen.getByRole('link', { name: 'Финансы' })).toHaveAttribute('href', '/financials');
    expect(screen.getByRole('link', { name: 'Студенты' })).toHaveAttribute('href', '/students');
    expect(screen.getByRole('link', { name: 'Активности' })).toHaveAttribute('href', '/activities');
  });
});
