"use client";

export const dynamic = "force-dynamic";

import React, { useEffect, useState, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";

interface EvolucaoDiaria {
  data: string;
  patrimonio_gerida: number;
  patrimonio_funcef: number;
  patrimonio_total: number;
  patrimonio_rv: number;
  twr_gerida: number;
  twr_total: number;
  twr_rv: number;
  cdi_acum: number;
  ipca_acum: number;
  ibov_acum: number;
  drawdown?: number | null;
}

function brl(n: number): string {
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function pct(n: number, digits = 2): string {
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(digits) + "%";
}

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

type Filtro = "3M" | "6M" | "YTD" | "1A" | "Tudo";

function filtrarSerie(serie: EvolucaoDiaria[], filtro: Filtro): EvolucaoDiaria[] {
  if (!serie.length) return serie;
  const hoje = new Date();
  let from: Date | null = null;
  if (filtro === "3M") { from = new Date(hoje); from.setMonth(from.getMonth() - 3); }
  else if (filtro === "6M") { from = new Date(hoje); from.setMonth(from.getMonth() - 6); }
  else if (filtro === "1A") { from = new Date(hoje); from.setFullYear(from.getFullYear() - 1); }
  else if (filtro === "YTD") { from = new Date(hoje.getFullYear(), 0, 1); }
  if (!from) return serie;
  const fromStr = from.toISOString().slice(0, 10);
  return serie.filter((d) => d.data >= fromStr);
}

function agruparMensal(serie: EvolucaoDiaria[]): {
  mes: string;
  patrimonio: number;
  aporte: number;
  variacao: number;
  twr_mes: number;
}[] {
  const byMes: Record<string, EvolucaoDiaria[]> = {};
  for (const d of serie) {
    const mes = d.data.slice(0, 7);
    if (!byMes[mes]) byMes[mes] = [];
    byMes[mes].push(d);
  }
  const meses = Object.keys(byMes).sort();
  return meses.map((mes, i) => {
    const rows = byMes[mes];
    const last = rows[rows.length - 1];
    const prevMes = meses[i - 1];
    const prevLast = prevMes ? byMes[prevMes][byMes[prevMes].length - 1] : null;
    const variacao = prevLast ? last.patrimonio_total - prevLast.patrimonio_total : 0;
    const twr_mes = prevLast && prevLast.twr_total !== undefined
      ? last.twr_total - prevLast.twr_total
      : 0;
    return {
      mes,
      patrimonio: last.patrimonio_total,
      aporte: 0, // não disponível diretamente
      variacao,
      twr_mes,
    };
  });
}

function GraficoSVG({ serie }: { serie: EvolucaoDiaria[] }) {
  const W = 900, H = 200, PAD = { top: 16, right: 16, bottom: 24, left: 70 };

  if (serie.length < 2) {
    return <div className="text-xs italic px-4 py-8 text-center" style={{ color: "var(--text-faint)" }}>Dados insuficientes para o gráfico.</div>;
  }

  const valores = serie.map((d) => d.patrimonio_total);
  const minV = Math.min(...valores);
  const maxV = Math.max(...valores);
  const rangeV = maxV - minV || 1;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const toX = (i: number) => PAD.left + (i / (serie.length - 1)) * innerW;
  const toY = (v: number) => PAD.top + (1 - (v - minV) / rangeV) * innerH;

  const path = serie.map((d, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(d.patrimonio_total).toFixed(1)}`).join(" ");
  const area = path + ` L${toX(serie.length - 1).toFixed(1)},${(PAD.top + innerH).toFixed(1)} L${PAD.left},${(PAD.top + innerH).toFixed(1)} Z`;

  // Eixo Y — 4 labels
  const yLabels = [0, 0.33, 0.67, 1].map((f) => ({
    v: minV + f * rangeV,
    y: PAD.top + (1 - f) * innerH,
  }));

  // Eixo X — 5 datas
  const xCount = 5;
  const xLabels = Array.from({ length: xCount }, (_, i) => {
    const idx = Math.round((i / (xCount - 1)) * (serie.length - 1));
    return { label: serie[idx].data.slice(0, 7), x: toX(idx) };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      <defs>
        <linearGradient id="grad-evo" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#C15F3C" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#C15F3C" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {yLabels.map((lbl, i) => (
        <line key={i} x1={PAD.left} x2={W - PAD.right} y1={lbl.y} y2={lbl.y} stroke="#E5DBC8" strokeWidth="1" />
      ))}
      {/* Area */}
      <path d={area} fill="url(#grad-evo)" />
      {/* Line */}
      <path d={path} fill="none" stroke="#C15F3C" strokeWidth="2" />
      {/* Y labels */}
      {yLabels.map((lbl, i) => (
        <text key={i} x={PAD.left - 4} y={lbl.y + 4} textAnchor="end" fill="#A69C88" fontSize="10">
          {brl(lbl.v)}
        </text>
      ))}
      {/* X labels */}
      {xLabels.map((lbl, i) => (
        <text key={i} x={lbl.x} y={H - 4} textAnchor="middle" fill="#A69C88" fontSize="9">
          {lbl.label}
        </text>
      ))}
    </svg>
  );
}

export default function Evolucao() {
  const router = useRouter();
  const [serie, setSerie] = useState<EvolucaoDiaria[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtro, setFiltro] = useState<Filtro>("YTD");

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const data = await apiFetch<EvolucaoDiaria[]>("/evolucao");
        setSerie(data);
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
  }, [router]);

  const [expandedMes, setExpandedMes] = useState<string | null>(null);
  const toggleMes = useCallback((mes: string) => setExpandedMes((prev) => prev === mes ? null : mes), []);

  const serieFiltrada = useMemo(() => filtrarSerie(serie, filtro), [serie, filtro]);
  const mensal = useMemo(() => agruparMensal(serieFiltrada), [serieFiltrada]);

  // Dias de um mês específico (da série completa para ter todos os dias)
  const diasDoMes = useCallback((mes: string) =>
    serie.filter((d) => d.data.startsWith(mes)).sort((a, b) => a.data.localeCompare(b.data)),
  [serie]);
  const ultimo = serie.length > 0 ? serie[serie.length - 1] : null;

  const pnlColor = (v: number) => v >= 0 ? "var(--positive)" : "var(--negative)";

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">
        <div className="flex items-end justify-between flex-wrap gap-2">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Evolução do Patrimônio
          </h1>
          {ultimo && (
            <div className="text-right">
              <p className="text-xl font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(ultimo.patrimonio_total)}</p>
              <p className="text-xs" style={{ color: "var(--text-faint)" }}>{ultimo.data}</p>
            </div>
          )}
        </div>

        {loading && <div className="animate-pulse h-48 rounded-xl" style={{ background: "var(--bg-card)" }} />}
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
            {/* Filtros */}
            <div className="flex gap-2">
              {(["3M", "6M", "YTD", "1A", "Tudo"] as Filtro[]).map((f) => {
                const active = filtro === f;
                return (
                  <button
                    key={f}
                    onClick={() => setFiltro(f)}
                    className="px-3.5 py-1.5 rounded-full text-xs font-semibold transition border"
                    style={{
                      whiteSpace: "nowrap",
                      borderColor: active ? "var(--accent)" : "var(--border)",
                      color: active ? "var(--accent-strong)" : "var(--text-muted)",
                      background: active ? "rgba(193,95,60,0.12)" : "transparent",
                    }}
                  >
                    {f}
                  </button>
                );
              })}
            </div>

            {/* Gráfico */}
            <section
              className="rounded-xl border overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="px-4 py-2.5 border-b" style={{ borderColor: "var(--border-soft)" }}>
                <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>Patrimônio Total</p>
              </div>
              <div className="p-2">
                <GraficoSVG serie={serieFiltrada} />
              </div>
            </section>

            {/* Comparativos TWR */}
            {ultimo && (
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Performance Acumulada</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: "TWR Gerida", value: pct(serieFiltrada.length > 0 ? serieFiltrada[serieFiltrada.length - 1].twr_gerida : 0), color: "var(--positive)" },
                    { label: "TWR Total", value: pct(serieFiltrada.length > 0 ? serieFiltrada[serieFiltrada.length - 1].twr_total : 0), color: "var(--positive)" },
                    { label: "CDI", value: pct(serieFiltrada.length > 0 ? serieFiltrada[serieFiltrada.length - 1].cdi_acum : 0), color: "var(--text-muted)" },
                    { label: "IBOV", value: pct(serieFiltrada.length > 0 ? serieFiltrada[serieFiltrada.length - 1].ibov_acum : 0), color: "var(--text-muted)" },
                  ].map((k) => (
                    <div key={k.label} className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                      <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>{k.label}</p>
                      <p className="text-sm font-bold mt-0.5" style={{ color: k.color, fontFamily: "var(--font-plex-mono)" }}>{k.value}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Tabela mensal com accordion diário */}
            <section
              className="rounded-xl border overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Evolução Mensal <span className="text-[10px] font-normal ml-2" style={{ color: "var(--text-faint)" }}>clique no mês para ver dias</span>
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                      <th className="px-4 py-2 text-left">Mês</th>
                      <th className="px-4 py-2 text-right">Patrimônio</th>
                      <th className="px-4 py-2 text-right">Variação R$</th>
                      <th className="px-4 py-2 text-right">TWR Mês</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...mensal].reverse().map((m) => {
                      const expanded = expandedMes === m.mes;
                      const dias = expanded ? diasDoMes(m.mes) : [];
                      return (
                        <React.Fragment key={m.mes}>
                          <tr
                            onClick={() => toggleMes(m.mes)}
                            className="border-b cursor-pointer transition"
                            style={{ borderColor: "var(--border-soft)", background: expanded ? "rgba(193,95,60,0.06)" : "transparent" }}
                          >
                            <td className="px-4 py-2 text-xs" style={{ fontFamily: "var(--font-plex-mono)", color: "var(--text-body)" }}>
                              <span className="mr-1" style={{ color: "var(--text-faint)" }}>{expanded ? "▼" : "▶"}</span>
                              {m.mes}
                            </td>
                            <td className="px-4 py-2 text-right text-xs" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(m.patrimonio)}</td>
                            <td className="px-4 py-2 text-right text-xs" style={{ color: pnlColor(m.variacao), fontFamily: "var(--font-plex-mono)" }}>
                              {m.variacao >= 0 ? "+" : ""}{brl(m.variacao)}
                            </td>
                            <td className="px-4 py-2 text-right text-xs" style={{ color: pnlColor(m.twr_mes), fontFamily: "var(--font-plex-mono)" }}>
                              {pct(m.twr_mes)}
                            </td>
                          </tr>
                          {expanded && dias.map((d, i) => {
                            const prev = i > 0 ? dias[i - 1] : null;
                            const varDia = prev ? d.patrimonio_total - prev.patrimonio_total : 0;
                            const twrDia = prev ? d.twr_total - prev.twr_total : 0;
                            return (
                              <tr key={d.data} className="border-b" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                                <td className="pl-10 pr-4 py-1.5 text-[10px]" style={{ color: "var(--text-faint)", fontFamily: "var(--font-plex-mono)" }}>{d.data}</td>
                                <td className="px-4 py-1.5 text-right text-[10px]" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(d.patrimonio_total)}</td>
                                <td className="px-4 py-1.5 text-right text-[10px]" style={{ color: pnlColor(varDia), fontFamily: "var(--font-plex-mono)" }}>
                                  {i > 0 ? (varDia >= 0 ? "+" : "") + brl(varDia) : "—"}
                                </td>
                                <td className="px-4 py-1.5 text-right text-[10px]" style={{ color: pnlColor(twrDia), fontFamily: "var(--font-plex-mono)" }}>
                                  {i > 0 ? pct(twrDia, 3) : "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
        </div>
      </main>
    </div>
  );
}
