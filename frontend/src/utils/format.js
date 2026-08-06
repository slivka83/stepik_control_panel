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
