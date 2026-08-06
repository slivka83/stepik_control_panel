import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Tabs from '../components/Tabs';

describe('Tabs', () => {
  const items = [
    { key: 'months', label: 'По месяцам' },
    { key: 'years', label: 'По годам' },
    { key: 'courses', label: 'По курсам' },
  ];

  it('renders all tab labels', () => {
    render(<Tabs items={items} active="months" onChange={vi.fn()} />);
    for (const item of items) {
      expect(screen.getByText(item.label)).toBeInTheDocument();
    }
  });

  it('marks the active tab with cyber-blue styles', () => {
    render(<Tabs items={items} active="years" onChange={vi.fn()} />);
    const active = screen.getByText('По годам').closest('button');
    expect(active.className).toContain('border-cyber-blue');
    expect(active.className).toContain('text-cyber-blue');
  });

  it('calls onChange with the clicked tab key', () => {
    const onChange = vi.fn();
    render(<Tabs items={items} active="months" onChange={onChange} />);
    fireEvent.click(screen.getByText('По курсам'));
    expect(onChange).toHaveBeenCalledWith('courses');
  });
});
