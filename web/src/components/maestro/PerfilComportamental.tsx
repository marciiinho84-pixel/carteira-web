"use client";

import React from "react";

interface Vies {
  nome_vies: string;
  detectado: boolean;
  fato?: string | null;
  frequencia?: number | null;
  [key: string]: unknown;
}

interface PerfilComportamentalProps {
  vieses: Vies[];
  periodo?: string;
}

const FREQ_LABEL: Record<string, string> = {
  baixa: "Baixa",
  media: "Média",
  alta:  "Alta",
};

function freqColor(f: number | null | undefined): string {
  if (f == null) return "#6b7280";
  if (f >= 0.7) return "#EF5350";
  if (f >= 0.4) return "#F59E0B";
  return "#26A69A";
}

function freqLabel(f: number | null | undefined): string {
  if (f == null) return "—";
  if (f >= 0.7) return "Alta";
  if (f >= 0.4) return "Média";
  return "Baixa";
}

const VIES_LABELS: Record<string, string> = {
  disposition_effect:    "Efeito Disposição",
  overtrading:           "Overtrading",
  subdiversificacao:     "Subdiversificação",
  clustering_temporal:   "Clustering Temporal",
  trend_chasing:         "Trend Chasing",
};

export default function PerfilComportamental({ vieses, periodo }: PerfilComportamentalProps) {
  if (!vieses || vieses.length === 0) {
    return (
      <p className="text-[#6b7280] text-sm">Sem dados comportamentais disponíveis.</p>
    );
  }

  return (
    <div className="rounded-lg border border-[#2A2D3A] bg-[#1A1D27] my-2 overflow-hidden">
      <div className="px-3 py-2 border-b border-[#2A2D3A] flex items-center justify-between">
        <span className="text-xs font-medium text-[#D1D4DC]">Perfil Comportamental</span>
        {periodo && <span className="text-xs text-[#6b7280]">{periodo}</span>}
      </div>

      <div className="divide-y divide-[#2A2D3A]">
        {vieses.map((v) => {
          const label = VIES_LABELS[v.nome_vies] ?? v.nome_vies;
          const color = v.detectado ? freqColor(v.frequencia as number) : "#6b7280";
          return (
            <div key={v.nome_vies} className="flex items-start gap-3 px-3 py-2.5">
              <span className="mt-0.5 text-sm">{v.detectado ? "⚠️" : "✅"}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className="text-xs font-medium"
                    style={{ color }}
                  >
                    {label}
                  </span>
                  {v.detectado && (
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded-full border"
                      style={{
                        color,
                        borderColor: color + "40",
                        backgroundColor: color + "10",
                      }}
                    >
                      {freqLabel(v.frequencia as number)}
                    </span>
                  )}
                </div>
                {v.fato && (
                  <p className="text-xs text-[#6b7280] mt-0.5 leading-snug">
                    {v.fato as string}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-3 py-2 border-t border-[#2A2D3A]">
        <p className="text-[10px] text-[#6b7280]">
          Padrões factuais — não são diagnósticos. A interpretação é sua.
        </p>
      </div>
    </div>
  );
}
