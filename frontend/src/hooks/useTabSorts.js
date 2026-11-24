import { useState } from 'react';

/**
 * Сортировка для страниц с вкладками: у каждой вкладки своя колонка и
 * направление.
 *
 * Первый клик по числовой колонке — по убыванию (большие значения сверху),
 * по текстовой — по возрастанию; повторный клик переворачивает направление.
 * Состояние вкладок независимо: переключение вкладки не сбрасывает сортировку
 * остальных.
 */
export function useTabSorts(tabColumns, initialSorts) {
  const [sorts, setSorts] = useState(initialSorts);

  const onSort = (tab) => (key) => {
    setSorts((prev) => {
      const cur = prev[tab] || { key: null, dir: 'asc' };
      const cfg = tabColumns[tab]?.find((c) => c.key === key);
      const next =
        cur.key === key
          ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: cfg?.numeric ? 'desc' : 'asc' };
      return { ...prev, [tab]: next };
    });
  };

  return { sorts, onSort };
}
