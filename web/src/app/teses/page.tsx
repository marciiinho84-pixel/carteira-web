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
  ATIVA: "var(--positive)",
  INVALIDADA: "var(--negative)",
  ENCERRADA: "var(--text-faint)",
};

const NIVEL_COR: Record<string, string> = {
  VERDE: "var(--positive)",
  AMARELO: "var(--warning)",
  VERMELHO: "var(--negative)",
};

const BLOCOS = ["Todos", "SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];
const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

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
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Teses de Investimento
          </h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-lg px-4 py-1.5 text-sm font-semibold transition"
            style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
          >
            {showForm ? "✕ Cancelar" : "＋ Nova Tese"}
          </button>
        </div>

        {/* Formulário nova tese */}
        {showForm && (
          <section
            className="rounded-xl border px-5 py-5"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
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
          {BLOCOS.map((b) => {
            const active = filtroBloco === b;
            return (
              <button
                key={b}
                onClick={() => setFiltroBloco(b)}
                className="px-3.5 py-1.5 rounded-full text-xs font-semibold transition border"
                style={{
                  whiteSpace: "nowrap",
                  borderColor: active ? "var(--accent)" : "var(--border)",
                  color: active ? "var(--accent-strong)" : "var(--text-muted)",
                  background: active ? "rgba(193,95,60,0.12)" : "transparent",
                }}
              >
                {b === "Todos" ? "Todos" : (BLOCO_LABEL[b] ?? b)}
              </button>
            );
          })}
        </div>

        {loading && (
          <div className="animate-pulse space-y-2">
            {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl" style={{ background: "var(--bg-card)" }} />)}
          </div>
        )}

        {error && (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
          >
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {(["VERMELHO", "AMARELO", "VERDE"] as const).map((nivel) => {
              const lista = porNivel(nivel);
              if (!lista.length) return null;
              return (
                <section
                  key={nivel}
                  className="rounded-xl border"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <span className="inline-block rounded-full shrink-0" style={{ width: 9, height: 9, background: NIVEL_COR[nivel] }} />
                    <h2 className="text-sm font-bold" style={{ color: NIVEL_COR[nivel] }}>
                      {nivel} ({lista.length})
                    </h2>
                  </div>
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {lista.map((t) => (
                      <Link
                        key={t.id}
                        href={`/teses/${t.id}`}
                        className="block px-5 py-3 transition"
                        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{t.ticker}</span>
                            {t.bloco_ips && (
                              <span
                                className="text-[9px] rounded px-1.5 py-0.5 border"
                                style={{ whiteSpace: "nowrap", color: "var(--text-faint)", borderColor: "var(--border)" }}
                              >
                                {BLOCO_LABEL[t.bloco_ips] ?? t.bloco_ips}
                              </span>
                            )}
                            <span
                              className="text-[9px] rounded px-1.5 py-0.5 border"
                              style={{ whiteSpace: "nowrap", color: STATUS_COR[t.status] ?? "var(--text-faint)", borderColor: STATUS_COR[t.status] ?? "var(--border)" }}
                            >
                              {t.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[10px]" style={{ color: "var(--text-faint)" }}>
                            {t.dias_desde_criacao != null && <span>{t.dias_desde_criacao}d</span>}
                            <span>›</span>
                          </div>
                        </div>
                        {t.racional && (
                          <p className="mt-1 text-xs line-clamp-2" style={{ color: "var(--text-body)" }}>{t.racional}</p>
                        )}
                        {t.criterio_invalidacao && (
                          <p className="mt-0.5 text-[10px]" style={{ color: "var(--warning)" }}>⚠ {t.criterio_invalidacao.slice(0, 80)}{t.criterio_invalidacao.length > 80 ? "…" : ""}</p>
                        )}
                      </Link>
                    ))}
                  </div>
                </section>
              );
            })}

            {filtered.length === 0 && (
              <p className="text-center text-xs italic py-8" style={{ color: "var(--text-faint)" }}>
                Nenhuma tese {filtroBloco !== "Todos" ? `no bloco ${BLOCO_LABEL[filtroBloco] ?? filtroBloco}` : "cadastrada"}.
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
