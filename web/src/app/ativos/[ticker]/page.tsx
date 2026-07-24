"use client";

export const dynamic = "force-dynamic";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";
import { useRefreshSignal } from "@/lib/refresh-context";

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

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

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
  const map: Record<string, string> = {
    VERDE: "var(--positive)",
    AMARELO: "var(--warning)",
    VERMELHO: "var(--negative)",
  };
  const color = map[nivel] ?? map.VERDE;
  return (
    <span
      title={nivel}
      className="inline-block shrink-0 rounded-full"
      style={{ width: 9, height: 9, background: color }}
    />
  );
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
      <div className="flex items-center justify-center h-48 text-sm" style={{ color: "var(--text-faint)" }}>
        <span className="animate-pulse">Gerando gráfico técnico…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-xs italic px-4 py-3" style={{ color: "var(--text-faint)" }}>{error}</div>
    );
  }
  if (arquivo) {
    return (
      <iframe
        src={`${API_BASE}/charts/${arquivo}`}
        className="w-full border-0 rounded-lg"
        style={{ height: "920px" }}
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
  const { refreshKey } = useRefreshSignal();
  const firstLoad = useRef(true);
  const [data, setData] = useState<AtivoData | null>(null);
  const [teses, setTeses] = useState<Tese[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    if (!ticker) return;

    async function load() {
      if (firstLoad.current) setLoading(true);
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
        firstLoad.current = false;
      }
    }
    load();
  }, [ticker, router, refreshKey]);

  const pnlColor = (v?: number) => (v == null ? "var(--text-primary)" : v >= 0 ? "var(--positive)" : "var(--negative)");
  const pos = data?.posicao;
  const fund = data?.fundamentos ?? {};

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs" style={{ color: "var(--text-faint)" }}>
          <Link href="/posicoes" className="hover:underline" style={{ color: "var(--text-faint)" }}>Posições</Link>
          <span className="mx-1">›</span>
          <span style={{ color: "var(--text-body)" }}>{ticker}</span>
        </div>

        {loading && (
          <div className="animate-pulse space-y-4">
            <div className="h-24 rounded-xl" style={{ background: "var(--bg-card)" }} />
            <div className="h-64 rounded-xl" style={{ background: "var(--bg-card)" }} />
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

        {!loading && data && (
          <>
            {/* 1. Header */}
            <header
              className="rounded-xl border px-5 py-4"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <h1
                      className="text-2xl font-semibold"
                      style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
                    >
                      {ticker}
                    </h1>
                    {pos?.bloco_ips && (
                      <span
                        className="rounded-md px-2 py-0.5 text-[10px] font-bold border"
                        style={{ whiteSpace: "nowrap", background: "rgba(108,99,196,0.14)", borderColor: "rgba(108,99,196,0.3)", color: "var(--purple-accent)" }}
                      >
                        {pos.bloco_ips.replace("_", " ")}
                      </span>
                    )}
                    {pos?.classe && (
                      <span
                        className="rounded-md px-2 py-0.5 text-[10px] border"
                        style={{ whiteSpace: "nowrap", background: "var(--bg-card-alt)", color: "var(--text-muted)", borderColor: "var(--border)" }}
                      >
                        {pos.classe}
                      </span>
                    )}
                  </div>
                  {pos?.setor && (
                    <p className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>{pos.setor}</p>
                  )}
                </div>
                {pos && (
                  <div className="flex flex-wrap gap-4">
                    <div className="text-right">
                      <p className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Preço Atual</p>
                      <p className="text-lg font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>
                        {pos.preco_atual != null ? fmt2(pos.preco_atual) : "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Valor Posição</p>
                      <p className="text-lg font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>
                        {brl(pos.valor_atual)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>P&amp;L</p>
                      <p className="text-lg font-bold" style={{ color: pnlColor(pos.pnl), fontFamily: "var(--font-plex-mono)" }}>
                        {brl(pos.pnl)}
                      </p>
                      <p className="text-xs" style={{ color: pnlColor(pos.pnl_pct), fontFamily: "var(--font-plex-mono)" }}>
                        {pct(pos.pnl_pct)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </header>

            {/* 2. Gráfico técnico */}
            <section
              className="rounded-xl border"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                <span className="text-base">📈</span>
                <div>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Gráfico Técnico</h2>
                  <p className="text-[10px]" style={{ color: "var(--text-faint)" }}>Via Maestro — RSI e MACD</p>
                </div>
              </div>
              <div className="px-2 py-2">
                <GraficoTecnico ticker={ticker} />
              </div>
            </section>

            {/* 3. Fundamentos */}
            <section
              className="rounded-xl border"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                <span className="text-base">📊</span>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Fundamentos</h2>
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
                  <div key={f.label} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                    <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>{f.label}</p>
                    <p className="text-sm font-bold mt-0.5" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{f.value}</p>
                  </div>
                ))}
              </div>
            </section>

            {/* 4. Teses vinculadas */}
            {teses.length > 0 && (
              <section
                className="rounded-xl border"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                  <span className="text-base">🔬</span>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Teses Vinculadas</h2>
                </div>
                <div className="px-5 py-4 space-y-3">
                  {teses.map((t) => (
                    <Link
                      key={t.id}
                      href={`/teses/${t.id}`}
                      className="block rounded-lg border px-4 py-3 transition"
                      style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "rgba(108,99,196,0.4)")}
                      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-soft)")}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Semaforo nivel={t.nivel_invalidacao} />
                        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{t.ticker}</span>
                        <span className="text-xs" style={{ color: "var(--text-faint)" }}>({t.status})</span>
                      </div>
                      {t.racional && (
                        <p className="text-xs line-clamp-2" style={{ color: "var(--text-body)" }}>{t.racional}</p>
                      )}
                      {t.criterio_invalidacao && (
                        <p className="text-[10px] mt-1" style={{ color: "var(--warning)" }}>⚠ {t.criterio_invalidacao.slice(0, 80)}{t.criterio_invalidacao.length > 80 ? "…" : ""}</p>
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
                className="rounded-lg px-4 py-2 text-sm font-semibold transition"
                style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
              >
                🤖 Perguntar ao Maestro sobre {ticker}
              </Link>
              <Link
                href="/posicoes"
                className="rounded-lg px-4 py-2 text-sm border transition"
                style={{ borderColor: "var(--border)", color: "var(--text-body)" }}
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
