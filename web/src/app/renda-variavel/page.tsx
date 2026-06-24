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
const green = "#26A69A", red = "#EF5350", amber = "#F59E0B";
const valColor = (n: number | null | undefined) => (n == null ? "#D1D4DC" : n >= 0 ? green : red);

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
  const totalRV = rv?.setores.reduce((s, sec) => s + sec.valor, 0) ?? 0;

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 space-y-4">
          <h1 className="text-lg font-bold text-white">Renda Variável</h1>

          {loading && <div className="animate-pulse space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-xl bg-[#1A1D27]" />)}</div>}
          {error && <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>}

          {!loading && !error && rv && (
            <>
              {/* Performance */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { label: "TWR RV YTD", value: pct(rv.twr_rv), color: valColor(rv.twr_rv) },
                  { label: "IBOV YTD", value: pct(rv.ibov_ytd), color: valColor(rv.ibov_ytd) },
                  { label: "S&P500 BRL YTD", value: pct(rv.sp500_brl_ytd), color: valColor(rv.sp500_brl_ytd) },
                ].map((k) => (
                  <div key={k.label} className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
                    <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">{k.label}</p>
                    <p className="text-base font-bold font-mono mt-0.5" style={{ color: k.color }}>{k.value}</p>
                  </div>
                ))}
              </div>

              {/* Caixa / Liquidações */}
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                <h2 className="text-sm font-semibold text-white mb-3">Caixa e Liquidações (D+2)</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  {[
                    { label: "Caixa atual (CAIXA FIC)", value: brl(rv.caixa_atual, 0), color: green },
                    { label: "Entrando (5 DU)", value: brl(rv.entrando_5d, 0), color: green },
                    { label: "Saindo (5 DU)", value: brl(rv.saindo_5d, 0), color: red },
                    { label: "Saldo projetado", value: brl(rv.saldo_projetado, 0), color: valColor(rv.saldo_projetado) },
                  ].map((k) => (
                    <div key={k.label}>
                      <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">{k.label}</p>
                      <p className="text-sm font-bold font-mono mt-0.5" style={{ color: k.color }}>{k.value}</p>
                    </div>
                  ))}
                </div>
                {rv.pendentes.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-y border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
                          <th className="px-3 py-1.5 text-left">Liquidação</th>
                          <th className="px-3 py-1.5 text-left">Ativo</th>
                          <th className="px-3 py-1.5 text-left">Tipo</th>
                          <th className="px-3 py-1.5 text-right">Valor</th>
                          <th className="px-3 py-1.5 text-right">Impacto</th>
                          <th className="px-3 py-1.5 text-right">Saldo proj.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rv.pendentes.map((p, i) => (
                          <tr key={i} className="border-b border-[#2A2D3A]">
                            <td className="px-3 py-1.5 font-mono">{p.liquidacao}</td>
                            <td className="px-3 py-1.5 font-bold">
                              <Link href={`/ativos/${p.ativo}`} className="text-[#6366F1] hover:underline">{p.ativo}</Link>
                            </td>
                            <td className="px-3 py-1.5 text-[#6b7280]">{p.tipo}</td>
                            <td className="px-3 py-1.5 text-right font-mono">{brl(p.valor, 2)}</td>
                            <td className="px-3 py-1.5 text-right font-mono font-bold" style={{ color: valColor(p.impacto) }}>
                              {p.impacto >= 0 ? "+" : ""}{brl(p.impacto, 2)}
                            </td>
                            <td className="px-3 py-1.5 text-right font-mono">{brl(p.saldo_projetado, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Distribuição Setorial */}
              {rv.setores.length > 0 && (
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                  <h2 className="text-sm font-semibold text-white mb-3">Distribuição Setorial</h2>
                  <div className="space-y-2">
                    {rv.setores.map((s) => (
                      <div key={s.setor}>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-[#D1D4DC] font-medium">{s.setor}</span>
                          <span className="font-mono text-[#6b7280]">
                            {(s.pct_rv * 100).toFixed(1)}% · {brl(s.valor, 0)} · {s.n_ativos} ativo{s.n_ativos !== 1 ? "s" : ""}
                          </span>
                        </div>
                        <div className="h-2 rounded-full bg-[#2A2D3A] overflow-hidden">
                          <div className="h-full rounded-full bg-[#26A69A]" style={{ width: `${(s.pct_rv * 100).toFixed(1)}%` }} />
                        </div>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {s.ativos.map((t) => (
                            <Link key={t} href={`/ativos/${t}`} className="text-[9px] text-[#6366F1] hover:underline border border-[#2A2D3A] rounded px-1 py-0.5">{t}</Link>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Sinais ativos */}
              {sinaiesAtivos.length > 0 && (
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                  <div className="px-5 py-3 border-b border-[#2A2D3A]">
                    <h2 className="text-sm font-semibold text-white">{sinaiesAtivos.length} Sinal{sinaiesAtivos.length !== 1 ? "is" : ""} Ativo{sinaiesAtivos.length !== 1 ? "s" : ""}</h2>
                  </div>
                  <div className="divide-y divide-[#2A2D3A]">
                    {sinaiesAtivos.map((s) => (
                      <div key={s.ticker} className="flex items-center gap-4 px-5 py-2.5">
                        <Link href={`/ativos/${s.ticker}`} className="font-bold text-white hover:text-[#26A69A] w-20 shrink-0">{s.ticker}</Link>
                        <span className="text-xs px-2 py-0.5 rounded font-medium border"
                          style={{ color: s.sinal === "COMPRA" ? green : s.sinal === "VENDA" ? red : amber, borderColor: s.sinal === "COMPRA" ? green : s.sinal === "VENDA" ? red : amber }}>
                          {s.sinal}
                        </span>
                        {s.preco_atual != null && <span className="text-xs font-mono text-[#6b7280]">atual: {brl(s.preco_atual, 2)}</span>}
                        {s.preco_alvo != null && <span className="text-xs font-mono text-[#6b7280]">alvo: {brl(s.preco_alvo, 2)}</span>}
                        {s.fonte && <span className="text-[10px] text-[#6b7280] ml-auto">{s.fonte}</span>}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Watchlist */}
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                <div className="px-5 py-3 border-b border-[#2A2D3A]">
                  <h2 className="text-sm font-semibold text-white">Watchlist</h2>
                </div>
                {/* Adicionar */}
                <div className="px-5 py-3 border-b border-[#2A2D3A] flex flex-wrap gap-2">
                  <input value={wlTicker} onChange={(e) => setWlTicker(e.target.value.toUpperCase())}
                    placeholder="Ticker" className="rounded bg-[#0F1117] border border-[#2A2D3A] px-2 py-1.5 text-xs w-24 text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]" />
                  <input value={wlAlvo} onChange={(e) => setWlAlvo(e.target.value)}
                    placeholder="Preço alvo" type="number" className="rounded bg-[#0F1117] border border-[#2A2D3A] px-2 py-1.5 text-xs w-28 text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]" />
                  <input value={wlObs} onChange={(e) => setWlObs(e.target.value)}
                    placeholder="Obs (opcional)" className="rounded bg-[#0F1117] border border-[#2A2D3A] px-2 py-1.5 text-xs flex-1 min-w-[120px] text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]" />
                  <button onClick={addWatchlist} disabled={wlAdding || !wlTicker.trim()}
                    className="rounded px-3 py-1.5 text-xs font-medium bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40 hover:bg-[#26A69A]/30 disabled:opacity-40 transition">
                    {wlAdding ? "…" : "+ Adicionar"}
                  </button>
                </div>
                {watchlist.length === 0 ? (
                  <p className="px-5 py-4 text-xs text-[#6b7280]">Watchlist vazia</p>
                ) : (
                  <div className="divide-y divide-[#2A2D3A]">
                    {watchlist.map((w) => (
                      <div key={w.id} className="flex items-center gap-3 px-5 py-2.5">
                        <Link href={`/ativos/${w.ticker}`} className="font-bold text-white hover:text-[#26A69A] w-20 shrink-0">{w.ticker}</Link>
                        {w.preco_alvo != null && <span className="text-xs font-mono text-[#6b7280]">alvo: {brl(w.preco_alvo, 2)}</span>}
                        {w.sinal && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded border"
                            style={{ color: w.sinal === "COMPRA" ? green : w.sinal === "VENDA" ? red : amber, borderColor: w.sinal === "COMPRA" ? green : w.sinal === "VENDA" ? red : amber }}>
                            {w.sinal}
                          </span>
                        )}
                        {w.obs && <span className="text-[10px] text-[#6b7280] flex-1 truncate">{w.obs}</span>}
                        <button onClick={() => removeWatchlist(w.id)}
                          className="ml-auto text-[#6b7280] hover:text-[#EF5350] transition text-xs shrink-0">✕</button>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Ranking todos ativos RV com sinal */}
              {sinais.length > 0 && (
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                  <div className="px-5 py-3 border-b border-[#2A2D3A]">
                    <h2 className="text-sm font-semibold text-white">Sinais — todos os ativos ({sinais.length})</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
                          <th className="px-4 py-2 text-left">Ativo</th>
                          <th className="px-4 py-2 text-left">Sinal</th>
                          <th className="px-4 py-2 text-right">Preço</th>
                          <th className="px-4 py-2 text-right">Alvo</th>
                          <th className="px-4 py-2 text-left">Fonte</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sinais.map((s) => (
                          <tr key={s.ticker} className="border-b border-[#2A2D3A] hover:bg-[#2A2D3A]/30 cursor-pointer"
                            onClick={() => router.push(`/ativos/${s.ticker}`)}>
                            <td className="px-4 py-2 font-bold text-white">{s.ticker}</td>
                            <td className="px-4 py-2">
                              <span className="font-medium" style={{ color: s.sinal === "COMPRA" ? green : s.sinal === "VENDA" ? red : amber }}>{s.sinal}</span>
                            </td>
                            <td className="px-4 py-2 text-right font-mono">{s.preco_atual != null ? brl(s.preco_atual, 2) : "—"}</td>
                            <td className="px-4 py-2 text-right font-mono">{s.preco_alvo != null ? brl(s.preco_alvo, 2) : "—"}</td>
                            <td className="px-4 py-2 text-[#6b7280]">{s.fonte ?? "—"}</td>
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
