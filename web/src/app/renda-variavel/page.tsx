"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";

interface CarteiraRV {
  caixa_atual: number;
  entrando_5d: number;
  saindo_5d: number;
  saldo_projetado: number;
  pendentes: PendenteItem[];
  setores: SetorItem[];
  twr_rv: number;
  ibov_ytd: number;
  sp500_brl_ytd: number;
}

interface PendenteItem {
  liquidacao: string;
  trade: string;
  tipo: string;
  ativo: string;
  qtd?: number;
  valor: number;
  impacto: number;
  prazo: string;
  saldo_projetado: number;
}

interface SetorItem {
  setor: string;
  valor: number;
  pct_rv: number;
  n_ativos: number;
  ativos: string[];
}

interface SinalItem {
  ticker: string;
  sinal: string;
  fonte?: string;
  preco_atual?: number;
  preco_alvo?: number;
  variacao_dia?: number;
  tem_sinal_ativo?: boolean;
}

interface WatchlistItem {
  id: number;
  ticker: string;
  preco_alvo?: number;
  obs?: string;
  sinal?: string;
}

function brl(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function pct(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(d) + "%";
}
const green = "var(--positive)", red = "var(--negative)", amber = "var(--warning)";
const valColor = (n: number | null | undefined) => (n == null ? "var(--text-primary)" : n >= 0 ? green : red);
const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";
const sinalColor = (s: string) => s === "COMPRA" ? green : s === "VENDA" ? red : amber;

export default function RendaVariavel() {
  const router = useRouter();
  const [rv, setRv] = useState<CarteiraRV | null>(null);
  const [sinais, setSinais] = useState<SinalItem[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [wlTicker, setWlTicker] = useState("");
  const [wlAlvo, setWlAlvo] = useState("");
  const [wlObs, setWlObs] = useState("");
  const [wlAdding, setWlAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [rvData, sinaisData, wlData] = await Promise.all([
        apiFetch<CarteiraRV>("/carteira-rv"),
        apiFetch<SinalItem[]>("/sinais/carteira_rv").catch(() => []),
        apiFetch<WatchlistItem[]>("/watchlist").catch(() => []),
      ]);
      setRv(rvData);
      setSinais(sinaisData);
      setWatchlist(wlData);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro";
      if (msg.includes("401")) { clearToken(); router.replace("/login"); return; }
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

  async function addWatchlist() {
    if (!wlTicker.trim()) return;
    setWlAdding(true);
    try {
      await apiFetch("/watchlist", {
        method: "POST",
        body: JSON.stringify({
          ticker: wlTicker.trim().toUpperCase(),
          preco_alvo: wlAlvo ? Number(wlAlvo) : null,
          obs: wlObs.trim() || null,
        }),
      });
      setWlTicker(""); setWlAlvo(""); setWlObs("");
      const wl = await apiFetch<WatchlistItem[]>("/watchlist");
      setWatchlist(wl);
    } catch { /* ignore */ }
    finally { setWlAdding(false); }
  }

  async function removeWatchlist(id: number) {
    await apiFetch(`/watchlist/${id}`, { method: "DELETE" }).catch(() => {});
    setWatchlist((prev) => prev.filter((w) => w.id !== id));
  }

  const sinaiesAtivos = sinais.filter((s) => s.tem_sinal_ativo);

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Renda Variável
          </h1>

          {loading && (
            <div className="animate-pulse space-y-3">
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

          {!loading && !error && rv && (
            <>
              {/* Performance */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { label: "TWR RV YTD", value: pct(rv.twr_rv), color: valColor(rv.twr_rv) },
                  { label: "IBOV YTD", value: pct(rv.ibov_ytd), color: valColor(rv.ibov_ytd) },
                  { label: "S&P500 BRL YTD", value: pct(rv.sp500_brl_ytd), color: valColor(rv.sp500_brl_ytd) },
                ].map((k) => (
                  <div
                    key={k.label}
                    className="rounded-xl border px-4 py-3"
                    style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                  >
                    <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{k.label}</p>
                    <p className="text-lg font-bold mt-0.5" style={{ color: k.color, fontFamily: "var(--font-plex-mono)" }}>{k.value}</p>
                  </div>
                ))}
              </div>

              {/* Caixa / Liquidações */}
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Caixa e Liquidações (D+2)</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  {[
                    { label: "Caixa atual (Geral)", value: brl(rv.caixa_atual, 0), color: green },
                    { label: "Vendas aguardando D+2 (já no caixa atual)", value: brl(rv.entrando_5d, 0), color: green },
                    { label: "Compras aguardando D+2 (já saiu do caixa)", value: brl(rv.saindo_5d, 0), color: red },
                    { label: "Disponível sem pendência", value: brl(rv.saldo_projetado, 0), color: valColor(rv.saldo_projetado) },
                  ].map((k) => (
                    <div key={k.label}>
                      <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{k.label}</p>
                      <p className="text-sm font-bold mt-0.5" style={{ color: k.color, fontFamily: "var(--font-plex-mono)" }}>{k.value}</p>
                    </div>
                  ))}
                </div>
                {rv.pendentes.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-y text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="px-3 py-1.5 text-left">Liquidação</th>
                          <th className="px-3 py-1.5 text-left">Ativo</th>
                          <th className="px-3 py-1.5 text-left">Tipo</th>
                          <th className="px-3 py-1.5 text-right">Valor</th>
                          <th className="px-3 py-1.5 text-right">Impacto</th>
                          <th className="px-3 py-1.5 text-right">Disponível ao liquidar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rv.pendentes.map((p, i) => (
                          <tr key={i} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                            <td className="px-3 py-1.5" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{p.liquidacao}</td>
                            <td className="px-3 py-1.5 font-bold">
                              <Link href={`/ativos/${p.ativo}`} className="hover:underline" style={{ color: "var(--purple-accent)" }}>{p.ativo}</Link>
                            </td>
                            <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{p.tipo}</td>
                            <td className="px-3 py-1.5 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.valor, 2)}</td>
                            <td className="px-3 py-1.5 text-right font-bold" style={{ color: valColor(p.impacto), fontFamily: "var(--font-plex-mono)" }}>
                              {p.impacto >= 0 ? "+" : ""}{brl(p.impacto, 2)}
                            </td>
                            <td className="px-3 py-1.5 text-right" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.saldo_projetado, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Distribuição Setorial */}
              {rv.setores.length > 0 && (
                <section
                  className="rounded-xl border px-5 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Distribuição Setorial</h2>
                  <div className="space-y-3">
                    {rv.setores.map((s) => (
                      <div key={s.setor}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="font-medium" style={{ color: "var(--text-body)" }}>{s.setor}</span>
                          <span style={{ color: "var(--text-faint)", fontFamily: "var(--font-plex-mono)" }}>
                            {(s.pct_rv * 100).toFixed(1)}% · {brl(s.valor, 0)} · {s.n_ativos} ativo{s.n_ativos !== 1 ? "s" : ""}
                          </span>
                        </div>
                        <div className="rounded-full overflow-hidden" style={{ height: 6, background: "var(--border-soft)" }}>
                          <div className="h-full rounded-full" style={{ width: `${(s.pct_rv * 100).toFixed(1)}%`, background: "var(--accent)" }} />
                        </div>
                        <div className="flex flex-wrap gap-1.5 mt-1.5">
                          {s.ativos.map((t) => (
                            <Link
                              key={t}
                              href={`/ativos/${t}`}
                              className="text-[10px] hover:underline rounded px-1.5 py-0.5 border"
                              style={{ whiteSpace: "nowrap", color: "var(--accent-strong)", borderColor: "var(--border)", fontFamily: "var(--font-plex-mono)" }}
                            >
                              {t}
                            </Link>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Sinais ativos */}
              {sinaiesAtivos.length > 0 && (
                <section
                  className="rounded-xl border"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{sinaiesAtivos.length} Sinal{sinaiesAtivos.length !== 1 ? "is" : ""} Ativo{sinaiesAtivos.length !== 1 ? "s" : ""}</h2>
                  </div>
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {sinaiesAtivos.map((s) => (
                      <div key={s.ticker} className="flex items-center gap-4 px-5 py-2.5 flex-wrap">
                        <Link href={`/ativos/${s.ticker}`} className="font-bold w-20 shrink-0" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{s.ticker}</Link>
                        <span
                          className="text-xs px-2 py-0.5 rounded font-semibold border"
                          style={{ whiteSpace: "nowrap", color: sinalColor(s.sinal), borderColor: sinalColor(s.sinal) }}
                        >
                          {s.sinal}
                        </span>
                        {s.preco_atual != null && <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>atual: {brl(s.preco_atual, 2)}</span>}
                        {s.preco_alvo != null && <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>alvo: {brl(s.preco_alvo, 2)}</span>}
                        {s.fonte && <span className="text-[10px] ml-auto" style={{ color: "var(--text-faint)" }}>{s.fonte}</span>}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Watchlist */}
              <section
                className="rounded-xl border"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Watchlist</h2>
                </div>
                {/* Adicionar */}
                <div className="px-5 py-3 border-b flex flex-wrap gap-2" style={{ borderColor: "var(--border-soft)" }}>
                  <input
                    value={wlTicker}
                    onChange={(e) => setWlTicker(e.target.value.toUpperCase())}
                    placeholder="Ticker"
                    className="rounded px-2 py-1.5 text-xs w-24 border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <input
                    value={wlAlvo}
                    onChange={(e) => setWlAlvo(e.target.value)}
                    placeholder="Preço alvo"
                    type="number"
                    className="rounded px-2 py-1.5 text-xs w-28 border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <input
                    value={wlObs}
                    onChange={(e) => setWlObs(e.target.value)}
                    placeholder="Obs (opcional)"
                    className="rounded px-2 py-1.5 text-xs flex-1 min-w-[120px] border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <button
                    onClick={addWatchlist}
                    disabled={wlAdding || !wlTicker.trim()}
                    className="rounded px-3 py-1.5 text-xs font-medium border disabled:opacity-40 transition"
                    style={{ whiteSpace: "nowrap", background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                  >
                    {wlAdding ? "…" : "+ Adicionar"}
                  </button>
                </div>
                {watchlist.length === 0 ? (
                  <p className="px-5 py-4 text-xs" style={{ color: "var(--text-faint)" }}>Watchlist vazia</p>
                ) : (
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {watchlist.map((w) => (
                      <div key={w.id} className="flex items-center gap-3 px-5 py-2.5 flex-wrap">
                        <Link href={`/ativos/${w.ticker}`} className="font-bold w-20 shrink-0" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{w.ticker}</Link>
                        {w.preco_alvo != null && <span className="text-xs" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>alvo: {brl(w.preco_alvo, 2)}</span>}
                        {w.sinal && (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded border"
                            style={{ whiteSpace: "nowrap", color: sinalColor(w.sinal), borderColor: sinalColor(w.sinal) }}
                          >
                            {w.sinal}
                          </span>
                        )}
                        {w.obs && <span className="text-[10px] flex-1 truncate" style={{ color: "var(--text-faint)" }}>{w.obs}</span>}
                        <button
                          onClick={() => removeWatchlist(w.id)}
                          className="ml-auto text-xs shrink-0 transition"
                          style={{ color: "var(--text-faint)" }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--negative)")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-faint)")}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Ranking todos ativos RV com sinal */}
              {sinais.length > 0 && (
                <section
                  className="rounded-xl border"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Sinais — todos os ativos ({sinais.length})</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="px-4 py-2 text-left">Ativo</th>
                          <th className="px-4 py-2 text-left">Sinal</th>
                          <th className="px-4 py-2 text-right">Preço</th>
                          <th className="px-4 py-2 text-right">Alvo</th>
                          <th className="px-4 py-2 text-left">Fonte</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sinais.map((s) => (
                          <tr
                            key={s.ticker}
                            className="border-b cursor-pointer transition"
                            style={{ borderColor: "var(--border-soft)" }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                            onClick={() => router.push(`/ativos/${s.ticker}`)}
                          >
                            <td className="px-4 py-2 font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{s.ticker}</td>
                            <td className="px-4 py-2">
                              <span className="font-semibold" style={{ color: sinalColor(s.sinal) }}>{s.sinal}</span>
                            </td>
                            <td className="px-4 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{s.preco_atual != null ? brl(s.preco_atual, 2) : "—"}</td>
                            <td className="px-4 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{s.preco_alvo != null ? brl(s.preco_alvo, 2) : "—"}</td>
                            <td className="px-4 py-2" style={{ color: "var(--text-muted)" }}>{s.fonte ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
