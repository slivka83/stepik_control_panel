import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { useTabState } from '../hooks/useTabState';

const TABS = ['months', 'years'];

function Probe() {
  const [tab, setTab] = useTabState('months', TABS);
  const location = useLocation();
  return (
    <div>
      <span data-testid="tab">{tab}</span>
      <span data-testid="search">{location.search}</span>
      <button type="button" onClick={() => setTab('years')}>
        years
      </button>
    </div>
  );
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Probe />
    </MemoryRouter>,
  );
}

describe('useTabState', () => {
  it('falls back to the default tab for an unknown ?tab=', () => {
    renderAt('/?tab=bogus');
    expect(screen.getByTestId('tab').textContent).toBe('months');
  });

  it('keeps a valid tab from the URL', () => {
    renderAt('/?tab=years');
    expect(screen.getByTestId('tab').textContent).toBe('years');
  });

  it('writes the tab to the URL and preserves other params', () => {
    renderAt('/?filter=1');
    fireEvent.click(screen.getByText('years'));
    expect(screen.getByTestId('tab').textContent).toBe('years');
    expect(screen.getByTestId('search').textContent).toContain('tab=years');
    expect(screen.getByTestId('search').textContent).toContain('filter=1');
  });
});
