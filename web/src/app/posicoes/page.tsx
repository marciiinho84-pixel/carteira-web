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

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

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

  const pnlColor = (v: number) => v >= 0 ? "var(--positive)" : "var(--negative)";

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">

        <div className="flex items-center justify-between flex-wrap gap-2">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Posições
          </h1>
          <span className="text-xs" style={{ color: "var(--text-faint)" }}>{filtered.length} ativos</span>
        </div>

        {/* Filtros de bloco */}
        <div className="flex flex-wrap gap-2">
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
          <div
            className="rounded-xl border overflow-hidden"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr
                    className="border-b text-[10px] uppercase tracking-wider"
                    style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}
                  >
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
                                className="text-[10px] rounded px-1.5 py-0.5 border"
                                style={{ whiteSpace: "nowrap", color: "var(--negative)", background: "rgba(180,68,44,0.10)", borderColor: "rgba(180,68,44,0.25)" }}
                              >
                                -15%+
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-2.5 text-xs" style={{ color: "var(--text-muted)" }}>{p.classe ?? "—"}</td>
                        <td className="px-4 py-2.5 text-xs">
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
                        <td className="px-4 py-2.5 text-right text-xs" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{fmt2(p.qtd)}</td>
                        <td className="px-4 py-2.5 text-right text-xs" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{fmt2(p.preco_atual)}</td>
                        <td className="px-4 py-2.5 text-right text-xs" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(p.valor_atual)}</td>
                        <td className="px-4 py-2.5 text-right text-xs font-semibold" style={{ color: pnlColor(p.pnl), fontFamily: "var(--font-plex-mono)" }}>{brl(p.pnl)}</td>
                        <td className="px-4 py-2.5 text-right text-xs font-semibold" style={{ color: pnlColor(p.pnl_pct), fontFamily: "var(--font-plex-mono)" }}>{pct(p.pnl_pct)}</td>
                        <td className="px-4 py-2.5 text-right text-xs" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{peso.toFixed(1)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
                {/* Totais */}
                <tfoot>
                  <tr className="border-t text-xs font-bold" style={{ borderColor: "var(--border)", background: "var(--bg-card-alt)" }}>
                    <td className="px-4 py-2.5" style={{ color: "var(--text-primary)" }} colSpan={5}>Total ({filtered.length} ativos)</td>
                    <td className="px-4 py-2.5 text-right" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(totalValor)}</td>
                    <td className="px-4 py-2.5 text-right" style={{ color: pnlColor(totalPnl), fontFamily: "var(--font-plex-mono)" }}>{brl(totalPnl)}</td>
                    <td className="px-4 py-2.5 text-right" style={{ color: pnlColor(totalPnl), fontFamily: "var(--font-plex-mono)" }}>
                      {totalValor > 0 ? pct(totalPnl / (totalValor - totalPnl)) : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>100%</td>
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
