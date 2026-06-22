"use client";

import { useState, useEffect, useCallback } from "react";

// ── Tipos ────────────────────────────────────────────────────────────────────

export type NivelAutomacao = "L1" | "L2" | "L3" | "L4";

export const NIVEL_LABELS: Record<NivelAutomacao, string> = {
  L1: "L1 — Observação",
  L2: "L2 — Sugestão",
  L3: "L3 — Aprovar/Rejeitar",
  L4: "L4 — Automático",
};

export const NIVEL_DESCRICAO: Record<NivelAutomacao, string> = {
  L1: "O Maestro observa e reporta. Nenhuma ação sugerida.",
  L2: "O Maestro sugere ações. Você decide se executa.",
  L3: "O Maestro propõe ações concretas. Você aprova ou rejeita cada uma.",
  L4: "O Maestro executa automaticamente dentro das regras do IPS.",
};

export type BlocoIPS = "SWING_TRADE" | "GROWTH" | "DEFENSIVOS" | "RENDA_FIXA" | "FORA_IPS";

export const BLOCO_LABELS: Record<BlocoIPS, string> = {
  SWING_TRADE: "Swing Trade",
  GROWTH:      "Growth",
  DEFENSIVOS:  "Defensivos",
  RENDA_FIXA:  "Renda Fixa",
  FORA_IPS:    "Fora IPS",
};

export type ConfigAutomacao = Record<BlocoIPS, NivelAutomacao>;

const DEFAULT_CONFIG: ConfigAutomacao = {
  SWING_TRADE: "L1",
  GROWTH:      "L1",
  DEFENSIVOS:  "L1",
  RENDA_FIXA:  "L1",
  FORA_IPS:    "L1",
};

const STORAGE_KEY = "carteira_automacao";

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useAutomacao() {
  const [config, setConfigState] = useState<ConfigAutomacao>(DEFAULT_CONFIG);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<ConfigAutomacao>;
        setConfigState({ ...DEFAULT_CONFIG, ...parsed });
      }
    } catch {
      // ignore parse errors
    }
    setLoaded(true);
  }, []);

  const setNivel = useCallback((bloco: BlocoIPS, nivel: NivelAutomacao) => {
    setConfigState((prev) => {
      const next = { ...prev, [bloco]: nivel };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  }, []);

  const nivelMaximo: NivelAutomacao = (
    Object.values(config).sort().reverse()[0] as NivelAutomacao
  ) ?? "L1";

  return { config, setNivel, nivelMaximo, loaded };
}
