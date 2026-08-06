import { memo, Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

const ROW_HEIGHT = 35;

function calcRowsPerPage(node) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  const row = node.querySelector('tbody tr');
  const rowH = row?.offsetHeight || ROW_HEIGHT;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}

export function naturalDirOf(column) {
  return column.naturalDir != null ? column.naturalDir : column.numeric ? 'asc' : 'desc';
}

// Generic comparator honoring the column config: numeric/nullLast/getValue.
export function makeComparator(columns) {
  const byKey = Object.fromEntries(columns.map((c) => [c.key, c]));
  return (a, b, key, dir) => {
    const cfg = byKey[key];
    const va = cfg.getValue ? cfg.getValue(a) : a[key];
    const vb = cfg.getValue ? cfg.getValue(b) : b[key];
    if (cfg.nullLast) {
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
    }
    let diff;
    if (cfg.numeric) {
      diff = (va ?? 0) - (vb ?? 0);
    } else {
      diff = String(va ?? '')
        .toLowerCase()
        .localeCompare(String(vb ?? '').toLowerCase(), 'ru');
    }
    return dir === 'asc' ? diff : -diff;
  };
}

export function useSortState(columns, initialSort) {
  const [sort, setSort] = useState(initialSort);
  const columnsByKey = useMemo(() => Object.fromEntries(columns.map((c) => [c.key, c])), [columns]);
  const onSort = useCallback(
    (key) => {
      setSort((state) =>
        state.key === key
          ? { key, dir: state.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: columnsByKey[key]?.numeric ? 'desc' : 'asc' },
      );
    },
    [columnsByKey],
  );
  return { sort, onSort };
}

export function useRowsPerPage() {
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const tableRef = useRef(null);
  const prevRows = useRef(0);
  const resizeRef = useRef(null);

  useLayoutEffect(() => {
    const node = tableRef.current;
    if (!node) return;
    const calc = calcRowsPerPage(node);
    if (calc !== prevRows.current) {
      prevRows.current = calc;
      setRowsPerPage(calc);
    }
  });

  useEffect(() => {
    prevRows.current = 0;
    const node = tableRef.current;
    if (!node) return;
    const ro = new ResizeObserver(() => {
      const calc = calcRowsPerPage(node);
      if (calc !== prevRows.current) {
        prevRows.current = calc;
        setRowsPerPage(calc);
      }
    });
    resizeRef.current = ro;
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  return { tableRef, rowsPerPage };
}

export const SortableTh = memo(function SortableTh({ column, sort, onSort }) {
  const active = sort.key === column.key;
  const arrow = (
    <span className={`shrink-0 ${active ? 'text-cyber-blue' : 'invisible'}`}>
      {sort.dir === naturalDirOf(column) ? '↓' : '↑'}
    </span>
  );
  return (
    <th
      className={`pb-2 pl-1 pr-1 font-normal text-gray-400 cursor-pointer select-none hover:text-gray-300 transition-colors ${
        column.align === 'right' ? 'text-right' : 'text-left'
      } ${column.width || ''} ${column.headerClassName || ''}`}
      onClick={() => onSort(column.key)}
    >
      <span className="inline-flex items-center gap-1">
        {column.align === 'right' && arrow}
        <span>{column.label}</span>
        {column.align !== 'right' && arrow}
      </span>
    </th>
  );
});

export function Pagination({ page, totalPages, setPage }) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-3 pl-1 pr-1 shrink-0">
      <span className="text-xs text-gray-500">
        Страница {page} из {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          ← Назад
        </button>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}

function defaultTdClass(column) {
  const base =
    column.align === 'right'
      ? 'text-right font-mono text-xs pl-1 pr-1 text-gray-300'
      : 'text-gray-300 font-mono text-xs pl-1 pr-1 truncate';
  return `${base} ${column.cellClassName || ''}`.trim();
}

function DefaultCell({ column, row }) {
  return <td className={defaultTdClass(column)}>{row[column.key] ?? ''}</td>;
}

const Row = memo(function Row({ columns, row }) {
  return (
    <tr className="border-b border-gray-800">
      {columns.map((col) => (
        <Fragment key={col.key}>
          {col.render ? col.render(row) : <DefaultCell column={col} row={row} />}
        </Fragment>
      ))}
    </tr>
  );
});

/**
 * Unified table shell.
 *
 * Column config: { key, label, width, align, numeric, nullLast, naturalDir,
 *   getValue(row) -> sort value, render(row) -> full <td>, cellClassName, headerClassName }
 *
 * Client mode (default): sorts and paginates `rows` internally.
 * Server mode: pass `totalPages` — `rows` are expected already sorted/paginated
 *   by the parent, which also supplies sort/page/rowsPerPage/tableRef.
 */
export default function DataTable({
  columns,
  rows,
  initialSort,
  rowKey,
  emptyText,
  emptyCentered = false,
  error,
  loading = false,
  panelClassName = 'glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none',
  sort: sortProp,
  onSort: onSortProp,
  page: pageProp,
  setPage: setPageProp,
  rowsPerPage: rowsPerPageProp,
  tableRef: tableRefProp,
  totalPages: totalPagesProp,
}) {
  const { tableRef: ownRef, rowsPerPage: ownRows } = useRowsPerPage();
  const { sort: ownSort, onSort: ownOnSort } = useSortState(columns, initialSort);
  const [ownPage, setOwnPage] = useState(1);

  const server = totalPagesProp !== undefined;
  const tableRef = tableRefProp || ownRef;
  const rowsPerPage = rowsPerPageProp ?? ownRows;
  const sort = sortProp !== undefined ? sortProp : ownSort;
  const onSort = onSortProp !== undefined ? onSortProp : ownOnSort;
  const page = pageProp !== undefined ? pageProp : ownPage;
  const setPage = setPageProp || setOwnPage;

  const comparator = useMemo(() => makeComparator(columns), [columns]);

  const view = useMemo(() => {
    if (server) return { rows, totalPages: totalPagesProp };
    const sorted = [...rows].sort((a, b) => comparator(a, b, sort.key, sort.dir));
    const totalPages = Math.max(1, Math.ceil(sorted.length / rowsPerPage));
    const safePage = Math.min(page, totalPages);
    return { rows: sorted.slice((safePage - 1) * rowsPerPage, safePage * rowsPerPage), totalPages };
  }, [server, rows, totalPagesProp, comparator, sort.key, sort.dir, rowsPerPage, page]);

  useEffect(() => {
    if (!server && page > view.totalPages) setPage(view.totalPages);
  }, [server, page, view.totalPages, setPage]);

  const showEmpty = !loading && !error && rows.length === 0 && emptyText;

  return (
    <div className={panelClassName}>
      <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
        <table className="w-full text-sm table-fixed fin-table sol-table">
          <thead>
            <tr className="border-b border-gray-700">
              {columns.map((col) => (
                <SortableTh key={col.key} column={col} sort={sort} onSort={onSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {view.rows.map((row) => (
              <Row key={rowKey(row)} columns={columns} row={row} rowKey={row} />
            ))}
            {showEmpty && !emptyCentered && (
              <tr>
                <td colSpan={columns.length} className="py-8 text-center text-gray-500 text-sm">
                  {emptyText}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        {showEmpty && emptyCentered && (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">{emptyText}</div>
        )}
        {!loading && error && (
          <div className="flex items-center justify-center h-full text-crimson-alert text-sm">{error}</div>
        )}
      </div>
      <Pagination page={page} totalPages={view.totalPages} setPage={setPage} />
    </div>
  );
}
