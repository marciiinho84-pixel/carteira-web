"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";
import FormularioTese from "@/components/maestro/FormularioTese";

interface Tese {
  id: number;
  ticker: string;
  bloco_ips?: string;
  racional?: string;
  criterio_invalidacao?: string;
  nivel_invalidacao: "VERDE" | "AMARELO" | "VERMELHO";
  status: string;
  dias_desde_criacao?: number;
  data_criacao?: string;
}

const STATUS_COR: Record<string, string> = {
  ATIVA: "#26A69A",
  INVALIDADA: "#EF5350",
  ENCERRADA: "#6b7280",
};

const NIVEL_COR: Record<string, string> = {
  VERDE: "#26A69A",
  AMARELO: "#F59E0B",
  VERMELHO: "#EF5350",
};

const NIVEL_EMOJI: Record<string, string> = {
  VERDE: "🟢",
  AMARELO: "🟡",
  VERMELHO: "🔴",
};

const BLOCOS = ["Todos", "SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];
const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

export default function Teses() {
  const router = useRouter();
  const [teses, setTeses] = useState<Tese[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtroBloco, setFiltroBloco] = useState("Todos");
  const [showForm, setShowForm] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await apiFetch<Tese[]>("/teses");
      setTeses(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar teses";
      if (msg.includes("401") || msg.includes("Unauthorized")) {
        clearToken();
        router.replace("/login");
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    load();
  }, [router]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = filtroBloco === "Todos"
    ? teses
    : teses.filter((t) => (t.bloco_ips ?? "FORA_IPS") === filtroBloco);

  const porNivel = (nivel: string) => filtered.filter((t) => t.nivel_invalidacao === nivel);

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1 className="text-lg font-bold text-white">Teses de Investimento</h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-lg px-4 py-1.5 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 transition"
          >
            {showForm ? "✕ Cancelar" : "＋ Nova Tese"}
          </button>
        </div>

        {/* Formulário nova tese */}
        {showForm && (
          <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5">
            <FormularioTese
              onSuccess={() => {
                setShowForm(false);
                load();
              }}
            />
          </section>
        )}

        {/* Filtro bloco */}
        <div className="flex flex-wrap gap-2">
          {BLOCOS.map((b) => (
            <button
              key={b}
              onClick={() => setFiltroBloco(b)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition border ${
                filtroBloco === b
                  ? "bg-[#26A69A]/20 border-[#26A69A] text-[#26A69A]"
                  : "border-[#2A2D3A] text-[#6b7280] hover:border-[#4b5563] hover:text-[#D1D4DC]"
              }`}
            >
              {b === "Todos" ? "Todos" : (BLOCO_LABEL[b] ?? b)}
            </button>
          ))}
        </div>

        {loading && (
          <div className="animate-pulse space-y-2">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl bg-[#1A1D27]" />)}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {!loading && !error && (
          <>
            {(["VERMELHO", "AMARELO", "VERDE"] as const).map((nivel) => {
              const lista = porNivel(nivel);
              if (!lista.length) return null;
              return (
                <section key={nivel} className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                  <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2D3A]">
                    <span>{NIVEL_EMOJI[nivel]}</span>
                    <h2 className="text-sm font-semibold" style={{ color: NIVEL_COR[nivel] }}>
                      {nivel} ({lista.length})
                    </h2>
                  </div>
                  <div className="divide-y divide-[#2A2D3A]">
                    {lista.map((t) => (
                      <Link
                        key={t.id}
                        href={`/teses/${t.id}`}
                        className="block px-5 py-3 hover:bg-[#2A2D3A]/30 transition"
                      >
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{t.ticker}</span>
                            {t.bloco_ips && (
                              <span className="text-[9px] text-[#6b7280] border border-[#2A2D3A] rounded px-1 py-0.5">
                                {BLOCO_LABEL[t.bloco_ips] ?? t.bloco_ips}
                              </span>
                            )}
                            <span className="text-[9px] rounded px-1 py-0.5 border" style={{ color: STATUS_COR[t.status] ?? "#6b7280", borderColor: (STATUS_COR[t.status] ?? "#6b7280") + "40" }}>
                              {t.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-[#6b7280]">
                            {t.dias_desde_criacao != null && <span>{t.dias_desde_criacao}d</span>}
                            <span className="text-[#6b7280]">›</span>
                          </div>
                        </div>
                        {t.racional && (
                          <p className="mt-1 text-xs text-[#D1D4DC] line-clamp-2">{t.racional}</p>
                        )}
                        {t.criterio_invalidacao && (
                          <p className="mt-0.5 text-[10px] text-[#F59E0B]">⚠️ {t.criterio_invalidacao.slice(0, 80)}{t.criterio_invalidacao.length > 80 ? "…" : ""}</p>
                        )}
                      </Link>
                    ))}
                  </div>
                </section>
              );
            })}

            {filtered.length === 0 && (
              <p className="text-center text-xs text-[#6b7280] italic py-8">
                Nenhuma tese {filtroBloco !== "Todos" ? `no bloco ${BLOCO_LABEL[filtroBloco] ?? filtroBloco}` : "cadastrada"}.
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
