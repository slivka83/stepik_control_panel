import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * Вкладка, синхронизированная с URL (?tab=).
 *
 * `allowed` — список допустимых ключей: неизвестное значение из адресной
 * строки (старая ссылка, опечатка) не должно оставлять страницу пустой.
 * activeTab следует за URL, поэтому работают Back/Forward.
 */
export function useTabState(defaultTab = 'months', allowed = null) {
  const [searchParams, setSearchParams] = useSearchParams();
  const allowedKey = allowed ? allowed.join(',') : '';

  const readTab = useCallback(() => {
    const value = searchParams.get('tab');
    const valid = allowed ? allowed.includes(value) : Boolean(value);
    return valid ? value : defaultTab;
  }, [searchParams, defaultTab, allowed, allowedKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const [activeTab, setActiveTab] = useState(readTab);

  useEffect(() => {
    setActiveTab(readTab());
  }, [readTab]);

  const handleTabChange = useCallback(
    (tab) => {
      setActiveTab(tab);
      const next = new URLSearchParams(searchParams);
      next.set('tab', tab);
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  return [activeTab, handleTabChange];
}
