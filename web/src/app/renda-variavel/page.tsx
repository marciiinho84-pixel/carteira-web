"use client";

export const dynamic = "force-dynamic";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";
import PosicoesHeatmap, { type PosicaoHeat } from "./PosicoesHeatmap";
import TreemapSetorial, { type SetorDetalhado } from "./TreemapSetorial";
import PerformanceRVChart, { type Marcador } from "./PerformanceRVChart";
import RankingPnl from "./RankingPnl";

// ─── Tipos (endpoints já existentes) ─────────────────────────────────────────

interface Posicao {
  ticker: string;
  classe?: string;
  familia?: string;
  composite: string;
  qtd: number;
  valor_atual: number;
  pnl: number;
  pnl_pct: number;
  var_dia?: number | null;
  var_dia_pct?: number | null;
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

interface EvolucaoDiaria {
  data: string;
  twr_rv: number;
  ibov_acum: number;
  cdi_acum: number;
}

interface Evento {
  id: number;
  data: string;
  ativo: string;
  tipo: string;
  valor: number;
}

interface SinalItem {
  ticker: string;
  rsi?: number | null;
  rsi_label?: string;
  rsi_cor?: string;
  macd_sinal?: string;
  macd_label?: string;
  macd_cor?: string;
  mm_sinal?: string;
  mm_label?: string;
  mm_cor?: string;
  combinado: { label: string; cor: string; peso: number };
  tem_sinal_ativo?: boolean;
  erro?: string | null;
  fonte?: string;
}

interface WatchlistItem {
  id: number;
  ticker: string;
  preco_alvo?: number;
  stop_loss?: number | null;
  motivo?: string | null;
  cotacao_atual?: number | null;
  distancia_alvo_pct?: number | null;
  distancia_stop_pct?: number | null;
  sinal?: string;
}

interface DecisaoItem {
  id: number;
  data_decisao: string;
  ativo: string;
  acao: string;
  tese: string;
  revisao_em: string | null;
}

// ─── Formatação ───────────────────────────────────────────────────────────────

function brl(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function brlSinal(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  return (n >= 0 ? "+" : "") + brl(n, d);
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

const THRESH_ATENCAO = -0.15;
const THRESH_CRITICO = -0.25;

export default function RendaVariavel() {
  const router = useRouter();
  const [rv, setRv] = useState<CarteiraRV | null>(null);
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [evolucao, setEvolucao] = useState<EvolucaoDiaria[]>([]);
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [decisoes, setDecisoes] = useState<DecisaoItem[]>([]);
  const [sinais, setSinais] = useState<SinalItem[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [wlTicker, setWlTicker] = useState("");
  const [wlAlvo, setWlAlvo] = useState("");
  const [wlStop, setWlStop] = useState("");
  const [wlMotivo, setWlMotivo] = useState("");
  const [wlAdding, setWlAdding] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [rvData, posData, evoData, evData, decData, sinaisData, wlData] = await Promise.all([
        apiFetch<CarteiraRV>("/carteira-rv"),
        apiFetch<Posicao[]>("/posicoes"),
        apiFetch<EvolucaoDiaria[]>("/evolucao"),
        apiFetch<Evento[]>("/eventos").catch(() => []),
        apiFetch<DecisaoItem[]>("/decisoes").catch(() => []),
        apiFetch<SinalItem[]>("/sinais/carteira_rv").catch(() => []),
        apiFetch<WatchlistItem[]>("/watchlist").catch(() => []),
      ]);
      setRv(rvData);
      setPosicoes(posData);
      setEvolucao(evoData);
      setEventos(evData);
      setDecisoes(decData);
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
    if (!wlTicker.trim() || !wlAlvo) return;
    setWlAdding(true);
    try {
      await apiFetch("/watchlist", {
        method: "POST",
        body: JSON.stringify({
          ticker: wlTicker.trim().toUpperCase(),
          preco_alvo: Number(wlAlvo),
          stop_loss: wlStop ? Number(wlStop) : null,
          motivo: wlMotivo.trim() || null,
        }),
      });
      setWlTicker(""); setWlAlvo(""); setWlStop(""); setWlMotivo("");
      const wl = await apiFetch<WatchlistItem[]>("/watchlist");
      setWatchlist(wl);
    } catch { /* ignore */ }
    finally { setWlAdding(false); }
  }

  async function removeWatchlist(id: number) {
    await apiFetch(`/watchlist/${id}`, { method: "DELETE" }).catch(() => {});
    setWatchlist((prev) => prev.filter((w) => w.id !== id));
  }

  // ─── Agregação client-side (porta de get_carteira_rv_dados) ────────────────

  const dados = useMemo(() => {
    if (!rv) return null;

    const posicoesRV = posicoes.filter((p) => p.classe === "Renda Variável");
    const valorAtual = posicoesRV.reduce((s, p) => s + p.valor_atual, 0);
    const varDiaRv = posicoesRV.reduce((s, p) => s + (p.var_dia ?? 0), 0);
    const valOntem = valorAtual - varDiaRv;
    const varDiaPct = valOntem > 0 ? varDiaRv / valOntem : 0;

    const tickerSetor: Record<string, string> = {};
    for (const s of rv.setores) for (const t of s.ativos) tickerSetor[t] = s.setor;

    const rvComVar = posicoesRV.filter((p) => p.var_dia_pct != null);
    const maiorAlta = rvComVar.length ? rvComVar.reduce((a, b) => ((b.var_dia_pct ?? 0) > (a.var_dia_pct ?? 0) ? b : a)) : null;
    const maiorQueda = rvComVar.length ? rvComVar.reduce((a, b) => ((b.var_dia_pct ?? 0) < (a.var_dia_pct ?? 0) ? b : a)) : null;
    const maiorImpacto = posicoesRV.length
      ? posicoesRV.reduce((a, b) => (Math.abs(b.var_dia ?? 0) > Math.abs(a.var_dia ?? 0) ? b : a))
      : null;

    function mover(p: Posicao | null) {
      if (!p) return { ticker: "—", pct: 0, contrib_rs: 0 };
      return { ticker: p.ticker, pct: p.var_dia_pct ?? 0, contrib_rs: p.var_dia ?? 0 };
    }

    const posicoesOut: PosicaoHeat[] = posicoesRV.map((p) => ({
      ticker: p.ticker,
      setor: tickerSetor[p.ticker] ?? "Outros",
      valor_atual: p.valor_atual,
      pct_rv: valorAtual > 0 ? p.valor_atual / valorAtual : 0,
      variacao_dia_pct: p.var_dia_pct ?? 0,
      contrib_dia_rs: p.var_dia ?? 0,
      pl_total_pct: p.pnl_pct,
      pl_total_rs: p.pnl,
    }));

    const performanceSerie = evolucao.map((r) => ({
      time: r.data,
      twr_rv: Math.round(r.twr_rv * 100 * 10000) / 10000,
      ibov: Math.round(r.ibov_acum * 100 * 10000) / 10000,
      cdi: Math.round(r.cdi_acum * 100 * 10000) / 10000,
    }));

    const tickerValor: Record<string, number> = {};
    for (const p of posicoesRV) tickerValor[p.ticker] = p.valor_atual;
    const setoresDetalhados: SetorDetalhado[] = rv.setores.map((s) => ({
      nome: s.setor,
      valor_total: s.valor,
      pct_rv: s.pct_rv,
      ativos: [...s.ativos]
        .map((t) => ({ ticker: t, valor: tickerValor[t] ?? 0, pct_setor: s.valor > 0 ? (tickerValor[t] ?? 0) / s.valor : 0 }))
        .sort((a, b) => b.valor - a.valor),
    }));

    const rvTickers = new Set(posicoesRV.map((p) => p.ticker));
    const opsPorData: Record<string, { COMPRA: string[]; VENDA: string[] }> = {};
    for (const ev of eventos) {
      if (!rvTickers.has(ev.ativo)) continue;
      if (ev.tipo !== "COMPRA" && ev.tipo !== "VENDA") continue;
      if (!opsPorData[ev.data]) opsPorData[ev.data] = { COMPRA: [], VENDA: [] };
      opsPorData[ev.data][ev.tipo as "COMPRA" | "VENDA"].push(ev.ativo);
    }
    const markers: Marcador[] = [];
    for (const d of Object.keys(opsPorData).sort()) {
      for (const tipo of ["COMPRA", "VENDA"] as const) {
        const tkrs = opsPorData[d][tipo];
        if (tkrs.length) markers.push({ time: d, tipo, label: tkrs.length === 1 ? tkrs[0] : `${tkrs.length}x` });
      }
    }

    const decisoesRV = decisoes
      .filter((d) => rvTickers.has(d.ativo))
      .sort((a, b) => (b.data_decisao ?? "").localeCompare(a.data_decisao ?? ""))
      .slice(0, 5);

    return {
      valorAtual, varDiaRv, varDiaPct,
      movers: { maiorAlta: mover(maiorAlta), maiorQueda: mover(maiorQueda), maiorImpacto: mover(maiorImpacto) },
      posicoesOut, performanceSerie, setoresDetalhados, markers, decisoesRV,
      movimentosExtremos: posicoesRV.filter((p) => Math.abs(p.var_dia_pct ?? 0) > 0.05),
      emRisco: posicoesOut.filter((p) => p.pl_total_pct < THRESH_ATENCAO).sort((a, b) => a.pl_total_pct - b.pl_total_pct),
    };
  }, [rv, posicoes, evolucao, eventos, decisoes]);

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">
          <h1
            className="text-3xl font-semibold"
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
              className="rounded-xl border px-5 py-4 text-base"
              style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
            >
              {error}
            </div>
          )}

          {!loading && !error && rv && dados && (
            <>
              {/* Pulso do dia */}
              {dados.movimentosExtremos.length > 0 && (
                <div
                  className="rounded-xl border px-5 py-4 text-base"
                  style={{ borderColor: "rgba(201,134,43,0.35)", background: "rgba(201,134,43,0.08)", color: "var(--warning)" }}
                >
                  ⚡ Movimento expressivo hoje (&gt;5%):{" "}
                  <strong>{dados.movimentosExtremos.slice(0, 3).map((p) => p.ticker).join(", ")}</strong>
                </div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Carteira RV</p>
                  <p className="text-lg font-semibold mt-0.5" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(dados.valorAtual, 0)}</p>
                  <p className="text-xs mt-0.5" style={{ color: valColor(dados.varDiaRv) }}>{pct(dados.varDiaPct)} · {brlSinal(dados.varDiaRv, 0)} hoje</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Maior Alta</p>
                  <Link href={`/ativos/${dados.movers.maiorAlta.ticker}`} className="text-lg font-semibold mt-0.5 block hover:underline" style={{ color: green, fontFamily: "var(--font-plex-mono)" }}>{dados.movers.maiorAlta.ticker}</Link>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{pct(dados.movers.maiorAlta.pct)} · {brlSinal(dados.movers.maiorAlta.contrib_rs, 0)}</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Maior Queda</p>
                  <Link href={`/ativos/${dados.movers.maiorQueda.ticker}`} className="text-lg font-semibold mt-0.5 block hover:underline" style={{ color: red, fontFamily: "var(--font-plex-mono)" }}>{dados.movers.maiorQueda.ticker}</Link>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{pct(dados.movers.maiorQueda.pct)} · {brlSinal(dados.movers.maiorQueda.contrib_rs, 0)}</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Maior Impacto P&amp;L</p>
                  <Link href={`/ativos/${dados.movers.maiorImpacto.ticker}`} className="text-lg font-semibold mt-0.5 block hover:underline" style={{ color: valColor(dados.movers.maiorImpacto.contrib_rs), fontFamily: "var(--font-plex-mono)" }}>{dados.movers.maiorImpacto.ticker}</Link>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{brlSinal(dados.movers.maiorImpacto.contrib_rs, 0)} · {pct(dados.movers.maiorImpacto.pct)}</p>
                </div>
              </div>

              {/* Performance YTD */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {[
                  { label: "TWR RV YTD", value: pct(rv.twr_rv), color: valColor(rv.twr_rv) },
                  { label: "IBOV YTD", value: pct(rv.ibov_ytd), color: valColor(rv.ibov_ytd) },
                  { label: "S&P500 BRL YTD", value: pct(rv.sp500_brl_ytd), color: valColor(rv.sp500_brl_ytd) },
                ].map((k) => (
                  <div key={k.label} className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                    <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{k.label}</p>
                    <p className="text-xl font-bold mt-0.5" style={{ color: k.color, fontFamily: "var(--font-plex-mono)" }}>{k.value}</p>
                  </div>
                ))}
              </div>

              {/* Heatmap de Posições */}
              <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                <h2 className="text-base font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Mapa de Posições</h2>
                <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Selecione a dimensão de análise</p>
                {dados.posicoesOut.length > 0 ? (
                  <PosicoesHeatmap posicoes={dados.posicoesOut} />
                ) : (
                  <p className="text-base" style={{ color: "var(--text-muted)" }}>Sem posições de Renda Variável.</p>
                )}
              </section>

              {/* Ranking P&L + Painel de Risco */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <h2 className="text-base font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Ranking P&amp;L</h2>
                  <RankingPnl posicoes={dados.posicoesOut} />
                </section>

                <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <h2 className="text-base font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Painel de Risco</h2>
                  <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>Posições com P&amp;L abaixo de {pct(THRESH_ATENCAO)}</p>
                  {dados.emRisco.length > 0 ? (
                    <div className="space-y-2">
                      {dados.emRisco.map((p) => {
                        const critico = p.pl_total_pct < THRESH_CRITICO;
                        const cor = critico ? red : amber;
                        return (
                          <div key={p.ticker} className="rounded-lg px-3 py-2 border-l-4" style={{ borderLeftColor: cor, background: critico ? "rgba(180,68,44,0.06)" : "rgba(201,134,43,0.06)" }}>
                            <div className="flex items-center justify-between">
                              <Link href={`/ativos/${p.ticker}`} className="text-base font-bold hover:underline" style={{ color: "var(--text-primary)" }}>{p.ticker}</Link>
                              <span className="text-xs font-semibold px-2 py-0.5 rounded" style={{ color: cor, background: critico ? "rgba(180,68,44,0.15)" : "rgba(201,134,43,0.15)" }}>
                                {critico ? "CRÍTICO" : "ATENÇÃO"}
                              </span>
                            </div>
                            <p className="text-sm" style={{ color: cor, fontFamily: "var(--font-plex-mono)" }}>
                              {pct(p.pl_total_pct)} <span style={{ color: "var(--text-muted)", fontFamily: "inherit" }}>· {brl(Math.abs(p.pl_total_rs), 0)}</span>
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="rounded-lg px-4 py-4 text-center text-base" style={{ background: "rgba(74,124,89,0.08)", border: "1px solid rgba(74,124,89,0.25)", color: green }}>
                      ✓ Nenhuma posição abaixo de {pct(THRESH_ATENCAO)}
                    </div>
                  )}
                </section>
              </div>

              {/* Caixa / Liquidações */}
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-base font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Caixa e Liquidações (D+2)</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                  {[
                    { label: "Caixa atual (Geral)", value: brl(rv.caixa_atual, 0), color: green },
                    { label: "Vendas aguardando D+2 (já no caixa atual)", value: brl(rv.entrando_5d, 0), color: green },
                    { label: "Compras aguardando D+2 (já saiu do caixa)", value: brl(rv.saindo_5d, 0), color: red },
                    { label: "Disponível sem pendência", value: brl(rv.saldo_projetado, 0), color: valColor(rv.saldo_projetado) },
                  ].map((k) => (
                    <div key={k.label}>
                      <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{k.label}</p>
                      <p className="text-base font-bold mt-0.5" style={{ color: k.color, fontFamily: "var(--font-plex-mono)" }}>{k.value}</p>
                    </div>
                  ))}
                </div>
                {rv.pendentes.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-y text-xs uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="px-3 py-2 text-left">Liquidação</th>
                          <th className="px-3 py-2 text-left">Ativo</th>
                          <th className="px-3 py-2 text-left">Tipo</th>
                          <th className="px-3 py-2 text-right">Valor</th>
                          <th className="px-3 py-2 text-right">Impacto</th>
                          <th className="px-3 py-2 text-right">Disponível ao liquidar</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rv.pendentes.map((p, i) => (
                          <tr key={i} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                            <td className="px-3 py-2" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{p.liquidacao}</td>
                            <td className="px-3 py-2 font-bold">
                              <Link href={`/ativos/${p.ativo}`} className="hover:underline" style={{ color: "var(--purple-accent)" }}>{p.ativo}</Link>
                            </td>
                            <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{p.tipo}</td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.valor, 2)}</td>
                            <td className="px-3 py-2 text-right font-bold" style={{ color: valColor(p.impacto), fontFamily: "var(--font-plex-mono)" }}>
                              {p.impacto >= 0 ? "+" : ""}{brl(p.impacto, 2)}
                            </td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.saldo_projetado, 0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              {/* Performance RV vs Benchmarks */}
              <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                <h2 className="text-base font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Performance RV vs Benchmarks</h2>
                <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>TWR carteira · IBOV · CDI — marcadores de operações</p>
                {dados.performanceSerie.length > 0 ? (
                  <PerformanceRVChart
                    twrRv={dados.performanceSerie.map((r) => ({ time: r.time, value: r.twr_rv }))}
                    ibov={dados.performanceSerie.map((r) => ({ time: r.time, value: r.ibov }))}
                    cdi={dados.performanceSerie.map((r) => ({ time: r.time, value: r.cdi }))}
                    markers={dados.markers}
                  />
                ) : (
                  <p className="text-base" style={{ color: "var(--text-muted)" }}>Dados de evolução indisponíveis.</p>
                )}
              </section>

              {/* Análise Setorial (treemap) */}
              {dados.setoresDetalhados.length > 0 && (
                <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <h2 className="text-base font-semibold mb-1" style={{ color: "var(--text-primary)" }}>Análise Setorial</h2>
                  <p className="text-sm mb-3" style={{ color: "var(--text-muted)" }}>setor → ativos · tamanho = valor alocado</p>
                  <TreemapSetorial setores={dados.setoresDetalhados} />
                </section>
              )}

              {/* Watchlist */}
              <section
                className="rounded-xl border"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Watchlist</h2>
                </div>
                {/* Adicionar */}
                <div className="px-5 py-3 border-b flex flex-wrap gap-2" style={{ borderColor: "var(--border-soft)" }}>
                  <input
                    value={wlTicker}
                    onChange={(e) => setWlTicker(e.target.value.toUpperCase())}
                    placeholder="Ticker"
                    className="rounded px-2 py-1.5 text-sm w-24 border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <input
                    value={wlAlvo}
                    onChange={(e) => setWlAlvo(e.target.value)}
                    placeholder="Preço alvo"
                    type="number"
                    className="rounded px-2 py-1.5 text-sm w-28 border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <input
                    value={wlStop}
                    onChange={(e) => setWlStop(e.target.value)}
                    placeholder="Stop-loss (opc.)"
                    type="number"
                    className="rounded px-2 py-1.5 text-sm w-28 border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <input
                    value={wlMotivo}
                    onChange={(e) => setWlMotivo(e.target.value)}
                    placeholder="Motivo / tese (opcional)"
                    className="rounded px-2 py-1.5 text-sm flex-1 min-w-[120px] border focus:outline-none"
                    style={{ background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" }}
                  />
                  <button
                    onClick={addWatchlist}
                    disabled={wlAdding || !wlTicker.trim() || !wlAlvo}
                    className="rounded px-3 py-2 text-sm font-medium border disabled:opacity-40 transition"
                    style={{ whiteSpace: "nowrap", background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                  >
                    {wlAdding ? "…" : "+ Adicionar"}
                  </button>
                </div>
                {watchlist.length === 0 ? (
                  <p className="px-5 py-4 text-sm" style={{ color: "var(--text-faint)" }}>Watchlist vazia</p>
                ) : (
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {watchlist.map((w) => (
                      <div key={w.id} className="flex items-center gap-3 px-5 py-3 flex-wrap">
                        <Link href={`/ativos/${w.ticker}`} className="font-bold w-20 shrink-0" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{w.ticker}</Link>
                        {w.preco_alvo != null && <span className="text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>alvo: {brl(w.preco_alvo, 2)}</span>}
                        {w.stop_loss != null && <span className="text-sm" style={{ color: "var(--negative)", fontFamily: "var(--font-plex-mono)" }}>stop: {brl(w.stop_loss, 2)}</span>}
                        {w.cotacao_atual != null && <span className="text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>cot.: {brl(w.cotacao_atual, 2)}</span>}
                        {w.sinal && (
                          <span
                            className="text-xs px-1.5 py-0.5 rounded border"
                            style={{ whiteSpace: "nowrap", color: sinalColor(w.sinal), borderColor: sinalColor(w.sinal) }}
                          >
                            {w.sinal}
                          </span>
                        )}
                        {w.motivo && <span className="text-xs flex-1 truncate" style={{ color: "var(--text-faint)" }}>{w.motivo}</span>}
                        <button
                          onClick={() => removeWatchlist(w.id)}
                          className="ml-auto text-sm shrink-0 transition"
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
                    <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>{sinais.length} {sinais.length === 1 ? "Sinal Ativo" : "Sinais Ativos"}</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-xs uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="px-4 py-2 text-left">Ativo</th>
                          <th className="px-4 py-2 text-left">Sinal</th>
                          <th className="px-4 py-2 text-left">RSI</th>
                          <th className="px-4 py-2 text-left">MACD</th>
                          <th className="px-4 py-2 text-left">MM</th>
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
                            <td className="px-4 py-2.5">
                              <span className="font-semibold" style={{ color: s.combinado.cor }}>{s.combinado.label}</span>
                            </td>
                            <td className="px-4 py-2.5" style={{ color: s.rsi_cor ?? "var(--text-muted)" }}>{s.rsi_label ?? "—"}</td>
                            <td className="px-4 py-2.5" style={{ color: s.macd_cor ?? "var(--text-muted)" }}>{s.macd_label ?? "—"}</td>
                            <td className="px-4 py-2.5" style={{ color: s.mm_cor ?? "var(--text-muted)" }}>{s.mm_label ?? "—"}</td>
                            <td className="px-4 py-2.5" style={{ color: "var(--text-muted)" }}>{s.fonte ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {/* Contexto do Diário */}
              <section
                className="rounded-xl border"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                  <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>Contexto do Diário</h2>
                </div>
                {dados.decisoesRV.length > 0 ? (
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {dados.decisoesRV.map((d) => (
                      <div key={d.id} className="px-5 py-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs" style={{ color: "var(--text-faint)" }}>{d.data_decisao}</span>
                          <Link href={`/ativos/${d.ativo}`} className="text-sm font-bold hover:underline" style={{ color: "var(--text-primary)" }}>{d.ativo}</Link>
                          <span
                            className="text-xs font-semibold px-1.5 py-0.5 rounded"
                            style={{ color: sinalColor(d.acao), background: `color-mix(in srgb, ${sinalColor(d.acao)} 15%, transparent)` }}
                          >
                            {d.acao}
                          </span>
                        </div>
                        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                          {d.tese.length > 160 ? d.tese.slice(0, 160) + "…" : d.tese}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="px-5 py-4 text-sm" style={{ color: "var(--text-faint)" }}>Nenhuma decisão registrada para ativos de Renda Variável ainda.</p>
                )}
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
