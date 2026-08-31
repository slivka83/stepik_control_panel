import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

export function useTabState(defaultTab = 'months') {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || defaultTab);

  const handleTabChange = useCallback(
    (tab) => {
      setActiveTab(tab);
      setSearchParams({ tab });
    },
    [setSearchParams],
  );

  return [activeTab, handleTabChange];
}
