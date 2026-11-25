/**
 * Sorting rules shared by every table (client and server).
 *
 * `naturalDir` is the direction that puts the "main" values on top:
 *   - numbers — largest first (desc),
 *   - text    — А→Я (asc),
 *   - dates   — newest first (desc; date columns are strings, so they set it
 *               explicitly instead of inheriting the text default).
 *
 * The first click on a column uses this direction; repeat clicks flip it.
 * The arrow points at the anchor value: ↑ when it is on top (current direction
 * equals naturalDir), ↓ when it is at the bottom.
 */
export function naturalDirOf(column) {
  if (column?.naturalDir != null) return column.naturalDir;
  return column?.numeric ? 'desc' : 'asc';
}

/** Generic comparator honoring the column config: numeric/nullLast/getValue. */
export function makeComparator(columns) {
  const byKey = Object.fromEntries(columns.map((c) => [c.key, c]));
  return (a, b, key, dir) => {
    const cfg = byKey[key] || {};
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

/** First-click direction for a column (uses naturalDir, not just numeric). */
export function firstSortDir(column) {
  return naturalDirOf(column);
}
