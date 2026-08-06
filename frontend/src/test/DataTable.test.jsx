import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import DataTable, { makeComparator } from '../components/DataTable';

const columns = [
  { key: 'name', label: 'Имя', width: 'w-[20%]' },
  { key: 'score', label: 'Балл', align: 'right', width: 'w-[20%]', numeric: true },
  { key: 'note', label: 'Заметка', align: 'right', width: 'w-[20%]', nullLast: true, render: (r) => <td>{r.note ?? '—'}</td> },
];

const rows = [
  { id: 1, name: 'Бета', score: 10, note: null },
  { id: 2, name: 'Альфа', score: 5, note: 'x' },
  { id: 3, name: 'Гамма', score: 15, note: 'y' },
];

function renderTable(overrides = {}) {
  return render(
    <DataTable
      columns={columns}
      rows={rows}
      initialSort={{ key: 'name', dir: 'asc' }}
      rowKey={(r) => r.id}
      {...overrides}
    />,
  );
}

const rowNames = () => screen.getAllByRole('row').slice(1).map((tr) => tr.textContent);

describe('DataTable', () => {
  it('sorts numeric column desc on first click and asc on second', () => {
    renderTable();
    expect(rowNames()[0]).toContain('Альфа');

    fireEvent.click(screen.getByText('Балл').closest('th'));
    expect(rowNames()[0]).toContain('Гамма');
    expect(rowNames()[2]).toContain('Альфа');

    fireEvent.click(screen.getByText('Балл').closest('th'));
    expect(rowNames()[0]).toContain('Альфа');
    expect(rowNames()[2]).toContain('Гамма');
  });

  it('sorts text column А-Я on first click and Я-А on second', () => {
    renderTable();
    fireEvent.click(screen.getByText('Балл').closest('th'));
    fireEvent.click(screen.getByText('Имя').closest('th'));
    expect(rowNames()[0]).toContain('Альфа');
    expect(rowNames()[1]).toContain('Бета');
    expect(rowNames()[2]).toContain('Гамма');

    fireEvent.click(screen.getByText('Имя').closest('th'));
    expect(rowNames()[0]).toContain('Гамма');
    expect(rowNames()[2]).toContain('Альфа');
  });

  it('keeps null values last when sorting in both directions', () => {
    renderTable();
    fireEvent.click(screen.getByText('Заметка').closest('th'));
    expect(rowNames()[2]).toContain('—');

    fireEvent.click(screen.getByText('Заметка').closest('th'));
    expect(rowNames()[2]).toContain('—');
    expect(rowNames()[0]).toContain('Гамма');
  });

  it('shows arrow pointing at the anchor value (up on first click, down on second)', () => {
    renderTable();
    const arrowOf = (th) => th.querySelector('span.text-cyber-blue').textContent;
    fireEvent.click(screen.getByText('Балл').closest('th'));
    expect(arrowOf(screen.getByText('Балл').closest('th'))).toBe('↑');
    fireEvent.click(screen.getByText('Балл').closest('th'));
    expect(arrowOf(screen.getByText('Балл').closest('th'))).toBe('↓');
  });

  it('uses getValue for the sort value (month composite key)', () => {
    const monthRows = [
      { id: 1, label: 'Январь 2026', year: 2026, month_num: 1 },
      { id: 2, label: 'Февраль 2025', year: 2025, month_num: 2 },
    ];
    const monthColumns = [
      { key: 'label', label: 'Месяц', width: 'w-[50%]', numeric: true, getValue: (r) => r.year * 100 + r.month_num },
    ];
    render(
      <DataTable
        columns={monthColumns}
        rows={monthRows}
        initialSort={{ key: 'label', dir: 'desc' }}
        rowKey={(r) => r.id}
      />,
    );
    let rowsEl = screen.getAllByRole('row').slice(1);
    expect(within(rowsEl[0]).getByText('Январь 2026')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Месяц').closest('th'));
    rowsEl = screen.getAllByRole('row').slice(1);
    expect(within(rowsEl[0]).getByText('Февраль 2025')).toBeInTheDocument();
  });

  it('renders custom render cells', () => {
    renderTable();
    expect(screen.getByText('x')).toBeInTheDocument();
    expect(screen.getByText('y')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('paginates rows client-side', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({ id: i + 1, name: `Ряд ${i + 1}`, score: i }));
    renderTable({ rows: many });
    expect(screen.getByText('Страница 1 из 2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Вперёд →'));
    expect(screen.getByText('Страница 2 из 2')).toBeInTheDocument();
    expect(screen.queryByText('Ряд 1')).not.toBeInTheDocument();
  });

  it('renders empty state row with colSpan when emptyText provided', () => {
    renderTable({ rows: [], emptyText: 'Нет данных' });
    const td = screen.getByText('Нет данных').closest('td');
    expect(td).toHaveAttribute('colspan', '3');
  });

  it('renders no placeholder when empty and emptyText omitted', () => {
    renderTable({ rows: [] });
    expect(screen.getByText('Имя')).toBeInTheDocument();
    expect(screen.queryByText('Нет данных')).not.toBeInTheDocument();
  });

  it('renders empty state centered when emptyCentered is set', () => {
    renderTable({ rows: [], emptyText: 'Нет данных', emptyCentered: true });
    expect(screen.getByText('Нет данных')).toBeInTheDocument();
    expect(screen.queryByRole('cell')).not.toBeInTheDocument();
  });

  it('renders error instead of empty state when error provided', () => {
    renderTable({ rows: [], emptyText: 'Нет данных', error: 'Не удалось загрузить данные' });
    expect(screen.getByText('Не удалось загрузить данные')).toBeInTheDocument();
    expect(screen.queryByText('Нет данных')).not.toBeInTheDocument();
  });

  it('server mode renders given rows without slicing and uses controlled props', () => {
    render(
      <DataTable
        columns={columns}
        rows={[rows[0]]}
        totalPages={2}
        sort={{ key: 'score', dir: 'desc' }}
        onSort={vi.fn()}
        page={2}
        setPage={vi.fn()}
        rowsPerPage={1}
        rowKey={(r) => r.id}
      />,
    );
    const rowsEl = screen.getAllByRole('row').slice(1);
    expect(rowsEl.length).toBe(1);
    expect(within(rowsEl[0]).getByText('Бета')).toBeInTheDocument();
    expect(screen.getByText('Страница 2 из 2')).toBeInTheDocument();
  });
});

describe('makeComparator', () => {
  it('sorts numeric values ascending and descending', () => {
    const compare = makeComparator(columns);
    expect(compare({ score: 1 }, { score: 2 }, 'score', 'asc')).toBeLessThan(0);
    expect(compare({ score: 1 }, { score: 2 }, 'score', 'desc')).toBeGreaterThan(0);
  });

  it('keeps null last when nullLast is set', () => {
    const compare = makeComparator(columns);
    expect(compare({ note: 'a' }, { note: null }, 'note', 'asc')).toBeLessThan(0);
    expect(compare({ note: null }, { note: 'a' }, 'note', 'asc')).toBeGreaterThan(0);
  });
});
