"use client";

export const dynamic = "force-dynamic";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";

interface Posicao {
  ticker: string;
  classe?: string;
  familia?: string;
  composite: string;
  qtd: number;
  custo_total: number;
  custo_medio: number;
  preco_atual?: number;
  valor_atual: number;
  pnl: number;
  pnl_pct: number;
  var_dia?: number;
  var_dia_pct?: number;
  yield_12m?: number;
  bloco_ips?: string;
}

const BLOCOS = ["Todos", "SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];
const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

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
const pnlColor = (v: number) => (v >= 0 ? "var(--positive)" : "var(--negative)");

type SortKey =
  | "ticker" | "classe" | "familia" | "composite" | "bloco_ips" | "qtd"
  | "custo_medio" | "custo_total" | "preco_atual" | "var_dia_pct"
  | "valor_atual" | "pnl" | "pnl_pct" | "yield_12m" | "peso";

const NUMERIC_KEYS = new Set<SortKey>([
  "qtd", "custo_medio", "custo_total", "preco_atual", "var_dia_pct",
  "valor_atual", "pnl", "pnl_pct", "yield_12m", "peso",
]);

interface ColDef {
  key: SortKey;
  label: string;
  align: "left" | "right";
}

const COLS: ColDef[] = [
  { key: "ticker", label: "Ativo", align: "left" },
  { key: "classe", label: "Classe", align: "left" },
  { key: "familia", label: "Família", align: "left" },
  { key: "composite", label: "Composite", align: "left" },
  { key: "bloco_ips", label: "Bloco IPS", align: "left" },
  { key: "qtd", label: "Qtd", align: "right" },
  { key: "custo_medio", label: "Custo Médio", align: "right" },
  { key: "custo_total", label: "Custo Total", align: "right" },
  { key: "preco_atual", label: "Preço Atual", align: "right" },
  { key: "var_dia_pct", label: "Var. dia", align: "right" },
  { key: "valor_atual", label: "Valor Atual", align: "right" },
  { key: "pnl", label: "P&L R$", align: "right" },
  { key: "pnl_pct", label: "P&L %", align: "right" },
  { key: "yield_12m", label: "Yield 12m", align: "right" },
  { key: "peso", label: "Peso %", align: "right" },
];

function csvEscape(v: string | number): string {
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function togglePill(set: Set<string>, v: string): Set<string> {
  const next = new Set(set);
  if (next.has(v)) next.delete(v); else next.add(v);
  return next;
}

export default function Posicoes() {
  const router = useRouter();
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtroBloco, setFiltroBloco] = useState("Todos");
  const [filtroFamilias, setFiltroFamilias] = useState<Set<string>>(new Set());
  const [filtroComposites, setFiltroComposites] = useState<Set<string>>(new Set());
  const [busca, setBusca] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("valor_atual");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const data = await apiFetch<Posicao[]>("/posicoes");
        setPosicoes(data.filter((p) => (p.valor_atual ?? 0) > 0));
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Erro ao carregar posições";
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
  }, [router]);

  const familiasDisponiveis = useMemo(
    () => Array.from(new Set(posicoes.map((p) => p.familia).filter((f): f is string => !!f))).sort(),
    [posicoes],
  );
  const compositesDisponiveis = useMemo(
    () => Array.from(new Set(posicoes.map((p) => p.composite).filter((c): c is string => !!c))).sort(),
    [posicoes],
  );

  const filtered = useMemo(() => {
    const buscaUpper = busca.trim().toUpperCase();
    return posicoes.filter((p) => {
      if (filtroBloco !== "Todos" && (p.bloco_ips ?? "FORA_IPS") !== filtroBloco) return false;
      if (filtroFamilias.size > 0 && !filtroFamilias.has(p.familia ?? "")) return false;
      if (filtroComposites.size > 0 && !filtroComposites.has(p.composite)) return false;
      if (buscaUpper && !p.ticker.toUpperCase().includes(buscaUpper)) return false;
      return true;
    });
  }, [posicoes, filtroBloco, filtroFamilias, filtroComposites, busca]);

  const totalCusto = filtered.reduce((s, p) => s + (p.custo_total ?? 0), 0);
  const totalValor = filtered.reduce((s, p) => s + (p.valor_atual ?? 0), 0);
  const totalPnl = filtered.reduce((s, p) => s + (p.pnl ?? 0), 0);

  const resumoComposite = useMemo(() => {
    const grupos: Record<string, { custo: number; valor: number; pnl: number; n: number }> = {};
    for (const p of filtered) {
      const g = grupos[p.composite] ?? { custo: 0, valor: 0, pnl: 0, n: 0 };
      g.custo += p.custo_total ?? 0;
      g.valor += p.valor_atual ?? 0;
      g.pnl += p.pnl ?? 0;
      g.n += 1;
      grupos[p.composite] = g;
    }
    return Object.entries(grupos).sort((a, b) => b[1].valor - a[1].valor);
  }, [filtered]);

  function acessor(p: Posicao, key: SortKey): string | number {
    switch (key) {
      case "ticker": return p.ticker;
      case "classe": return p.classe ?? "";
      case "familia": return p.familia ?? "";
      case "composite": return p.composite ?? "";
      case "bloco_ips": return p.bloco_ips ?? "";
      case "qtd": return p.qtd ?? 0;
      case "custo_medio": return p.custo_medio ?? 0;
      case "custo_total": return p.custo_total ?? 0;
      case "preco_atual": return p.preco_atual ?? 0;
      case "var_dia_pct": return p.var_dia_pct ?? 0;
      case "valor_atual": return p.valor_atual ?? 0;
      case "pnl": return p.pnl ?? 0;
      case "pnl_pct": return p.pnl_pct ?? 0;
      case "yield_12m": return p.yield_12m ?? 0;
      case "peso": return totalValor > 0 ? p.valor_atual / totalValor : 0;
    }
  }

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const va = acessor(a, sortKey);
      const vb = acessor(b, sortKey);
      let cmp: number;
      if (typeof va === "string" || typeof vb === "string") {
        cmp = String(va).localeCompare(String(vb), "pt-BR");
      } else {
        cmp = va - vb;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, sortKey, sortDir, totalValor]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(NUMERIC_KEYS.has(key) ? "desc" : "asc");
    }
  }

  function exportarCSV() {
    const headers = COLS.map((c) => c.label);
    const linhas = sorted.map((p) => {
      const peso = totalValor > 0 ? (p.valor_atual / totalValor) * 100 : 0;
      return [
        p.ticker, p.classe ?? "", p.familia ?? "", p.composite ?? "", p.bloco_ips ?? "",
        p.qtd, p.custo_medio, p.custo_total, p.preco_atual ?? "",
        p.var_dia_pct != null ? (p.var_dia_pct * 100).toFixed(2) : "",
        p.valor_atual, p.pnl, (p.pnl_pct * 100).toFixed(2),
        p.yield_12m != null ? (p.yield_12m * 100).toFixed(2) : "",
        peso.toFixed(2),
      ];
    });
    const csv = [headers, ...linhas]
      .map((row) => row.map((v) => csvEscape(v)).join(","))
      .join("\n");
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `posicoes_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <span style={{ opacity: 0.25 }}>↕</span>;
    return <span>{sortDir === "asc" ? "▲" : "▼"}</span>;
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">

          <div className="flex items-center justify-between flex-wrap gap-2">
            <h1
              className="text-3xl font-semibold"
              style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
            >
              Posições
            </h1>
            <button
              onClick={exportarCSV}
              disabled={sorted.length === 0}
              className="rounded-lg px-3.5 py-1.5 text-sm font-medium border disabled:opacity-40 transition"
              style={{ background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
            >
              ⬇ Exportar CSV
            </button>
          </div>

          {/* Filtros */}
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2 items-center">
              <span className="text-xs uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Bloco IPS:</span>
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

            {compositesDisponiveis.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-xs uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Composite:</span>
                {compositesDisponiveis.map((c) => {
                  const active = filtroComposites.has(c);
                  return (
                    <button
                      key={c}
                      onClick={() => setFiltroComposites((s) => togglePill(s, c))}
                      className="px-3.5 py-1.5 rounded-full text-xs font-semibold transition border"
                      style={{
                        whiteSpace: "nowrap",
                        borderColor: active ? "var(--purple-accent)" : "var(--border)",
                        color: active ? "var(--purple-accent)" : "var(--text-muted)",
                        background: active ? "rgba(108,99,196,0.12)" : "transparent",
                      }}
                    >
                      {c}
                    </button>
                  );
                })}
                {filtroComposites.size > 0 && (
                  <button
                    onClick={() => setFiltroComposites(new Set())}
                    className="text-xs underline"
                    style={{ color: "var(--text-faint)" }}
                  >
                    limpar
                  </button>
                )}
              </div>
            )}

            {familiasDisponiveis.length > 0 && (
              <div className="flex flex-wrap gap-2 items-center">
                <span className="text-xs uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>Família:</span>
                {familiasDisponiveis.map((f) => {
                  const active = filtroFamilias.has(f);
                  return (
                    <button
                      key={f}
                      onClick={() => setFiltroFamilias((s) => togglePill(s, f))}
                      className="px-3.5 py-1.5 rounded-full text-xs font-semibold transition border"
                      style={{
                        whiteSpace: "nowrap",
                        borderColor: active ? "var(--warning)" : "var(--border)",
                        color: active ? "var(--warning)" : "var(--text-muted)",
                        background: active ? "rgba(201,134,43,0.12)" : "transparent",
                      }}
                    >
                      {f}
                    </button>
                  );
                })}
                {filtroFamilias.size > 0 && (
                  <button
                    onClick={() => setFiltroFamilias(new Set())}
                    className="text-xs underline"
                    style={{ color: "var(--text-faint)" }}
                  >
                    limpar
                  </button>
                )}
              </div>
            )}

            <div className="flex items-center gap-2">
              <input
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                placeholder="Buscar ticker…"
                className="rounded-lg px-3 py-1.5 text-sm border focus:outline-none w-48"
                style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)" }}
              />
              {busca && (
                <button onClick={() => setBusca("")} className="text-xs underline" style={{ color: "var(--text-faint)" }}>
                  limpar
                </button>
              )}
            </div>
          </div>

          {loading && (
            <div className="animate-pulse space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-10 rounded-lg" style={{ background: "var(--bg-card)" }} />
              ))}
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
              {/* KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Ativos exibidos</p>
                  <p className="text-lg font-semibold mt-0.5" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{filtered.length}</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Custo Total</p>
                  <p className="text-lg font-semibold mt-0.5" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(totalCusto)}</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Valor Atual</p>
                  <p className="text-lg font-semibold mt-0.5" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(totalValor)}</p>
                </div>
                <div className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <p className="text-xs uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>P&amp;L Total</p>
                  <p className="text-lg font-semibold mt-0.5" style={{ color: pnlColor(totalPnl), fontFamily: "var(--font-plex-mono)" }}>{brl(totalPnl)}</p>
                  <p className="text-xs mt-0.5" style={{ color: pnlColor(totalPnl) }}>{totalCusto > 0 ? pct(totalPnl / totalCusto) : "—"}</p>
                </div>
              </div>

              {/* Resumo por Composite */}
              {resumoComposite.length > 0 && (
                <section className="rounded-xl border px-5 py-4" style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}>
                  <h2 className="text-base font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Resumo por Composite</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {resumoComposite.map(([comp, g]) => (
                      <div key={comp} className="rounded-lg px-4 py-3 border" style={{ borderColor: "var(--border-soft)" }}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                            {comp === "FUNCEF" ? "🏛️ " : "💼 "}{comp}
                          </span>
                          <span className="text-xs" style={{ color: "var(--text-faint)" }}>{g.n} ativos</span>
                        </div>
                        <p className="text-lg font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(g.valor)}</p>
                        <p className="text-sm" style={{ color: pnlColor(g.pnl), fontFamily: "var(--font-plex-mono)" }}>
                          P&amp;L: {brl(g.pnl)} {g.custo > 0 && `(${pct(g.pnl / g.custo)})`}
                        </p>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs mt-3" style={{ color: "var(--text-faint)" }}>
                    Peso % na tabela abaixo é relativo aos ativos exibidos — filtre por Composite pra ver o peso dentro de Gerida ou FUNCEF isoladamente.
                  </p>
                </section>
              )}

              {/* Tabela principal */}
              <div
                className="rounded-xl border overflow-hidden"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr
                        className="border-b text-xs uppercase tracking-wider"
                        style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}
                      >
                        {COLS.map((c) => (
                          <th
                            key={c.key}
                            onClick={() => toggleSort(c.key)}
                            className={`px-4 py-2.5 select-none cursor-pointer transition ${c.align === "right" ? "text-right" : "text-left"}`}
                            style={{ color: sortKey === c.key ? "var(--accent-strong)" : "var(--text-faint)" }}
                          >
                            <span className="inline-flex items-center gap-1" style={{ flexDirection: c.align === "right" ? "row-reverse" : "row" }}>
                              {c.label} <SortIcon col={c.key} />
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sorted.map((p) => {
                        const peso = totalValor > 0 ? (p.valor_atual / totalValor) * 100 : 0;
                        const alertaPnl = p.pnl_pct < -0.15;
                        return (
                          <tr
                            key={p.ticker}
                            className="border-b cursor-pointer transition"
                            style={{ borderColor: "var(--border-soft)" }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                            onClick={() => router.push(`/ativos/${p.ticker}`)}
                          >
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2">
                                <span className="font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{p.ticker}</span>
                                {alertaPnl && (
                                  <span
                                    className="text-xs rounded px-1.5 py-0.5 border"
                                    style={{ whiteSpace: "nowrap", color: "var(--negative)", background: "rgba(180,68,44,0.10)", borderColor: "rgba(180,68,44,0.25)" }}
                                  >
                                    -15%+
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-sm" style={{ color: "var(--text-muted)" }}>{p.classe ?? "—"}</td>
                            <td className="px-4 py-2.5 text-sm" style={{ color: "var(--text-muted)", whiteSpace: "nowrap" }}>{p.familia ?? "—"}</td>
                            <td className="px-4 py-2.5 text-sm" style={{ color: "var(--text-muted)" }}>{p.composite ?? "—"}</td>
                            <td className="px-4 py-2.5 text-sm">
                              {p.bloco_ips ? (
                                <Link
                                  href={`/blocos/${p.bloco_ips}`}
                                  onClick={(e) => e.stopPropagation()}
                                  className="hover:underline"
                                  style={{ color: "var(--purple-accent)", whiteSpace: "nowrap" }}
                                >
                                  {BLOCO_LABEL[p.bloco_ips] ?? p.bloco_ips}
                                </Link>
                              ) : (
                                <span style={{ color: "var(--text-faint)" }}>—</span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{fmt2(p.qtd)}</td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.custo_medio)}</td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.custo_total)}</td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{fmt2(p.preco_atual)}</td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: p.var_dia_pct != null ? pnlColor(p.var_dia_pct) : "var(--text-faint)", fontFamily: "var(--font-plex-mono)" }}>
                              {p.var_dia_pct != null ? (
                                <>
                                  {p.var_dia != null && (p.var_dia >= 0 ? "↑" : "↓")}{brl(Math.abs(p.var_dia ?? 0))} ({pct(p.var_dia_pct)})
                                </>
                              ) : "—"}
                            </td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.valor_atual)}</td>
                            <td className="px-4 py-2.5 text-right text-sm font-semibold" style={{ color: pnlColor(p.pnl), fontFamily: "var(--font-plex-mono)" }}>{brl(p.pnl)}</td>
                            <td className="px-4 py-2.5 text-right text-sm font-semibold" style={{ color: pnlColor(p.pnl_pct), fontFamily: "var(--font-plex-mono)" }}>{pct(p.pnl_pct)}</td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>
                              {p.yield_12m ? pct(p.yield_12m) : "—"}
                            </td>
                            <td className="px-4 py-2.5 text-right text-sm" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{peso.toFixed(1)}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="border-t text-sm font-bold" style={{ borderColor: "var(--border)", background: "var(--bg-card-alt)" }}>
                        <td className="px-4 py-2.5" style={{ color: "var(--text-primary)" }} colSpan={7}>Total ({filtered.length} ativos)</td>
                        <td className="px-4 py-2.5 text-right" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(totalCusto)}</td>
                        <td className="px-4 py-2.5" />
                        <td className="px-4 py-2.5" />
                        <td className="px-4 py-2.5 text-right" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(totalValor)}</td>
                        <td className="px-4 py-2.5 text-right" style={{ color: pnlColor(totalPnl), fontFamily: "var(--font-plex-mono)" }}>{brl(totalPnl)}</td>
                        <td className="px-4 py-2.5 text-right" style={{ color: pnlColor(totalPnl), fontFamily: "var(--font-plex-mono)" }}>
                          {totalCusto > 0 ? pct(totalPnl / totalCusto) : "—"}
                        </td>
                        <td className="px-4 py-2.5" />
                        <td className="px-4 py-2.5 text-right" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>100%</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
