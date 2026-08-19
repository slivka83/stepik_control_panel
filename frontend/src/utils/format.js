export function yearMonthLabel(label) {
  const parts = String(label).split(' ');
  if (parts.length === 2 && /^\d{4}$/.test(parts[1])) return `${parts[1]} ${parts[0]}`;
  return label;
}

export function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

const RATING_STOPS = [
  [1.0, 255, 0, 0],
  [2.0, 255, 120, 0],
  [3.0, 255, 210, 0],
  [4.0, 160, 230, 0],
  [4.5, 0, 180, 0],
  [4.9, 0, 255, 0],
];

export function getRatingColor(rating) {
  const r = Math.max(1, Math.min(5, rating == null ? 0 : rating));
  let color = RATING_STOPS[0];
  for (const stop of RATING_STOPS) {
    if (r >= stop[0]) color = stop;
    else break;
  }
  const [, cr, cg, cb] = color;
  return `rgb(${cr}, ${cg}, ${cb})`;
}
