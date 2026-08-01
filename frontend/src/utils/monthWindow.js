export const MONTH_NAMES = {
  1: 'Январь',
  2: 'Февраль',
  3: 'Март',
  4: 'Апрель',
  5: 'Май',
  6: 'Июнь',
  7: 'Июль',
  8: 'Август',
  9: 'Сентябрь',
  10: 'Октябрь',
  11: 'Ноябрь',
  12: 'Декабрь',
}

const MONTH_NUMBERS = Object.fromEntries(
  Object.entries(MONTH_NAMES).map(([num, name]) => [name, Number(num)])
)

export function parseMonthLabel(label) {
  if (!label) return null
  const match = String(label).match(/^(\D+)\s+(\d{4})$/)
  if (!match) return null
  const monthNum = MONTH_NUMBERS[match[1].trim()]
  if (!monthNum) return null
  return { year: Number(match[2]), month: monthNum }
}

export function formatMonthLabel(month, year) {
  return `${MONTH_NAMES[month]} ${year}`
}

export function buildMonthWindow(months, { now = new Date(), size = 18 } = {}) {
  if (!months || !months.length) return []
  const byKey = new Map()
  for (const m of months) {
    const parsed = parseMonthLabel(m && m.month)
    if (parsed) byKey.set(`${parsed.year}-${parsed.month}`, m)
  }
  if (!byKey.size) return months.slice(-size)

  const base = now.getFullYear() * 12 + now.getMonth()
  const entries = []
  for (let i = size - 1; i >= 0; i--) {
    const total = base - i
    const year = Math.floor(total / 12)
    const month = (total % 12) + 1
    const key = `${year}-${month}`
    entries.push(byKey.get(key) || { month: formatMonthLabel(month, year) })
  }
  return entries
}
