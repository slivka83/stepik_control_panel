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
  // Возврат — не покупка: «комиссия» от возвращённой суммы смысла не имеет
  // (полный возврат давал бы 100%). В таблице показываем «—».
  if (payment?.status === 'refunded') return null;
  const paid = Number(payment.payment_amount);
  const income = Number(payment.amount);
  if (!Number.isFinite(paid) || paid <= 0) return null;
  const fee = Math.max(0, paid - Math.abs(Number.isFinite(income) ? income : 0));
  return { pct: Math.round((fee / paid) * 100), amount: fee };
}

/** Ставка Stepik для покупок по авторской (А-)ссылке. */
const AUTHOR_LINK_COMMISSION_PCT = 7;

/**
 * Подозрительная комиссия: покупка по А-ссылке, но процент выше 7%.
 *
 * 7% полагается только авторской продаже по А-ссылке. Если промокод
 * не авторский, а от Stepik, — это продвижение Stepik, и ставка 7% не
 * применяется: 40% для такой продажи нормальны. Обычные продажи через
 * Stepik (без А-ссылки) тоже не помечаем, даже если промокод авторский.
 * Возвраты не помечаем: там процент считается от возвращённой суммы.
 *
 * `promo_is_stepik === null` — промокод не синкан, владелец неизвестен.
 * Такой платёж не помечаем: ложные срабатывания хуже пропущенного.
 * Отсутствие поля (старый снапшот) — данных о промокоде нет, ведём себя как
 * раньше и помечаем: после ближайшего синка появится точный флаг.
 */
export function commissionWarning(payment, expectedPct = AUTHOR_LINK_COMMISSION_PCT) {
  if (payment?.status === 'refunded') return null;
  const commission = paymentCommission(payment);
  if (!commission) return null;
  const authorLink = payment?.channel === 'А-ссылка' || payment?.raw?.is_z_link_used === true;
  if (!authorLink) return null;
  if (payment?.promo_is_stepik === true || payment?.promo_is_stepik === null) return null;
  const paid = Number(payment.payment_amount);
  const exactPct = paid > 0 ? (commission.amount / paid) * 100 : 0;
  // Compare the exact rate: 7.4% must be flagged even though the table shows
  // it rounded as 7%.
  if (exactPct <= expectedPct + 1e-9) return null;
  return {
    ...commission,
    pct: Math.round(exactPct * 10) / 10,
    expectedPct,
    delta: Math.round((exactPct - expectedPct) * 10) / 10,
    severity: 'error',
  };
}

/** Комиссия по строке графика: оборот минус доход (в деньгах), не ниже нуля. */
export function chartCommission(row) {
  // Возвраты могут сделать income больше оборота; отрицательный столбик
  // комиссии ломал бы стек — как в RevenueChart, снизу ограничиваем нулём.
  return Math.max((row?.turnover || 0) - (row?.income || 0), 0);
}

/** UTM-метки платежа для нативного тултипа (по строке на метку). */
export function formatUtmTooltip(raw) {
  const utm = raw?.last_course_click_utm;
  if (!utm || typeof utm !== 'object') return '';
  return Object.entries(utm)
    .map(([k, v]) => `${k}: ${v ?? ''}`)
    .join('\n');
}
