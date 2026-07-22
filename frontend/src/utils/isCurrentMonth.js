const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

export const isCurrentMonth = (monthStr) => {
  if (!monthStr) return false
  const now = new Date()
  const current = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`

  if (monthStr.startsWith(current)) return true

  if (/^\d{4}-\d{2}/.test(monthStr)) {
    return monthStr.slice(0, 7) === current
  }

  const parts = monthStr.split(' ')
  const idx = MONTHS_RU.indexOf(parts[0])
  if (idx >= 0 && parts[1]) {
    const isoMonth = String(idx + 1).padStart(2, '0')
    return `${parts[1]}-${isoMonth}` === current
  }

  return false
}
