"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("carteira_token");
}

function brl(n: number | null | undefined): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(n: number | null | undefined): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(2) + "%";
}

function fmt2(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

interface AtivoData {
  ticker: string;
  posicao: {
    ticker: string;
    classe?: string;
    familia?: string;
    bloco_ips?: string;
    setor?: string;
    qtd: number;
    custo_total: number;
    custo_medio: number;
    preco_atual?: number;
    valor_atual: number;
    pnl: number;
    pnl_pct: number;
  } | null;
  sinais: Record<string, unknown>;
  fundamentos: {
    pl?: number | null;
    pvp?: number | null;
    roe?: number | null;
    div_yield?: number | null;
    margem_ebitda?: number | null;
    div_liq_ebitda?: number | null;
  };
}

interface Tese {
  id: number;
  ticker: string;
  bloco_ips?: string;
  racional?: string;
  criterio_invalidacao?: string;
  nivel_invalidacao: "VERDE" | "AMARELO" | "VERMELHO";
  status: string;
}

function Semaforo({ nivel }: { nivel: string }) {
  const map: Record<string, { color: string; emoji: string }> = {
    VERDE:    { color: "#26A69A", emoji: "🟢" },
    AMARELO:  { color: "#F59E0B", emoji: "🟡" },
    VERMELHO: { color: "#EF5350", emoji: "🔴" },
  };
  const s = map[nivel] ?? map.VERDE;
  return <span title={nivel} style={{ color: s.color }}>{s.emoji}</span>;
}

function GraficoTecnico({ ticker }: { ticker: string }) {
  const [arquivo, setArquivo] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setArquivo(null);
    setError(null);

    async function load() {
      const token = getToken();
      try {
        const res = await fetch(`${API_BASE}/ativos/${ticker}/grafico`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        const data = await res.json();
        if (data.arquivo) {
          const filename = (data.arquivo as string).split("/").pop() ?? "";
          setArquivo(filename);
        } else {
          setError(data.erro ?? "Gráfico indisponível.");
        }
      } catch {
        setError("Erro ao carregar gráfico técnico.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [ticker]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-[#6b7280] text-sm">
        <span className="animate-pulse">Gerando gráfico técnico…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-xs text-[#6b7280] italic px-4 py-3">{error}</div>
    );
  }
  if (arquivo) {
    return (
      <iframe
        src={`${API_BASE}/charts/${arquivo}`}
        className="w-full border-0 rounded-lg"
        style={{ height: "440px" }}
        title={`Gráfico técnico ${ticker}`}
      />
    );
  }
  return null;
}

export default function DetalheAtivo() {
  const params = useParams<{ ticker: string }>();
  const ticker = (params?.ticker ?? "").toUpperCase();
  const router = useRouter();
  const [data, setData] = useState<AtivoData | null>(null);
  const [teses, setTeses] = useState<Tese[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    if (!ticker) return;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [ativoData, tesData] = await Promise.all([
          apiFetch<AtivoData>(`/ativos/${ticker}`),
          apiFetch<Tese[]>(`/teses?ticker=${ticker}`).catch(() => [] as Tese[]),
        ]);
        setData(ativoData);
        setTeses(tesData);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erro ao carregar";
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
  }, [ticker, router]);

  const pnlColor = (v?: number) => (v == null ? "#D1D4DC" : v >= 0 ? "#26A69A" : "#EF5350");
  const pos = data?.posicao;
  const fund = data?.fundamentos ?? {};

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs text-[#6b7280]">
          <Link href="/posicoes" className="hover:text-[#26A69A]">Posições</Link>
          <span className="mx-1">›</span>
          <span className="text-[#D1D4DC]">{ticker}</span>
        </div>

        {loading && (
          <div className="animate-pulse space-y-4">
            <div className="h-24 rounded-xl bg-[#1A1D27]" />
            <div className="h-64 rounded-xl bg-[#1A1D27]" />
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && data && (
          <>
            {/* 1. Header */}
            <header className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-white">{ticker}</h1>
                    {pos?.bloco_ips && (
                      <span className="rounded-md bg-[#6366F1]/20 px-2 py-0.5 text-[10px] font-bold text-[#6366F1] border border-[#6366F1]/30">
                        {pos.bloco_ips.replace("_", " ")}
                      </span>
                    )}
                    {pos?.classe && (
                      <span className="rounded-md bg-[#2A2D3A] px-2 py-0.5 text-[10px] text-[#6b7280] border border-[#2A2D3A]">
                        {pos.classe}
                      </span>
                    )}
                  </div>
                  {pos?.setor && (
                    <p className="text-xs text-[#6b7280] mt-0.5">{pos.setor}</p>
                  )}
                </div>
                {pos && (
                  <div className="flex flex-wrap gap-4">
                    <div className="text-right">
                      <p className="text-[10px] text-[#6b7280] uppercase">Preço Atual</p>
                      <p className="text-lg font-bold font-mono text-[#D1D4DC]">
                        {pos.preco_atual != null ? fmt2(pos.preco_atual) : "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-[#6b7280] uppercase">Valor Posição</p>
                      <p className="text-lg font-bold font-mono text-[#D1D4DC]">
                        {brl(pos.valor_atual)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] text-[#6b7280] uppercase">P&amp;L</p>
                      <p className="text-lg font-bold font-mono" style={{ color: pnlColor(pos.pnl) }}>
                        {brl(pos.pnl)}
                      </p>
                      <p className="text-xs font-mono" style={{ color: pnlColor(pos.pnl_pct) }}>
                        {pct(pos.pnl_pct)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </header>

            {/* 2. Gráfico técnico */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
              <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2D3A]">
                <span className="text-base">📈</span>
                <div>
                  <h2 className="text-sm font-semibold text-white">Gráfico Técnico</h2>
                  <p className="text-[10px] text-[#6b7280]">Via Maestro — RSI e MACD</p>
                </div>
              </div>
              <div className="px-2 py-2">
                <GraficoTecnico ticker={ticker} />
              </div>
            </section>

            {/* 3. Fundamentos */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
              <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2D3A]">
                <span className="text-base">📊</span>
                <h2 className="text-sm font-semibold text-white">Fundamentos</h2>
              </div>
              <div className="px-5 py-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: "P/L", value: fmt2(fund.pl) },
                  { label: "P/VP", value: fmt2(fund.pvp) },
                  { label: "ROE", value: fund.roe != null ? (fund.roe * 100).toFixed(1) + "%" : "—" },
                  { label: "Div. Yield", value: fund.div_yield != null ? (fund.div_yield * 100).toFixed(2) + "%" : "—" },
                  { label: "Marg. EBITDA", value: fund.margem_ebitda != null ? (fund.margem_ebitda * 100).toFixed(1) + "%" : "—" },
                  { label: "Dív/EBITDA", value: fmt2(fund.div_liq_ebitda) },
                ].map((f) => (
                  <div key={f.label} className="rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2">
                    <p className="text-[9px] text-[#6b7280] uppercase tracking-wider">{f.label}</p>
                    <p className="text-sm font-bold font-mono text-[#D1D4DC] mt-0.5">{f.value}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* 4. Teses vinculadas */}
            {teses.length > 0 && (
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2D3A]">
                  <span className="text-base">🔬</span>
                  <h2 className="text-sm font-semibold text-white">Teses Vinculadas</h2>
                </div>
                <div className="px-5 py-4 space-y-3">
                  {teses.map((t) => (
                    <Link key={t.id} href={`/teses/${t.id}`} className="block rounded-lg border border-[#2A2D3A] bg-[#0F1117] px-4 py-3 hover:border-[#6366F1]/50 transition">
                      <div className="flex items-center gap-2 mb-1">
                        <Semaforo nivel={t.nivel_invalidacao} />
                        <span className="text-sm font-semibold text-white">{t.ticker}</span>
                        <span className="text-xs text-[#6b7280]">({t.status})</span>
                      </div>
                      {t.racional && (
                        <p className="text-xs text-[#D1D4DC] line-clamp-2">{t.racional}</p>
                      )}
                      {t.criterio_invalidacao && (
                        <p className="text-[10px] text-[#F59E0B] mt-1">⚠️ {t.criterio_invalidacao.slice(0, 80)}{t.criterio_invalidacao.length > 80 ? "…" : ""}</p>
                      )}
                    </Link>
                  ))}
                </div>
              </section>
            )}

            {/* 5. Ações */}
            <div className="flex flex-wrap gap-3">
              <Link
                href={`/maestro?q=Analise+${ticker}`}
                className="rounded-lg px-4 py-2 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 transition"
              >
                🤖 Perguntar ao Maestro sobre {ticker}
              </Link>
              <Link
                href="/posicoes"
                className="rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
              >
                ← Voltar às Posições
              </Link>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
