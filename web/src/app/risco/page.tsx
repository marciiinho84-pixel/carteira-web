"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken, salaDeComando, type BlocoIPS } from "@/lib/api";

interface Posicao {
  ticker: string;
  classe?: string;
  composite: string;
  qtd: number;
  valor_atual: number;
  pnl: number;
  pnl_pct: number;
  bloco_ips?: string;
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

const BLOCO_LABEL: Record<string, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH: "Growth",
  DEFENSIVOS: "Defensivos",
  RENDA_FIXA: "Renda Fixa",
  FORA_IPS: "Fora IPS",
};

export default function Risco() {
  const router = useRouter();
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [totalFuncef, setTotalFuncef] = useState<number>(0);
  const [blocos, setBlocos] = useState<BlocoIPS[]>([]);
  const [hhi, setHhi] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const [pos, sd] = await Promise.all([
          apiFetch<Posicao[]>("/posicoes"),
          salaDeComando().catch(() => null),
        ]);
        const ativas = pos.filter((p) => (p.valor_atual ?? 0) > 0);
        // Separar Carteira Gerida da FUNCEF — mesma lógica do Streamlit IPS §1
        const gerida = ativas.filter((p) => p.composite !== "FUNCEF");
        const funcef = ativas.filter((p) => p.composite === "FUNCEF");
        setPosicoes(gerida);
        setTotalFuncef(funcef.reduce((s, p) => s + p.valor_atual, 0));
        if (sd?.comportamental?.blocos) {
          setBlocos(sd.comportamental.blocos);
        }
        // HHI sobre Carteira Gerida (exclui FUNCEF)
        const total = gerida.reduce((s, p) => s + p.valor_atual, 0);
        if (total > 0) {
          const hhiVal = gerida.reduce((s, p) => {
            const w = p.valor_atual / total;
            return s + w * w * 10000;
          }, 0);
          setHhi(Math.round(hhiVal));
        }
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
  }, [router]);

  const total = posicoes.reduce((s, p) => s + p.valor_atual, 0);
  const top5 = [...posicoes]
    .sort((a, b) => b.valor_atual - a.valor_atual)
    .slice(0, 5);

  const hhiNivel = hhi == null ? null : hhi > 2500 ? "ALTO" : hhi > 1500 ? "MODERADO" : "BAIXO";
  const hhiCor = hhiNivel === "ALTO" ? "#EF5350" : hhiNivel === "MODERADO" ? "#F59E0B" : "#26A69A";
  const pnlColor = (v: number) => v >= 0 ? "#26A69A" : "#EF5350";

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 space-y-4">
        <h1 className="text-lg font-bold text-white">Risco e Exposição</h1>

        {loading && (
          <div className="animate-pulse space-y-3">
            <div className="h-24 rounded-xl bg-[#1A1D27]" />
            <div className="h-48 rounded-xl bg-[#1A1D27]" />
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {!loading && !error && (
          <>
            {/* KPI bar: Gerida vs FUNCEF */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
                <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">Carteira Gerida</p>
                <p className="text-base font-bold text-white mt-0.5">{brl(posicoes.reduce((s,p)=>s+p.valor_atual,0))}</p>
              </div>
              <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
                <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">FUNCEF (excluída)</p>
                <p className="text-base font-bold text-[#F59E0B] mt-0.5">{brl(totalFuncef)}</p>
                <p className="text-[9px] text-[#6b7280]">fora do escopo IPS</p>
              </div>
              <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
                <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">Patrimônio Total</p>
                <p className="text-base font-bold text-white mt-0.5">{brl(posicoes.reduce((s,p)=>s+p.valor_atual,0) + totalFuncef)}</p>
              </div>
              <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
                <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">Ativos (Gerida)</p>
                <p className="text-base font-bold text-white mt-0.5">{posicoes.length}</p>
              </div>
            </div>

            {/* HHI */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <h2 className="text-sm font-semibold text-white">Concentração (HHI)</h2>
                  <p className="text-[10px] text-[#6b7280] mt-0.5">
                    Base: Carteira Gerida · exclui FUNCEF. &lt;1500: diversificado | &gt;2500: concentrado.
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-3xl font-bold font-mono" style={{ color: hhiCor }}>
                    {hhi ?? "—"}
                  </p>
                  {hhiNivel && (
                    <p className="text-xs font-semibold" style={{ color: hhiCor }}>{hhiNivel}</p>
                  )}
                </div>
              </div>
              {/* Barra HHI */}
              {hhi != null && (
                <div className="mt-3 space-y-1">
                  <div className="h-2 rounded-full bg-[#2A2D3A] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, hhi / 100)}%`, backgroundColor: hhiCor }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-[#6b7280]">
                    <span>0 (pulverizado)</span>
                    <span>10.000 (monopolista)</span>
                  </div>
                </div>
              )}
            </section>

            {/* Exposição por bloco vs IPS */}
            {blocos.length > 0 && (
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                <div className="px-5 py-3 border-b border-[#2A2D3A]">
                  <h2 className="text-sm font-semibold text-white">Exposição por Bloco IPS</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
                        <th className="px-4 py-2 text-left">Bloco</th>
                        <th className="px-4 py-2 text-right">Real %</th>
                        <th className="px-4 py-2 text-right">Alvo %</th>
                        <th className="px-4 py-2 text-right">Banda</th>
                        <th className="px-4 py-2 text-right">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {blocos.map((b) => {
                        const cor = b.status === "OK" ? "#26A69A" : "#EF5350";
                        return (
                          <tr key={b.bloco} className="border-b border-[#2A2D3A]">
                            <td className="px-4 py-2.5">
                              <Link href={`/blocos/${b.bloco}`} className="text-[#6366F1] hover:underline text-xs">
                                {BLOCO_LABEL[b.bloco] ?? b.bloco}
                              </Link>
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-xs" style={{ color: cor }}>
                              {(b.pct_real * 100).toFixed(1)}%
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-xs text-[#6b7280]">
                              {(b.pct_alvo * 100).toFixed(1)}%
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-xs text-[#6b7280]">
                              {(b.banda_min * 100).toFixed(0)}%–{(b.banda_max * 100).toFixed(0)}%
                            </td>
                            <td className="px-4 py-2.5 text-right text-xs font-medium" style={{ color: cor }}>
                              {b.status}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {/* Top 5 ativos */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
              <div className="px-5 py-3 border-b border-[#2A2D3A]">
                <h2 className="text-sm font-semibold text-white">Top 5 Ativos por Peso</h2>
              </div>
              <div className="divide-y divide-[#2A2D3A]">
                {top5.map((p, i) => {
                  const peso = total > 0 ? (p.valor_atual / total) * 100 : 0;
                  return (
                    <Link
                      key={p.ticker}
                      href={`/ativos/${p.ticker}`}
                      className="flex items-center justify-between px-5 py-3 hover:bg-[#2A2D3A]/30 transition"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-[#6b7280] w-4">{i + 1}</span>
                        <span className="font-bold text-white">{p.ticker}</span>
                        {p.bloco_ips && (
                          <span className="text-[9px] text-[#6b7280] border border-[#2A2D3A] rounded px-1 py-0.5">
                            {BLOCO_LABEL[p.bloco_ips] ?? p.bloco_ips}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs font-mono">
                        <div className="w-24 bg-[#2A2D3A] rounded-full h-1.5">
                          <div
                            className="h-full rounded-full bg-[#26A69A]"
                            style={{ width: `${Math.min(100, peso * 2)}%` }}
                          />
                        </div>
                        <span className="text-[#D1D4DC]">{peso.toFixed(1)}%</span>
                        <span>{brl(p.valor_atual)}</span>
                        <span style={{ color: pnlColor(p.pnl_pct) }}>{pct(p.pnl_pct)}</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          </>
        )}
        </div>
      </main>
    </div>
  );
}
