"use client";

import React from "react";

interface SemaforoTeseProps {
  ticker: string;
  tese: string;
  status: "ATIVA" | "INVALIDA" | "REVISAO" | string;
  convicao?: number | null;
  invalidacao?: string | null;
  data_criacao?: string | null;
  dias_desde_criacao?: number | null;
}

const STATUS_CONFIG: Record<string, { cor: string; label: string; emoji: string }> = {
  ATIVA:    { cor: "#26A69A", label: "Ativa",   emoji: "🟢" },
  REVISAO:  { cor: "#F59E0B", label: "Revisão", emoji: "🟡" },
  INVALIDA: { cor: "#EF5350", label: "Inválida", emoji: "🔴" },
};

function getStatus(s: string) {
  return STATUS_CONFIG[s] ?? { cor: "#6b7280", label: s, emoji: "⚪" };
}

export default function SemaforoTese({
  ticker,
  tese,
  status,
  convicao,
  invalidacao,
  data_criacao,
  dias_desde_criacao,
}: SemaforoTeseProps) {
  const cfg = getStatus(status);

  return (
    <div
      className="rounded-lg border bg-[#1A1D27] p-4 my-2"
      style={{ borderColor: cfg.cor + "40" }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{cfg.emoji}</span>
          <span className="font-mono text-[#26A69A] font-semibold text-sm">{ticker}</span>
          <span
            className="text-xs px-1.5 py-0.5 rounded-full border"
            style={{ color: cfg.cor, borderColor: cfg.cor + "40", backgroundColor: cfg.cor + "10" }}
          >
            {cfg.label}
          </span>
        </div>
        {convicao != null && (
          <div className="flex items-center gap-1" title={`Convicção ${convicao}/5`}>
            {Array.from({ length: 5 }, (_, i) => (
              <div
                key={i}
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: i < convicao ? cfg.cor : "#2A2D3A" }}
              />
            ))}
          </div>
        )}
      </div>

      <p className="text-[#D1D4DC] text-sm leading-relaxed">{tese}</p>

      {invalidacao && (
        <div className="mt-3 pt-3 border-t border-[#2A2D3A]">
          <p className="text-xs text-[#6b7280]">
            <span className="text-[#F59E0B] font-medium">Invalidação:</span> {invalidacao}
          </p>
        </div>
      )}

      {(data_criacao || dias_desde_criacao != null) && (
        <div className="mt-2 flex gap-3 text-[10px] text-[#6b7280]">
          {data_criacao && <span>Criada em {data_criacao}</span>}
          {dias_desde_criacao != null && <span>{dias_desde_criacao}d atrás</span>}
        </div>
      )}
    </div>
  );
}
