/**
 * Чистые расчёты страницы «Финансы» (без React) — вынесены из страницы, чтобы
 * их можно было проверять отдельно от вёрстки.
 */

// Aggregate recent payments by the viewer's LOCAL calendar day, mirroring the
// date logic used by the "Последние операции" tab (new Date(p.time)). This
// guarantees the "today" row matches what the recent-operations tab shows.
export function buildDailyStats(recent, daysBack = 30) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const buckets = {};
  for (const p of recent || []) {
    const t = new Date(p.time);
    if (Number.isNaN(t.getTime())) continue;
    const d = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    if (d > today) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const b =
      buckets[key] ||
      (buckets[key] = {
        day: key,
        payments_count: 0,
        turnover: 0,
        income: 0,
        refunds: 0,
        refunds_count: 0,
      });
    b.payments_count += 1;
    const status = p.status || '';
    const amount = parseFloat(p.amount) || 0;
    const paymentAmount = parseFloat(p.payment_amount) || 0;
    if (status === 'refunded') {
      b.refunds += Math.abs(amount);
      b.refunds_count += 1;
      b.turnover -= paymentAmount;
      b.income += amount;
    } else {
      b.turnover += paymentAmount;
      b.income += amount;
    }
  }
  const out = [];
  const start = new Date(today);
  start.setDate(start.getDate() - (daysBack - 1));
  for (let i = 0; i < daysBack; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    out.push(
      buckets[key] || {
        day: key,
        payments_count: 0,
        turnover: 0,
        income: 0,
        refunds: 0,
        refunds_count: 0,
      },
    );
  }
  out.sort((a, b) => (a.day < b.day ? 1 : -1));
  return out;
}

/**
 * Комиссия Stepik по платежу: сколько платформа удержала с покупателя.
 * Возвращает null, если платежа нет (делить не на что).
 */
export function paymentCommission(payment) {
  const paid = Number(payment.payment_amount);
  const income = Number(payment.amount);
  if (!Number.isFinite(paid) || paid <= 0) return null;
  const fee = Math.max(0, paid - Math.abs(Number.isFinite(income) ? income : 0));
  return { pct: Math.round((fee / paid) * 100), amount: fee };
}

/** Комиссия по строке графика: оборот минус доход (в деньгах). */
export function chartCommission(row) {
  return (row?.turnover || 0) - (row?.income || 0);
}

/** UTM-метки платежа для нативного тултипа (по строке на метку). */
export function formatUtmTooltip(raw) {
  const utm = raw?.last_course_click_utm;
  if (!utm || typeof utm !== 'object') return '';
  return Object.entries(utm)
    .map(([k, v]) => `${k}: ${v ?? ''}`)
    .join('\n');
}
