const asNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};

export const formatNumber = (value, options = {}) =>
  asNumber(value).toLocaleString('ru-RU', { maximumFractionDigits: 0, ...options });

export const formatCurrency = (value, currency = 'RUB') =>
  asNumber(value).toLocaleString('ru-RU', {
    style: 'currency',
    currency: String(currency || 'RUB').toUpperCase(),
    maximumFractionDigits: 0,
  });
