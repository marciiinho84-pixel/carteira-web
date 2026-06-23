"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken, salaDeComando, type BlocoIPS } from "@/lib/api";

interface Posicao {
  ticker: string;
  classe?: string;
  familia?: string;
  composite: string;
  qtd: number;
  custo_total: number;
  preco_atual?: number;
  valor_atual: number;
  pnl: number;
  pnl_pct: number;
  bloco_ips?: string;
}

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

function BarraVisual({ real, alvo, min, max }: { real: number; alvo: number; min: number; max: number }) {
  const color = Math.abs(real - alvo) < (max - min) * 0.5 ? "#26A69A" : "#EF5350";
  const maxVal = max > 0 ? max : 0.5;
  const pctPos = Math.min(100, Math.max(0, (real / maxVal) * 100));
  const realPct = Math.round(real * 100);
  const alvoPct = Math.round(alvo * 100);
  const minPct = Math.round(min * 100);
  const maxPct = Math.round(max * 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-[#D1D4DC] font-medium">Real: <span style={{ color }}>{realPct}%</span></span>
        <span className="text-[#6b7280]">Alvo: {alvoPct}% | Banda: {minPct}%–{maxPct}%</span>
      </div>
      <div className="relative h-3 rounded-full bg-[#2A2D3A] overflow-hidden">
        <div
          className="absolute h-full opacity-20 rounded-full"
          style={{
            left: `${(min / maxVal) * 100}%`,
            right: `${100 - Math.min(100, (max / maxVal) * 100)}%`,
            backgroundColor: "#26A69A",
          }}
        />
        <div
          className="absolute h-full rounded-full"
          style={{ width: `${pctPos}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function BlocoPage() {
  const params = useParams<{ bloco: string }>();
  const bloco = (params?.bloco ?? "").toUpperCase();
  const router = useRouter();
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [blocoInfo, setBlocoInfo] = useState<BlocoIPS | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const [posData, sdData] = await Promise.all([
          apiFetch<Posicao[]>("/posicoes"),
          salaDeComando().catch(() => null),
        ]);
        const filtered = posData.filter((p) => (p.bloco_ips ?? "FORA_IPS") === bloco && p.qtd > 0);
        setPosicoes(filtered);
        if (sdData?.comportamental?.blocos) {
          const b = sdData.comportamental.blocos.find((x) => x.bloco === bloco);
          if (b) setBlocoInfo(b);
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
  }, [bloco, router]);

  const totalValor = posicoes.reduce((s, p) => s + p.valor_atual, 0);
  const pnlColor = (v: number) => v >= 0 ? "#26A69A" : "#EF5350";

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs text-[#6b7280]">
          <Link href="/sala-de-comando" className="hover:text-[#26A69A]">Sala de Comando</Link>
          <span className="mx-1">›</span>
          <span className="text-[#D1D4DC]">{BLOCO_LABEL[bloco] ?? bloco}</span>
        </div>

        <h1 className="text-lg font-bold text-white">
          {BLOCO_LABEL[bloco] ?? bloco}
        </h1>

        {loading && (
          <div className="animate-pulse space-y-3">
            <div className="h-20 rounded-xl bg-[#1A1D27]" />
            <div className="h-48 rounded-xl bg-[#1A1D27]" />
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Barra IPS */}
            {blocoInfo && (
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                <h2 className="text-sm font-semibold text-white mb-3">Alocação vs IPS</h2>
                <BarraVisual
                  real={blocoInfo.pct_real}
                  alvo={blocoInfo.pct_alvo}
                  min={blocoInfo.banda_min}
                  max={blocoInfo.banda_max}
                />
                <p className="mt-2 text-xs">
                  Status:{" "}
                  <span style={{ color: blocoInfo.status === "OK" ? "#26A69A" : "#EF5350" }}>
                    {blocoInfo.status}
                  </span>
                </p>
              </section>
            )}

            {/* Lista de ativos */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-[#2A2D3A]">
                <h2 className="text-sm font-semibold text-white">
                  Ativos ({posicoes.length})
                </h2>
                <span className="text-xs text-[#6b7280]">Total: {brl(totalValor)}</span>
              </div>
              {posicoes.length === 0 ? (
                <p className="px-5 py-4 text-xs text-[#6b7280] italic">
                  Nenhum ativo no bloco {BLOCO_LABEL[bloco] ?? bloco}.
                </p>
              ) : (
                <div className="divide-y divide-[#2A2D3A]">
                  {posicoes
                    .sort((a, b) => b.valor_atual - a.valor_atual)
                    .map((p) => {
                      const peso = totalValor > 0 ? (p.valor_atual / totalValor) * 100 : 0;
                      return (
                        <Link
                          key={p.ticker}
                          href={`/ativos/${p.ticker}`}
                          className="flex items-center justify-between px-5 py-3 hover:bg-[#2A2D3A]/30 transition"
                        >
                          <div>
                            <span className="font-bold text-white">{p.ticker}</span>
                            {p.classe && (
                              <span className="ml-2 text-[10px] text-[#6b7280]">{p.classe}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs font-mono">
                            <span className="text-[#6b7280]">{peso.toFixed(1)}%</span>
                            <span>{brl(p.valor_atual)}</span>
                            <span style={{ color: pnlColor(p.pnl_pct) }}>{pct(p.pnl_pct)}</span>
                            <span className="text-[#6b7280]">›</span>
                          </div>
                        </Link>
                      );
                    })}
                </div>
              )}
            </section>

            <Link
              href="/sala-de-comando"
              className="inline-block rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
            >
              ← Sala de Comando
            </Link>
          </>
        )}
      </main>
    </div>
  );
}
