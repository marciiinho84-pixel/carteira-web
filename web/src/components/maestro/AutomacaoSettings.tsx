"use client";

import React from "react";
import {
  useAutomacao,
  NIVEL_LABELS,
  NIVEL_DESCRICAO,
  BLOCO_LABELS,
  type BlocoIPS,
  type NivelAutomacao,
} from "@/lib/automacao";

const NIVEIS: NivelAutomacao[] = ["L1", "L2", "L3", "L4"];
const BLOCOS: BlocoIPS[] = ["SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];

const NIVEL_COLOR: Record<NivelAutomacao, string> = {
  L1: "#6b7280",
  L2: "#26A69A",
  L3: "#F59E0B",
  L4: "#EF5350",
};

export default function AutomacaoSettings() {
  const { config, setNivel, loaded } = useAutomacao();

  if (!loaded) {
    return (
      <div className="text-[#6b7280] text-sm py-4 text-center">
        Carregando configurações...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-[#D1D4DC] text-sm font-medium">Nível de Automação por Bloco IPS</span>
        <span className="text-xs text-[#6b7280]">— salvo automaticamente</span>
      </div>

      {BLOCOS.map((bloco) => {
        const nivel = config[bloco];
        return (
          <div
            key={bloco}
            className="flex items-center gap-3 p-3 rounded-lg border border-[#2A2D3A] bg-[#0F1117]"
          >
            <span className="w-28 text-[#D1D4DC] text-xs font-medium shrink-0">
              {BLOCO_LABELS[bloco]}
            </span>
            <select
              value={nivel}
              onChange={(e) => setNivel(bloco, e.target.value as NivelAutomacao)}
              className="flex-1 bg-[#1A1D27] border border-[#2A2D3A] rounded px-2 py-1.5 text-xs text-[#D1D4DC] focus:outline-none focus:border-[#26A69A] cursor-pointer"
              style={{ color: NIVEL_COLOR[nivel] }}
            >
              {NIVEIS.map((n) => (
                <option key={n} value={n} style={{ color: NIVEL_COLOR[n] }}>
                  {NIVEL_LABELS[n]}
                </option>
              ))}
            </select>
          </div>
        );
      })}

      <div className="mt-4 p-3 rounded-lg border border-[#2A2D3A] bg-[#0F1117]">
        <p className="text-xs text-[#6b7280] leading-relaxed">
          <span className="text-[#26A69A] font-medium">L1</span> Observação &bull;{" "}
          <span className="text-[#F59E0B] font-medium">L2</span> Sugestão &bull;{" "}
          <span className="text-[#F59E0B] font-medium">L3</span> Aprovar/Rejeitar &bull;{" "}
          <span className="text-[#EF5350] font-medium">L4</span> Automático
        </p>
        <p className="text-xs text-[#6b7280] mt-1">
          L4 ainda não está disponível nesta versão.
        </p>
      </div>

      {/* Descrição do nível selecionado mais alto */}
      <div className="space-y-1">
        {NIVEIS.filter((n) => Object.values(config).includes(n)).map((n) => (
          <p key={n} className="text-xs text-[#6b7280]">
            <span style={{ color: NIVEL_COLOR[n] }} className="font-medium">{n}</span>:{" "}
            {NIVEL_DESCRICAO[n]}
          </p>
        ))}
      </div>
    </div>
  );
}
