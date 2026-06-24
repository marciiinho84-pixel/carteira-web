"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { apiFetch, clearToken, salaDeComando, type Meta } from "@/lib/api";

interface MetaOut {
  patrimonio_atual: number;
  twr_anualizado: number;
  aporte_anual: number;
  meta: number;
  projecao: { ano: number; aporte: number; twr: number; patrimonio: number; pct_meta: number }[];
}

function brl(n: number | null | undefined): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function pct(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(d) + "%";
}

function calcProjecao(
  patrimonioAtual: number,
  twrAnual: number,
  aporteAnual: number,
  aporteExtra: number,
  meta: number,
  anos = 30
) {
  const total = aporteAnual + aporteExtra * 12;
  const pts: { ano: number; patrimonio: number }[] = [];
  let pat = patrimonioAtual;
  const anoAtual = new Date().getFullYear();
  for (let i = 0; i <= anos; i++) {
    pts.push({ ano: anoAtual + i, patrimonio: pat });
    if (pat >= meta) break;
    pat = pat * (1 + twrAnual) + total;
  }
  return pts;
}

function GraficoProjecao({
  proj,
  meta,
}: {
  proj: { ano: number; patrimonio: number }[];
  meta: number;
}) {
  const W = 800, H = 180, PAD = { top: 16, right: 16, bottom: 28, left: 80 };
  if (proj.length < 2) return null;
  const maxV = Math.max(meta * 1.05, ...proj.map((p) => p.patrimonio));
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const toX = (i: number) => PAD.left + (i / (proj.length - 1)) * innerW;
  const toY = (v: number) => PAD.top + (1 - v / maxV) * innerH;

  const path = proj.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p.patrimonio).toFixed(1)}`).join(" ");
  const metaY = toY(meta);

  // Labels Y
  const yLabels = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    v: f * maxV,
    y: PAD.top + (1 - f) * innerH,
  }));

  // X labels
  const step = Math.max(1, Math.floor(proj.length / 5));
  const xLabels = proj.filter((_, i) => i % step === 0).map((p, i) => ({
    label: String(p.ano),
    x: toX(proj.indexOf(p) >= 0 ? proj.findIndex((q) => q.ano === p.ano) : i * step),
  }));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: H }}>
      <defs>
        <linearGradient id="grad-meta" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#6366F1" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#6366F1" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Meta line */}
      <line x1={PAD.left} x2={W - PAD.right} y1={metaY} y2={metaY} stroke="#F59E0B" strokeWidth="1" strokeDasharray="4 3" />
      <text x={W - PAD.right + 2} y={metaY + 4} fill="#F59E0B" fontSize="9">Meta</text>
      {/* Grid */}
      {yLabels.map((l, i) => (
        <line key={i} x1={PAD.left} x2={W - PAD.right} y1={l.y} y2={l.y} stroke="#2A2D3A" strokeWidth="1" />
      ))}
      {/* Area */}
      <path
        d={path + ` L${toX(proj.length - 1).toFixed(1)},${(PAD.top + innerH).toFixed(1)} L${PAD.left},${(PAD.top + innerH).toFixed(1)} Z`}
        fill="url(#grad-meta)"
      />
      {/* Line */}
      <path d={path} fill="none" stroke="#6366F1" strokeWidth="2" />
      {/* Y labels */}
      {yLabels.map((l, i) => (
        <text key={i} x={PAD.left - 4} y={l.y + 4} textAnchor="end" fill="#6b7280" fontSize="9">
          {brl(l.v)}
        </text>
      ))}
      {/* X labels */}
      {xLabels.map((l, i) => (
        <text key={i} x={l.x} y={H - 6} textAnchor="middle" fill="#6b7280" fontSize="9">{l.label}</text>
      ))}
    </svg>
  );
}

export default function MetaPage() {
  const router = useRouter();
  const [metaData, setMetaData] = useState<MetaOut | null>(null);
  const [sdMeta, setSdMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aporteExtra, setAporteExtra] = useState(0);
  const [twrSlider, setTwrSlider] = useState<number | null>(null); // null = usar TWR real

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const [md, sd] = await Promise.all([
          apiFetch<MetaOut>("/meta"),
          salaDeComando().catch(() => null),
        ]);
        setMetaData(md);
        if (sd?.meta) setSdMeta(sd.meta);
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

  const META = metaData?.meta ?? 3_000_000;
  const patAtual = metaData?.patrimonio_atual ?? sdMeta?.patrimonio_atual ?? 0;
  const twrReal = metaData?.twr_anualizado ?? sdMeta?.twr_anualizado ?? 0;
  const twr = twrSlider !== null ? twrSlider / 100 : twrReal;
  const aporteAnual = metaData?.aporte_anual ?? 0;
  const pctAtingido = META > 0 ? patAtual / META : 0;

  const projecaoBase = useMemo(
    () => calcProjecao(patAtual, twr, aporteAnual, 0, META),
    [patAtual, twr, aporteAnual, META]
  );

  const projecaoExtra = useMemo(
    () => calcProjecao(patAtual, twr, aporteAnual, aporteExtra, META),
    [patAtual, twr, aporteAnual, aporteExtra, META]
  );

  const anoMetaBase = projecaoBase.find((p) => p.patrimonio >= META)?.ano ?? null;
  const anoMetaExtra = projecaoExtra.find((p) => p.patrimonio >= META)?.ano ?? null;

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">
        <h1 className="text-lg font-bold text-white">Meta R$ 3 Milhões</h1>

        {loading && <div className="animate-pulse h-64 rounded-xl bg-[#1A1D27]" />}
        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {!loading && !error && (
          <>
            {/* Progress */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5">
              <div className="flex justify-between text-sm mb-2">
                <span className="font-bold text-white">{brl(patAtual)}</span>
                <span className="text-[#6b7280]">{brl(META)}</span>
              </div>
              <div className="h-5 rounded-full bg-[#2A2D3A] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#26A69A] to-[#6366F1] transition-all"
                  style={{ width: `${Math.min(100, pctAtingido * 100)}%` }}
                />
              </div>
              <div className="flex justify-between mt-1 text-xs">
                <span className="text-[#26A69A] font-bold">{(pctAtingido * 100).toFixed(1)}% atingido</span>
                <span className="text-[#6b7280]">Falta {brl(META - patAtual)}</span>
              </div>
            </section>

            {/* KPIs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: "Projeção (base)", value: anoMetaBase ? `até ${anoMetaBase}` : "—", color: "#6366F1" },
                { label: "TWR Anualizado", value: pct(twr), color: "#26A69A" },
                { label: "Aporte Mensal (base)", value: brl(aporteAnual / 12), color: "#D1D4DC" },
                { label: "Necessário / mês", value: sdMeta?.ritmo_mensal_necessario ? brl(sdMeta.ritmo_mensal_necessario) : "—", color: "#F59E0B" },
              ].map((k) => (
                <div key={k.label} className="rounded-lg bg-[#1A1D27] border border-[#2A2D3A] px-4 py-3">
                  <p className="text-[9px] text-[#6b7280] uppercase tracking-wider">{k.label}</p>
                  <p className="text-sm font-bold font-mono mt-0.5" style={{ color: k.color }}>{k.value}</p>
                </div>
              ))}
            </div>

            {/* Simulador de Projeção */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">Simulador de Projeção</h2>
                <button onClick={() => { setTwrSlider(null); setAporteExtra(0); }}
                  className="text-[10px] text-[#6b7280] hover:text-[#D1D4DC] border border-[#2A2D3A] rounded px-2 py-0.5 transition">
                  Resetar
                </button>
              </div>

              {/* Slider TWR */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-[#D1D4DC]">TWR anualizado:</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[#26A69A]">{(twr * 100).toFixed(1)}% a.a.</span>
                    {twrSlider !== null && (
                      <span className="text-[10px] text-[#F59E0B]">real: {(twrReal * 100).toFixed(1)}%</span>
                    )}
                  </div>
                </div>
                <input
                  type="range"
                  min="0"
                  max="30"
                  step="0.5"
                  value={twrSlider !== null ? twrSlider : twrReal * 100}
                  onChange={(e) => setTwrSlider(Number(e.target.value))}
                  className="w-full accent-[#26A69A]"
                />
                <div className="flex justify-between text-[10px] text-[#6b7280]">
                  <span>0% a.a.</span>
                  <span>30% a.a.</span>
                </div>
              </div>

              {/* Slider Aporte Extra */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-[#D1D4DC]">Aporte extra mensal:</span>
                  <span className="font-mono text-[#26A69A]">{brl(aporteExtra)}/mês</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="20000"
                  step="500"
                  value={aporteExtra}
                  onChange={(e) => setAporteExtra(Number(e.target.value))}
                  className="w-full accent-[#26A69A]"
                />
                <div className="flex justify-between text-[10px] text-[#6b7280]">
                  <span>R$ 0</span>
                  <span>R$ 20.000</span>
                </div>
              </div>

              {/* Resumo */}
              <div className="rounded-lg border border-[#2A2D3A] bg-[#0F1117] px-4 py-3 text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-[#6b7280]">Cenário atual</span>
                  <span className="font-mono text-white">meta em <span className="text-[#26A69A] font-bold">{anoMetaBase ? `${anoMetaBase}` : "30+ anos"}</span></span>
                </div>
                {aporteExtra > 0 && (
                  <div className="flex justify-between">
                    <span className="text-[#6b7280]">+ Aporte extra</span>
                    <span className="font-mono text-white">meta em <span className="text-[#F59E0B] font-bold">{anoMetaExtra ? `${anoMetaExtra}` : "30+ anos"}</span>
                      {anoMetaBase && anoMetaExtra && anoMetaExtra < anoMetaBase && (
                        <span className="text-[#F59E0B] ml-1">(-{anoMetaBase - anoMetaExtra} anos)</span>
                      )}
                    </span>
                  </div>
                )}
              </div>

              <GraficoProjecao
                proj={aporteExtra > 0 ? projecaoExtra : projecaoBase}
                meta={META}
              />
            </section>
          </>
        )}
      </main>
    </div>
  );
}
