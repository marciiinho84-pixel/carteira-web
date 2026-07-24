"use client";

export const dynamic = "force-dynamic";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken, salaDeComando, type BlocoIPS } from "@/lib/api";
import { useRefreshSignal } from "@/lib/refresh-context";

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

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

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
  const color = Math.abs(real - alvo) < (max - min) * 0.5 ? "var(--positive)" : "var(--negative)";
  const maxVal = max > 0 ? max : 0.5;
  const pctPos = Math.min(100, Math.max(0, (real / maxVal) * 100));
  const realPct = Math.round(real * 100);
  const alvoPct = Math.round(alvo * 100);
  const minPct = Math.round(min * 100);
  const maxPct = Math.round(max * 100);

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="font-medium" style={{ color: "var(--text-body)" }}>Real: <span style={{ color }}>{realPct}%</span></span>
        <span style={{ color: "var(--text-faint)" }}>Alvo: {alvoPct}% | Banda: {minPct}%–{maxPct}%</span>
      </div>
      <div className="relative rounded-full overflow-hidden" style={{ height: 8, background: "var(--border-soft)" }}>
        <div
          className="absolute h-full rounded-full"
          style={{
            left: `${(min / maxVal) * 100}%`,
            right: `${100 - Math.min(100, (max / maxVal) * 100)}%`,
            background: "rgba(122,113,96,0.18)",
          }}
        />
        <div
          className="absolute h-full rounded-full"
          style={{ width: `${pctPos}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function BlocoPage() {
  const params = useParams<{ bloco: string }>();
  const bloco = (params?.bloco ?? "").toUpperCase();
  const router = useRouter();
  const { refreshKey } = useRefreshSignal();
  const firstLoad = useRef(true);
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [blocoInfo, setBlocoInfo] = useState<BlocoIPS | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      if (firstLoad.current) setLoading(true);
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
        firstLoad.current = false;
      }
    }
    load();
  }, [bloco, router, refreshKey]);

  const totalValor = posicoes.reduce((s, p) => s + p.valor_atual, 0);
  const pnlColor = (v: number) => v >= 0 ? "var(--positive)" : "var(--negative)";

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">

        {/* Breadcrumb */}
        <div className="text-xs" style={{ color: "var(--text-faint)" }}>
          <Link href="/sala-de-comando" className="hover:underline" style={{ color: "var(--text-faint)" }}>Sala de Comando</Link>
          <span className="mx-1">›</span>
          <span style={{ color: "var(--text-body)" }}>{BLOCO_LABEL[bloco] ?? bloco}</span>
        </div>

        <h1
          className="text-2xl font-semibold"
          style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
        >
          {BLOCO_LABEL[bloco] ?? bloco}
        </h1>

        {loading && (
          <div className="animate-pulse space-y-3">
            <div className="h-20 rounded-xl" style={{ background: "var(--bg-card)" }} />
            <div className="h-48 rounded-xl" style={{ background: "var(--bg-card)" }} />
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
            {/* Barra IPS */}
            {blocoInfo && (
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Alocação vs IPS</h2>
                <BarraVisual
                  real={blocoInfo.pct_real}
                  alvo={blocoInfo.pct_alvo}
                  min={blocoInfo.banda_min}
                  max={blocoInfo.banda_max}
                />
                <p className="mt-2 text-xs">
                  Status:{" "}
                  <span style={{ color: blocoInfo.status === "OK" ? "var(--positive)" : "var(--negative)" }}>
                    {blocoInfo.status}
                  </span>
                </p>
              </section>
            )}

            {/* Lista de ativos */}
            <section
              className="rounded-xl border overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Ativos ({posicoes.length})
                </h2>
                <span className="text-xs" style={{ color: "var(--text-faint)" }}>Total: {brl(totalValor)}</span>
              </div>
              {posicoes.length === 0 ? (
                <p className="px-5 py-4 text-xs italic" style={{ color: "var(--text-faint)" }}>
                  Nenhum ativo no bloco {BLOCO_LABEL[bloco] ?? bloco}.
                </p>
              ) : (
                <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                  {posicoes
                    .sort((a, b) => b.valor_atual - a.valor_atual)
                    .map((p) => {
                      const peso = totalValor > 0 ? (p.valor_atual / totalValor) * 100 : 0;
                      return (
                        <Link
                          key={p.ticker}
                          href={`/ativos/${p.ticker}`}
                          className="flex items-center justify-between px-5 py-3 transition flex-wrap gap-2"
                          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                        >
                          <div>
                            <span className="font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{p.ticker}</span>
                            {p.classe && (
                              <span className="ml-2 text-[10px]" style={{ color: "var(--text-faint)" }}>{p.classe}</span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs" style={{ fontFamily: "var(--font-plex-mono)" }}>
                            <span style={{ color: "var(--text-faint)" }}>{peso.toFixed(1)}%</span>
                            <span style={{ color: "var(--text-body)" }}>{brl(p.valor_atual)}</span>
                            <span style={{ color: pnlColor(p.pnl_pct) }}>{pct(p.pnl_pct)}</span>
                            <span style={{ color: "var(--text-faint)" }}>›</span>
                          </div>
                        </Link>
                      );
                    })}
                </div>
              )}
            </section>

            <Link
              href="/sala-de-comando"
              className="inline-block rounded-lg px-4 py-2 text-sm border transition"
              style={{ borderColor: "var(--border)", color: "var(--text-body)" }}
            >
              ← Sala de Comando
            </Link>
          </>
        )}
      </main>
    </div>
  );
}
