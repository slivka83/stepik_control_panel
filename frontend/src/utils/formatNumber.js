export const formatNumber = (value, options = {}) =>
  (value ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 0, ...options });

export const formatCurrency = (value, currency = 'RUB') =>
  (value ?? 0).toLocaleString('ru-RU', {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  });
