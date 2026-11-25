import { memo, Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { firstSortDir, makeComparator, naturalDirOf } from '../utils/sorting';

const ROW_HEIGHT = 35;

function calcRowsPerPage(node, rowHeight = ROW_HEIGHT) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  // Empty-state row has py-8 and must not define the page size.
  const row = node.querySelector('tbody tr[data-row]');
  const rowH = row?.offsetHeight || rowHeight;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}

// Re-exported for pages/tests that historically imported it from DataTable.
export { makeComparator };

export function useSortState(columns, initialSort) {
  const [sort, setSort] = useState(initialSort);
  const columnsByKey = useMemo(() => Object.fromEntries(columns.map((c) => [c.key, c])), [columns]);
  const onSort = useCallback(
    (key) => {
      setSort((state) =>
        state.key === key
          ? { key, dir: state.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: firstSortDir(columnsByKey[key]) },
      );
    },
    [columnsByKey],
  );
  return { sort, onSort };
}

export function useRowsPerPage(rowsLength = 0) {
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [node, setNode] = useState(null);
  const prevRows = useRef(0);
  // Remember the real row height. When a new page is loading the table may be
  // briefly empty; falling back to 35px then made the page size oscillate
  // (clear → measure 35 → fetch → rows at 20 → clear …).
  const rowHeightRef = useRef(ROW_HEIGHT);

  // Callback ref (not a ref object): lazy tabs have no <table> at mount, and
  // an effect with [] would never see the node when the tab is opened later.
  const tableRef = useCallback((nextNode) => setNode(nextNode), []);

  const measure = useCallback(() => {
    if (!node) return;
    const row = node.querySelector('tbody tr[data-row]');
    if (row?.offsetHeight) rowHeightRef.current = row.offsetHeight;
    const calc = calcRowsPerPage(node, rowHeightRef.current);
    if (calc !== prevRows.current) {
      prevRows.current = calc;
      setRowsPerPage(calc);
    }
  }, [node]);

  useEffect(() => {
    if (!node) return undefined;
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(node);
    window.addEventListener('resize', measure);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [node, measure]);

  // Server tables: rows arrive after the request; recalculate the page size
  // for the now-known real row height.
  useEffect(() => {
    measure();
  }, [rowsLength, measure]);

  return { tableRef, rowsPerPage };
}

const SortableTh = memo(function SortableTh({ column, sort, onSort }) {
  const active = sort.key === column.key;
  const arrow = (
    <span className={`shrink-0 ${active ? 'text-cyber-blue' : 'invisible'}`}>
      {sort.dir === naturalDirOf(column) ? '↑' : '↓'}
    </span>
  );
  const activate = () => onSort(column.key);
  return (
    <th
      className={`pb-2 pl-1 pr-1 font-normal text-gray-400 cursor-pointer select-none hover:text-gray-300 transition-colors ${
        column.align === 'right' ? 'text-right' : 'text-left'
      } ${column.width || ''} ${column.headerClassName || ''}`}
      onClick={activate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          activate();
        }
      }}
      tabIndex={0}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span className="inline-flex items-center gap-1">
        {column.align === 'right' && arrow}
        <span>{column.label}</span>
        {column.align !== 'right' && arrow}
      </span>
    </th>
  );
});

function Pagination({ page, totalPages, setPage }) {
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
    <tr data-row="1" className="border-b border-gray-800">
      {columns.map((col) => (
        <Fragment key={col.key}>{col.render ? col.render(row) : <DefaultCell column={col} row={row} />}</Fragment>
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
  const { tableRef: ownRef, rowsPerPage: ownRows } = useRowsPerPage(rows.length);
  const fallbackSort = useMemo(
    () =>
      initialSort || {
        key: columns[0]?.key,
        dir: firstSortDir(columns[0]),
      },
    [initialSort, columns],
  );
  const { sort: ownSort, onSort: ownOnSort } = useSortState(columns, fallbackSort);
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

  // Client tables: a new sort should start from the first page, not keep the
  // old page number of a completely different ordering.
  useEffect(() => {
    if (!server) setPage(1);
  }, [sort.key, sort.dir, server, setPage]);

  const showEmpty = !loading && !error && rows.length === 0 && emptyText;
  const displayPage = Math.min(Math.max(1, page), view.totalPages);

  return (
    <div className={panelClassName}>
      <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
        <table className="w-full text-sm table-fixed fin-table">
          <thead>
            <tr className="border-b border-gray-700">
              {columns.map((col) => (
                <SortableTh key={col.key} column={col} sort={sort} onSort={onSort} />
              ))}
            </tr>
          </thead>
          <tbody>
            {view.rows.map((row) => (
              <Row key={rowKey(row)} columns={columns} row={row} />
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
      <Pagination page={displayPage} totalPages={view.totalPages} setPage={setPage} />
    </div>
  );
}
