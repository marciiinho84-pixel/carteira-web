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
  VERDE: "var(--positive)",
  AMARELO: "var(--warning)",
  VERMELHO: "var(--negative)",
};

const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

function Semaforo({ nivel }: { nivel: string }) {
  return (
    <span
      title={nivel}
      className="inline-block shrink-0 rounded-full"
      style={{ width: 11, height: 11, background: NIVEL_COR[nivel] ?? NIVEL_COR.VERDE }}
    />
  );
}

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
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs" style={{ color: "var(--text-faint)" }}>
          <Link href="/teses" className="hover:underline" style={{ color: "var(--text-faint)" }}>Teses</Link>
          <span className="mx-1">›</span>
          <span style={{ color: "var(--text-body)" }}>{tese?.ticker ?? "..."}</span>
        </div>

        {loading && <div className="animate-pulse h-64 rounded-xl" style={{ background: "var(--bg-card)" }} />}
        {error && (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
          >
            {error}
          </div>
        )}

        {!loading && tese && (
          <>
            {/* Header */}
            <header
              className="rounded-xl border px-5 py-4"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3">
                    <Semaforo nivel={tese.nivel_invalidacao} />
                    <h1
                      className="text-2xl font-semibold"
                      style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
                    >
                      {tese.ticker}
                    </h1>
                    {tese.bloco_ips && (
                      <span
                        className="rounded-md px-2 py-0.5 text-[10px] font-bold border"
                        style={{ whiteSpace: "nowrap", background: "rgba(108,99,196,0.14)", borderColor: "rgba(108,99,196,0.3)", color: "var(--purple-accent)" }}
                      >
                        {BLOCO_LABEL[tese.bloco_ips] ?? tese.bloco_ips}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs font-semibold" style={{ color: NIVEL_COR[tese.nivel_invalidacao] }}>
                      {tese.nivel_invalidacao}
                    </span>
                    <span className="text-xs" style={{ color: "var(--text-faint)" }}>•</span>
                    <span className="text-xs" style={{ color: "var(--text-faint)" }}>{tese.status}</span>
                    {tese.dias_desde_criacao != null && (
                      <>
                        <span className="text-xs" style={{ color: "var(--text-faint)" }}>•</span>
                        <span className="text-xs" style={{ color: "var(--text-faint)" }}>{tese.dias_desde_criacao}d desde criação</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </header>

            {/* Conteúdo da tese */}
            <section
              className="rounded-xl border px-5 py-5 space-y-4"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              {tese.racional && (
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-faint)" }}>Racional / Tese</h2>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-body)" }}>{tese.racional}</p>
                </div>
              )}
              {tese.cenario_esperado && (
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--text-faint)" }}>Cenário Esperado</h2>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-body)" }}>{tese.cenario_esperado}</p>
                </div>
              )}
              {tese.criterio_invalidacao && (
                <div>
                  <h2 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "var(--warning)" }}>⚠ Critério de Invalidação</h2>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--warning)" }}>{tese.criterio_invalidacao}</p>
                </div>
              )}
            </section>

            {/* Edição inline */}
            <section
              className="rounded-xl border px-5 py-5 space-y-4"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Atualizar Tese</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-faint)" }}>Nível de Invalidação</label>
                  <div className="flex gap-2">
                    {(["VERDE", "AMARELO", "VERMELHO"] as const).map((n) => {
                      const active = editNivel === n;
                      return (
                        <button
                          key={n}
                          onClick={() => setEditNivel(n)}
                          className="px-3 py-1.5 rounded-lg text-xs font-medium border transition flex items-center gap-1.5"
                          style={{
                            whiteSpace: "nowrap",
                            color: active ? NIVEL_COR[n] : "var(--text-muted)",
                            borderColor: active ? NIVEL_COR[n] : "var(--border)",
                          }}
                        >
                          <span className="inline-block rounded-full shrink-0" style={{ width: 8, height: 8, background: NIVEL_COR[n] }} />
                          {n}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <label className="text-xs block mb-1" style={{ color: "var(--text-faint)" }}>Critério de Invalidação</label>
                  <textarea
                    value={editCriterio ?? ""}
                    onChange={(e) => setEditCriterio(e.target.value)}
                    rows={3}
                    className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none resize-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={salvar}
                    disabled={saving}
                    className="rounded-lg px-4 py-1.5 text-sm font-semibold transition disabled:opacity-50"
                    style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
                  >
                    {saving ? "Salvando…" : "Salvar"}
                  </button>
                  {saveMsg && (
                    <span className="text-xs" style={{ color: saveMsg.includes("Erro") ? "var(--negative)" : "var(--positive)" }}>
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
                className="rounded-lg px-4 py-2 text-sm border transition"
                style={{ borderColor: "var(--border)", color: "var(--text-body)" }}
              >
                📋 Ver ativo {tese.ticker}
              </Link>
              <Link
                href={`/maestro?q=Status+da+tese+de+${tese.ticker}`}
                className="rounded-lg px-4 py-2 text-sm font-semibold transition"
                style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
              >
                🤖 Perguntar ao Maestro
              </Link>
              <Link
                href="/teses"
                className="rounded-lg px-4 py-2 text-sm border transition"
                style={{ borderColor: "var(--border)", color: "var(--text-body)" }}
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
