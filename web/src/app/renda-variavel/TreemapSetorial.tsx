"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { treemapLayout } from "./treemapUtils";

export interface AtivoSetor {
  ticker: string;
  valor: number;
  pct_setor: number;
}

export interface SetorDetalhado {
  nome: string;
  valor_total: number;
  pct_rv: number;
  ativos: AtivoSetor[];
}

const PALETA_HEX = ["#C15F3C", "#4A7C59", "#6C63C4", "#C9862B", "#A64E2E", "#7A7160", "#8A6D4F", "#3D6B7A"];
const HEADER_H = 22;

function brlCompact(v: number): string {
  if (v >= 1_000_000) return "R$ " + (v / 1_000_000).toFixed(2).replace(".", ",") + "M";
  if (v >= 1000) return "R$ " + (v / 1000).toFixed(1).replace(".", ",") + "k";
  return "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function TreemapSetorial({ setores }: { setores: SetorDetalhado[] }) {
  const [hover, setHover] = useState<{ setor: string; ticker: string } | null>(null);
  const W = 900;
  const H = 420;

  const setorItems = useMemo(
    () => setores.map((s, i) => ({ ...s, value: Math.max(0.01, s.valor_total), colorIdx: i })),
    [setores],
  );
  const setorRects = useMemo(() => treemapLayout(setorItems, 0, 0, W, H), [setorItems]);

  const hoverAtivo = hover
    ? setores.find((s) => s.nome === hover.setor)?.ativos.find((a) => a.ticker === hover.ticker)
    : null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 420, display: "block" }}>
        {setorRects.map((sr) => {
          const cor = PALETA_HEX[sr.colorIdx % PALETA_HEX.length];
          const innerY = sr.y + HEADER_H;
          const innerH = Math.max(0, sr.h - HEADER_H);
          const ativoItems = sr.ativos.map((a) => ({ ...a, value: Math.max(0.01, a.valor) }));
          const ativoRects = sr.h > HEADER_H + 10 && sr.w > 4 ? treemapLayout(ativoItems, sr.x, innerY, sr.w, innerH) : [];
          return (
            <g key={sr.nome}>
              <rect
                x={sr.x + 1} y={sr.y + 1}
                width={Math.max(0, sr.w - 2)} height={Math.max(0, sr.h - 2)}
                rx={4} fill={cor} opacity={0.14} stroke={cor} strokeWidth={1.5}
              />
              {sr.w > 60 && (
                <text x={sr.x + 8} y={sr.y + 15} fontSize={11} fontWeight={700} fill={cor}>
                  {sr.nome} · {brlCompact(sr.valor_total)}
                </text>
              )}
              {ativoRects.map((ar) => (
                <g
                  key={ar.ticker}
                  onMouseEnter={() => setHover({ setor: sr.nome, ticker: ar.ticker })}
                  onMouseLeave={() => setHover((h) => (h?.ticker === ar.ticker ? null : h))}
                  style={{ cursor: "pointer" }}
                >
                  <Link href={`/ativos/${ar.ticker}`}>
                    <rect x={ar.x + 2} y={ar.y + 2} width={Math.max(0, ar.w - 4)} height={Math.max(0, ar.h - 4)} rx={3} fill={cor} opacity={0.68} />
                    {ar.w > 38 && ar.h > 18 && (
                      <text x={ar.x + ar.w / 2} y={ar.y + ar.h / 2 + 4} textAnchor="middle" fontSize={10} fontWeight={600} fill="#FDF9F0">
                        {ar.ticker}
                      </text>
                    )}
                  </Link>
                </g>
              ))}
            </g>
          );
        })}
      </svg>

      {hoverAtivo && hover && (
        <div
          className="absolute top-2 right-2 rounded-lg border px-3 py-2 text-xs pointer-events-none"
          style={{ background: "var(--bg-card)", borderColor: "var(--border)", boxShadow: "0 4px 12px rgba(61,54,41,0.12)" }}
        >
          <p className="font-bold" style={{ color: "var(--text-primary)" }}>{hoverAtivo.ticker}</p>
          <p style={{ color: "var(--text-muted)" }}>{hover.setor}</p>
          <p style={{ fontFamily: "var(--font-plex-mono)", color: "var(--text-body)" }}>
            {brlCompact(hoverAtivo.valor)} · {(hoverAtivo.pct_setor * 100).toFixed(1)}% do setor
          </p>
        </div>
      )}
    </div>
  );
}
