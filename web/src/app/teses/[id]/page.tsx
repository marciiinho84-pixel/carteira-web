"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";

interface Tese {
  id: number;
  ticker: string;
  bloco_ips?: string;
  racional?: string;
  cenario_esperado?: string;
  criterio_invalidacao?: string;
  nivel_invalidacao: "VERDE" | "AMARELO" | "VERMELHO";
  status: string;
  dias_desde_criacao?: number;
  data_criacao?: string;
}

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

const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

export default function DetalheTese() {
  const params = useParams<{ id: string }>();
  const id = params?.id;
  const router = useRouter();
  const [tese, setTese] = useState<Tese | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editNivel, setEditNivel] = useState<string | null>(null);
  const [editCriterio, setEditCriterio] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    if (!id) return;
    async function load() {
      setLoading(true);
      try {
        const data = await apiFetch<Tese>(`/teses/${id}`);
        setTese(data);
        setEditNivel(data.nivel_invalidacao);
        setEditCriterio(data.criterio_invalidacao ?? "");
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erro";
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
    load();
  }, [id, router]);

  async function salvar() {
    if (!id || !tese) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await apiFetch(`/teses/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          nivel_invalidacao: editNivel,
          criterio_invalidacao: editCriterio,
        }),
      });
      setTese({ ...tese, nivel_invalidacao: editNivel as "VERDE" | "AMARELO" | "VERMELHO", criterio_invalidacao: editCriterio ?? undefined });
      setSaveMsg("Salvo com sucesso!");
    } catch (e: unknown) {
      setSaveMsg("Erro ao salvar: " + (e instanceof Error ? e.message : ""));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs text-[#6b7280]">
          <Link href="/teses" className="hover:text-[#26A69A]">Teses</Link>
          <span className="mx-1">›</span>
          <span className="text-[#D1D4DC]">{tese?.ticker ?? "..."}</span>
        </div>

        {loading && <div className="animate-pulse h-64 rounded-xl bg-[#1A1D27]" />}
        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {!loading && tese && (
          <>
            {/* Header */}
            <header className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{NIVEL_EMOJI[tese.nivel_invalidacao]}</span>
                    <h1 className="text-2xl font-bold text-white">{tese.ticker}</h1>
                    {tese.bloco_ips && (
                      <span className="rounded-md bg-[#6366F1]/20 px-2 py-0.5 text-[10px] font-bold text-[#6366F1] border border-[#6366F1]/30">
                        {BLOCO_LABEL[tese.bloco_ips] ?? tese.bloco_ips}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs" style={{ color: NIVEL_COR[tese.nivel_invalidacao] }}>
                      {tese.nivel_invalidacao}
                    </span>
                    <span className="text-[#6b7280] text-xs">•</span>
                    <span className="text-xs text-[#6b7280]">{tese.status}</span>
                    {tese.dias_desde_criacao != null && (
                      <>
                        <span className="text-[#6b7280] text-xs">•</span>
                        <span className="text-xs text-[#6b7280]">{tese.dias_desde_criacao}d desde criação</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </header>

            {/* Conteúdo da tese */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
              {tese.racional && (
                <div>
                  <h2 className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-1">Racional / Tese</h2>
                  <p className="text-sm text-[#D1D4DC] leading-relaxed">{tese.racional}</p>
                </div>
              )}
              {tese.cenario_esperado && (
                <div>
                  <h2 className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-1">Cenário Esperado</h2>
                  <p className="text-sm text-[#D1D4DC] leading-relaxed">{tese.cenario_esperado}</p>
                </div>
              )}
              {tese.criterio_invalidacao && (
                <div>
                  <h2 className="text-xs font-semibold text-[#F59E0B] uppercase tracking-wider mb-1">⚠️ Critério de Invalidação</h2>
                  <p className="text-sm text-[#F59E0B] leading-relaxed">{tese.criterio_invalidacao}</p>
                </div>
              )}
            </section>

            {/* Edição inline */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
              <h2 className="text-sm font-semibold text-white">Atualizar Tese</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-[#6b7280] block mb-1">Nível de Invalidação</label>
                  <div className="flex gap-2">
                    {(["VERDE", "AMARELO", "VERMELHO"] as const).map((n) => (
                      <button
                        key={n}
                        onClick={() => setEditNivel(n)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition ${
                          editNivel === n
                            ? "border-current"
                            : "border-[#2A2D3A] text-[#6b7280]"
                        }`}
                        style={editNivel === n ? { color: NIVEL_COR[n], borderColor: NIVEL_COR[n] + "60" } : {}}
                      >
                        {NIVEL_EMOJI[n]} {n}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-[#6b7280] block mb-1">Critério de Invalidação</label>
                  <textarea
                    value={editCriterio ?? ""}
                    onChange={(e) => setEditCriterio(e.target.value)}
                    rows={3}
                    className="w-full rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2 text-sm text-[#D1D4DC] focus:outline-none focus:border-[#6366F1] resize-none"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={salvar}
                    disabled={saving}
                    className="rounded-lg px-4 py-1.5 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 disabled:opacity-50 transition"
                  >
                    {saving ? "Salvando…" : "Salvar"}
                  </button>
                  {saveMsg && (
                    <span className={`text-xs ${saveMsg.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>
                      {saveMsg}
                    </span>
                  )}
                </div>
              </div>
            </section>

            {/* Ações */}
            <div className="flex flex-wrap gap-3">
              <Link
                href={`/ativos/${tese.ticker}`}
                className="rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
              >
                📋 Ver ativo {tese.ticker}
              </Link>
              <Link
                href={`/maestro?q=Status+da+tese+de+${tese.ticker}`}
                className="rounded-lg px-4 py-2 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 transition"
              >
                🤖 Perguntar ao Maestro
              </Link>
              <Link
                href="/teses"
                className="rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
              >
                ← Voltar às Teses
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
