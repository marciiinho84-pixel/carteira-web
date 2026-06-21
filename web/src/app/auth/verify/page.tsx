"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { auth, setToken } from "@/lib/api";
import { Suspense } from "react";

function VerifyInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<"verifying" | "error">("verifying");
  const [message, setMessage] = useState("Validando token…");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setStatus("error");
      setMessage("Token ausente na URL.");
      return;
    }

    auth
      .verify(token)
      .then((res) => {
        setToken(res.access_token);
        router.replace("/dashboard");
      })
      .catch((err: unknown) => {
        setStatus("error");
        setMessage(
          err instanceof Error ? err.message : "Token inválido ou expirado."
        );
      });
  }, [params, router]);

  return (
    <main className="min-h-screen flex items-center justify-center bg-[#0F1117]">
      <div className="w-full max-w-sm rounded-2xl border border-zinc-800 bg-zinc-900 p-8 text-center shadow-xl">
        {status === "verifying" ? (
          <>
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-teal-500 border-t-transparent" />
            <p className="text-sm text-zinc-400">{message}</p>
          </>
        ) : (
          <>
            <p className="mb-4 text-sm font-medium text-red-400">{message}</p>
            <a href="/login" className="text-sm text-teal-400 hover:underline">
              Solicitar novo link
            </a>
          </>
        )}
      </div>
    </main>
  );
}

export default function VerifyPage() {
  return (
    <Suspense>
      <VerifyInner />
    </Suspense>
  );
}
