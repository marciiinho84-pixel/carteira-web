"use client";

import React from "react";

interface GraficoTecnicoProps {
  htmlContent: string;
  ticker?: string;
  height?: number;
}

export default function GraficoTecnico({
  htmlContent,
  ticker,
  height = 500,
}: GraficoTecnicoProps) {
  return (
    <div className="rounded-lg border border-[#2A2D3A] overflow-hidden bg-[#0F1117] my-2">
      {ticker && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[#2A2D3A]">
          <span className="text-xs font-mono text-[#26A69A] font-medium">{ticker}</span>
          <span className="text-xs text-[#6b7280]">Gráfico Técnico</span>
        </div>
      )}
      <div
        className="overflow-hidden"
        style={{ height }}
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
}
