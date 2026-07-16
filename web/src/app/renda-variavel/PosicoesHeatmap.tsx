"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { treemapLayout, interpolateColor } from "./treemapUtils";

export interface PosicaoHeat {
  ticker: string;
  setor: string;
  valor_atual: number;
  pct_rv: number;
  variacao_dia_pct: number;
  contrib_dia_rs: number;
  pl_total_pct: number;
  pl_total_rs: number;
}

type Modo = "dia" | "pnl" | "tamanho";

const DIVERGENTE = ["#7A3019", "#B4442C", "#A69C88", "#4A7C59", "#2E5A3D"];
const SEQUENCIAL = ["#EFE7D8", "#DDBBA0", "#C15F3C"];

function brl(v: number): string {
  const abs = Math.abs(v);
  const s = "R$ " + abs.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (v < 0 ? "-" : "") + s;
}

function luminance(rgb: string): number {
  const m = rgb.match(/\d+/g);
  if (!m) return 0;
  const [r, g, b] = m.map(Number);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

const MODOS: { key: Modo; label: string }[] = [
  { key: "dia", label: "Variação Hoje" },
  { key: "pnl", label: "P&L Total" },
  { key: "tamanho", label: "Concentração" },
];

export default function PosicoesHeatmap({ posicoes }: { posicoes: PosicaoHeat[] }) {
  const [modo, setModo] = useState<Modo>("dia");
  const [hover, setHover] = useState<string | null>(null);

  const W = 900;
  const H = 320;

  const itens = useMemo(() => {
    const ordenadas = [...posicoes].sort((a, b) => b.valor_atual - a.valor_atual);
    return ordenadas.map((p) => ({ ...p, value: Math.max(0.01, p.valor_atual) }));
  }, [posicoes]);

  const rects = useMemo(() => treemapLayout(itens, 0, 0, W, H), [itens]);

  function corCelula(p: PosicaoHeat): string {
    if (modo === "dia") return interpolateColor(p.variacao_dia_pct * 100, -3, 3, DIVERGENTE);
    if (modo === "pnl") return interpolateColor(p.pl_total_pct * 100, -50, 100, DIVERGENTE);
    return interpolateColor(p.pct_rv * 100, 0, 20, SEQUENCIAL);
  }

  function labelValor(p: PosicaoHeat): string {
    if (modo === "dia") return (p.variacao_dia_pct >= 0 ? "+" : "") + (p.variacao_dia_pct * 100).toFixed(2) + "%";
    if (modo === "pnl") return (p.pl_total_pct >= 0 ? "+" : "") + (p.pl_total_pct * 100).toFixed(1) + "%";
    return (p.pct_rv * 100).toFixed(1) + "% RV";
  }

  const hoverData = hover ? posicoes.find((p) => p.ticker === hover) : null;

  return (
    <div>
      <div className="flex gap-1 mb-3">
        {MODOS.map((m) => (
          <button
            key={m.key}
            onClick={() => setModo(m.key)}
            className="text-xs px-3 py-1.5 rounded-lg border transition"
            style={{
              borderColor: modo === m.key ? "var(--accent)" : "var(--border)",
              background: modo === m.key ? "rgba(193,95,60,0.10)" : "transparent",
              color: modo === m.key ? "var(--accent-strong)" : "var(--text-muted)",
              fontWeight: modo === m.key ? 600 : 400,
            }}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 320, display: "block" }}>
          {rects.map((r) => {
            const cor = corCelula(r);
            const txtCor = luminance(cor) > 0.55 ? "#2E2921" : "#FDF9F0";
            const showLabel = r.w > 46 && r.h > 28;
            return (
              <g
                key={r.ticker}
                onMouseEnter={() => setHover(r.ticker)}
                onMouseLeave={() => setHover((h) => (h === r.ticker ? null : h))}
                style={{ cursor: "pointer" }}
              >
                <Link href={`/ativos/${r.ticker}`}>
                  <rect x={r.x + 1.5} y={r.y + 1.5} width={Math.max(0, r.w - 3)} height={Math.max(0, r.h - 3)} rx={4} fill={cor} />
                  {showLabel && (
                    <>
                      <text x={r.x + r.w / 2} y={r.y + r.h / 2 - 6} textAnchor="middle" fontSize={12} fontWeight={700} fill={txtCor}>
                        {r.ticker}
                      </text>
                      <text x={r.x + r.w / 2} y={r.y + r.h / 2 + 10} textAnchor="middle" fontSize={10} fill={txtCor} opacity={0.9}>
                        {labelValor(r)}
                      </text>
                    </>
                  )}
                </Link>
              </g>
            );
          })}
        </svg>

        {hoverData && (
          <div
            className="absolute top-2 right-2 rounded-lg border px-3 py-2 text-xs pointer-events-none"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)", boxShadow: "0 4px 12px rgba(61,54,41,0.12)", minWidth: 180 }}
          >
            <p className="font-bold mb-1" style={{ color: "var(--text-primary)" }}>{hoverData.ticker}</p>
            <p style={{ color: "var(--text-muted)" }}>{hoverData.setor}</p>
            <p style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>
              {brl(hoverData.valor_atual)} · {(hoverData.pct_rv * 100).toFixed(1)}% RV
            </p>
            <p style={{ fontFamily: "var(--font-plex-mono)", color: hoverData.variacao_dia_pct >= 0 ? "var(--positive)" : "var(--negative)" }}>
              Hoje: {(hoverData.variacao_dia_pct >= 0 ? "+" : "") + (hoverData.variacao_dia_pct * 100).toFixed(2)}% ({brl(hoverData.contrib_dia_rs)})
            </p>
            <p style={{ fontFamily: "var(--font-plex-mono)", color: hoverData.pl_total_pct >= 0 ? "var(--positive)" : "var(--negative)" }}>
              P&L: {(hoverData.pl_total_pct >= 0 ? "+" : "") + (hoverData.pl_total_pct * 100).toFixed(2)}% ({brl(hoverData.pl_total_rs)})
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
