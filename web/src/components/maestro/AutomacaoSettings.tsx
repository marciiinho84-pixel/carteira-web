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
  L1: "var(--text-faint)",
  L2: "var(--positive)",
  L3: "var(--warning)",
  L4: "var(--negative)",
};

export default function AutomacaoSettings() {
  const { config, setNivel, loaded } = useAutomacao();

  if (!loaded) {
    return (
      <div className="text-sm py-4 text-center" style={{ color: "var(--text-faint)" }}>
        Carregando configurações...
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm font-medium" style={{ color: "var(--text-body)" }}>Nível de Automação por Bloco IPS</span>
        <span className="text-xs" style={{ color: "var(--text-faint)" }}>— salvo automaticamente</span>
      </div>

      {BLOCOS.map((bloco) => {
        const nivel = config[bloco];
        return (
          <div
            key={bloco}
            className="flex items-center gap-3 p-3 rounded-lg border"
            style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}
          >
            <span className="w-28 text-xs font-medium shrink-0" style={{ color: "var(--text-body)" }}>
              {BLOCO_LABELS[bloco]}
            </span>
            <select
              value={nivel}
              onChange={(e) => setNivel(bloco, e.target.value as NivelAutomacao)}
              className="flex-1 rounded px-2 py-1.5 text-xs border focus:outline-none cursor-pointer"
              style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: NIVEL_COLOR[nivel] }}
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

      <div className="mt-4 p-3 rounded-lg border" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
          <span className="font-medium" style={{ color: "var(--positive)" }}>L1</span> Observação &bull;{" "}
          <span className="font-medium" style={{ color: "var(--warning)" }}>L2</span> Sugestão &bull;{" "}
          <span className="font-medium" style={{ color: "var(--warning)" }}>L3</span> Aprovar/Rejeitar &bull;{" "}
          <span className="font-medium" style={{ color: "var(--negative)" }}>L4</span> Automático
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-faint)" }}>
          L4 ainda não está disponível nesta versão.
        </p>
      </div>

      {/* Descrição do nível selecionado mais alto */}
      <div className="space-y-1">
        {NIVEIS.filter((n) => Object.values(config).includes(n)).map((n) => (
          <p key={n} className="text-xs" style={{ color: "var(--text-muted)" }}>
            <span style={{ color: NIVEL_COLOR[n] }} className="font-medium">{n}</span>:{" "}
            {NIVEL_DESCRICAO[n]}
          </p>
        ))}
      </div>
    </div>
  );
}
