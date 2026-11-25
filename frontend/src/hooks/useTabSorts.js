import { useState } from 'react';
import { firstSortDir } from '../utils/sorting';

/**
 * Сортировка для страниц с вкладками: у каждой вкладки своя колонка и
 * направление.
 *
 * Первый клик использует «естественное» направление колонки (числа — по
 * убыванию, текст — А→Я, даты — новые сверху); повторный клик переворачивает
 * направление. Состояние вкладок независимо: переключение вкладки не сбрасывает
 * сортировку остальных.
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
          : { key, dir: firstSortDir(cfg) };
      return { ...prev, [tab]: next };
    });
  };

  return { sorts, onSort };
}
