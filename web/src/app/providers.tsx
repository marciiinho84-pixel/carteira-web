"use client";

import { SessionProvider, useSession } from "next-auth/react";
import { useEffect } from "react";

function TokenSync() {
  const { data: session } = useSession();

  useEffect(() => {
    if (session?.apiToken) {
      localStorage.setItem("carteira_token", session.apiToken);
    }
  }, [session?.apiToken]);

  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <TokenSync />
      {children}
    </SessionProvider>
  );
}
