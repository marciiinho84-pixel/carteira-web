"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

interface RefreshContextValue {
  refreshKey: number;
  triggerRefresh: () => void;
}

const RefreshContext = createContext<RefreshContextValue>({
  refreshKey: 0,
  triggerRefresh: () => {},
});

export function RefreshProvider({ children }: { children: React.ReactNode }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const triggerRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const value = useMemo(() => ({ refreshKey, triggerRefresh }), [refreshKey, triggerRefresh]);
  return <RefreshContext.Provider value={value}>{children}</RefreshContext.Provider>;
}

/**
 * Incrementa a cada vez que "Atualizar cotações" ou "Recalcular" termina com sucesso
 * (ver ActionBar). Páginas que exibem dados ao vivo devem incluir `refreshKey` no
 * array de dependências do useEffect que busca seus dados, pra rebuscar sem F5.
 */
export function useRefreshSignal() {
  return useContext(RefreshContext);
}
