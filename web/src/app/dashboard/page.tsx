"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth, apiStatus, clearToken } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [apiVersion, setApiVersion] = useState<string>("");

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    auth
      .me()
      .then((res) => setUserEmail(res.email))
      .catch(() => {
        clearToken();
        router.replace("/login");
      });

    apiStatus()
      .then((res) => {
        setApiOk(true);
        setApiVersion(res.version);
      })
      .catch(() => setApiOk(false));
  }, [router]);

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <main className="min-h-screen bg-[#0F1117] text-zinc-100 p-8">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">App Minha Carteira</h1>
            {userEmail && (
              <p className="text-sm text-zinc-400 mt-1">
                Olá, <span className="text-teal-400">{userEmail}</span>
              </p>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm
                       text-zinc-400 hover:border-zinc-500 hover:text-zinc-200 transition"
          >
            Sair
          </button>
        </div>

        {/* API Status */}
        <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
          <h2 className="mb-3 text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            Status da Infraestrutura
          </h2>
          <div className="flex items-center gap-3">
            <div
              className={`h-3 w-3 rounded-full ${
                apiOk === null
                  ? "bg-zinc-600"
                  : apiOk
                  ? "bg-teal-500"
                  : "bg-red-500"
              }`}
            />
            <span className="text-sm text-zinc-300">
              {apiOk === null
                ? "Verificando API…"
                : apiOk
                ? `Backend OK (v${apiVersion})`
                : "Backend inacessível"}
            </span>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <div className="h-3 w-3 rounded-full bg-teal-500" />
            <span className="text-sm text-zinc-300">Auth JWT ativo</span>
          </div>
          <div className="mt-2 flex items-center gap-3">
            <div className="h-3 w-3 rounded-full bg-teal-500" />
            <span className="text-sm text-zinc-300">PostgreSQL (via backend)</span>
          </div>
        </div>

        {/* Em construção */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center">
          <div className="mb-4 text-4xl">🏗️</div>
          <h2 className="text-lg font-semibold text-zinc-200">Sala de Comando</h2>
          <p className="mt-2 text-sm text-zinc-500">
            Em construção — Fatia 15.
            <br />
            A interface React será construída aqui após a infra estar estável.
          </p>
          <p className="mt-4 text-xs text-zinc-600">
            Por enquanto, o app Streamlit continua acessível em{" "}
            <a
              href="https://minhacarteira.duckdns.org"
              className="text-teal-600 hover:text-teal-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              minhacarteira.duckdns.org
            </a>
          </p>
        </div>
      </div>
    </main>
  );
}
