"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
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

export default function Posicoes() {
  const router = useRouter();
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filtroBloco, setFiltroBloco] = useState("Todos");

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const data = await apiFetch<Posicao[]>("/posicoes");
        // Enrich bloco_ips from ativos endpoint if missing
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

  const filtered = filtroBloco === "Todos"
    ? posicoes
    : posicoes.filter((p) => (p.bloco_ips ?? "FORA_IPS") === filtroBloco);

  const totalValor = filtered.reduce((s, p) => s + (p.valor_atual ?? 0), 0);
  const totalPnl   = filtered.reduce((s, p) => s + (p.pnl ?? 0), 0);

  const pnlColor = (v: number) => v >= 0 ? "#26A69A" : "#EF5350";

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 space-y-4">

        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1 className="text-lg font-bold text-white">Posições</h1>
          <span className="text-xs text-[#6b7280]">{filtered.length} ativos</span>
        </div>

        {/* Filtros de bloco */}
        <div className="flex flex-wrap gap-2">
          {BLOCOS.map((b) => (
            <button
              key={b}
              onClick={() => setFiltroBloco(b)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition border ${
                filtroBloco === b
                  ? "bg-[#26A69A]/20 border-[#26A69A] text-[#26A69A]"
                  : "border-[#2A2D3A] text-[#6b7280] hover:border-[#4b5563] hover:text-[#D1D4DC]"
              }`}
            >
              {b === "Todos" ? "Todos" : (BLOCO_LABEL[b] ?? b)}
            </button>
          ))}
        </div>

        {loading && (
          <div className="animate-pulse space-y-2">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-10 rounded-lg bg-[#1A1D27]" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
                    <th className="px-4 py-2 text-left">Ativo</th>
                    <th className="px-4 py-2 text-left">Classe</th>
                    <th className="px-4 py-2 text-left">Bloco IPS</th>
                    <th className="px-4 py-2 text-right">Qtd</th>
                    <th className="px-4 py-2 text-right">Preço Atual</th>
                    <th className="px-4 py-2 text-right">Valor Atual</th>
                    <th className="px-4 py-2 text-right">P&amp;L R$</th>
                    <th className="px-4 py-2 text-right">P&amp;L %</th>
                    <th className="px-4 py-2 text-right">Peso %</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => {
                    const peso = totalValor > 0 ? (p.valor_atual / totalValor) * 100 : 0;
                    const alertaPnl = p.pnl_pct < -0.15;
                    return (
                      <tr
                        key={p.ticker}
                        className="border-b border-[#2A2D3A] hover:bg-[#2A2D3A]/30 cursor-pointer transition"
                        onClick={() => router.push(`/ativos/${p.ticker}`)}
                      >
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{p.ticker}</span>
                            {alertaPnl && (
                              <span className="text-[9px] rounded px-1 py-0.5 bg-red-900/40 text-[#EF5350] border border-red-800/50">
                                ⚠️ -15%+
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-[#6b7280] text-xs">{p.classe ?? "—"}</td>
                        <td className="px-4 py-2.5 text-xs">
                          {p.bloco_ips ? (
                            <Link
                              href={`/blocos/${p.bloco_ips}`}
                              onClick={(e) => e.stopPropagation()}
                              className="text-[#6366F1] hover:underline"
                            >
                              {BLOCO_LABEL[p.bloco_ips] ?? p.bloco_ips}
                            </Link>
                          ) : (
                            <span className="text-[#6b7280]">—</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{fmt2(p.qtd)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{fmt2(p.preco_atual)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{brl(p.valor_atual)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs" style={{ color: pnlColor(p.pnl) }}>{brl(p.pnl)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs" style={{ color: pnlColor(p.pnl_pct) }}>{pct(p.pnl_pct)}</td>
                        <td className="px-4 py-2.5 text-right font-mono text-xs">{peso.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
                {/* Totais */}
                <tfoot>
                  <tr className="border-t border-[#2A2D3A] bg-[#0F1117] text-xs font-bold">
                    <td className="px-4 py-2.5" colSpan={5}>Total ({filtered.length} ativos)</td>
                    <td className="px-4 py-2.5 text-right font-mono">{brl(totalValor)}</td>
                    <td className="px-4 py-2.5 text-right font-mono" style={{ color: pnlColor(totalPnl) }}>{brl(totalPnl)}</td>
                    <td className="px-4 py-2.5 text-right font-mono" style={{ color: pnlColor(totalPnl) }}>
                      {totalValor > 0 ? pct(totalPnl / (totalValor - totalPnl)) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono">100%</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}
        </div>
      </main>
    </div>
  );
}
