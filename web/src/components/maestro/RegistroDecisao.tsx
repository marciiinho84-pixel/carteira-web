"use client";

import React, { useState } from "react";
import { apiFetch } from "@/lib/api";

interface RegistroDecisaoProps {
  ticker?: string;
  acao?: "COMPRA" | "VENDA" | "MANUTENCAO";
  onSuccess?: () => void;
}

interface DecisaoPayload {
  ticker: string;
  acao: string;
  racional: string;
  convicao: number;
  horizonte?: string;
}

export default function RegistroDecisao({
  ticker: tickerProp = "",
  acao: acaoProp = "COMPRA",
  onSuccess,
}: RegistroDecisaoProps) {
  const [ticker, setTicker] = useState(tickerProp);
  const [acao, setAcao] = useState<string>(acaoProp);
  const [racional, setRacional] = useState("");
  const [convicao, setConvicao] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || !racional.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const payload: DecisaoPayload = {
        ticker: ticker.toUpperCase().trim(),
        acao,
        racional: racional.trim(),
        convicao,
      };
      await apiFetch("/diario-decisoes", { method: "POST", body: JSON.stringify(payload) });
      setSuccess(true);
      setRacional("");
      setConvicao(3);
      onSuccess?.();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar decisão");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-[#2A2D3A] bg-[#1A1D27] p-4 my-2 space-y-3"
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-medium text-[#D1D4DC]">Registrar Decisão</span>
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <label className="block text-xs text-[#6b7280] mb-1">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="WEGE3"
            className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] font-mono placeholder-[#6b7280] focus:outline-none focus:border-[#26A69A]"
            required
          />
        </div>

        <div className="w-32">
          <label className="block text-xs text-[#6b7280] mb-1">Ação</label>
          <select
            value={acao}
            onChange={(e) => setAcao(e.target.value)}
            className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-2 py-1.5 text-xs text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]"
          >
            <option value="COMPRA">Compra</option>
            <option value="VENDA">Venda</option>
            <option value="MANUTENCAO">Manutenção</option>
            <option value="AUMENTO">Aumento</option>
            <option value="REDUCAO">Redução</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-1">Racional</label>
        <textarea
          value={racional}
          onChange={(e) => setRacional(e.target.value)}
          placeholder="Por que esta decisão agora?"
          rows={2}
          className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] placeholder-[#6b7280] focus:outline-none focus:border-[#26A69A] resize-none"
          required
        />
      </div>

      <div className="flex items-center gap-4">
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">
            Convicção <span className="text-[#26A69A]">{convicao}/5</span>
          </label>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setConvicao(n)}
                className="w-7 h-7 rounded border text-xs font-medium transition-all"
                style={{
                  borderColor: n <= convicao ? "#26A69A" : "#2A2D3A",
                  backgroundColor: n <= convicao ? "#26A69A20" : "transparent",
                  color: n <= convicao ? "#26A69A" : "#6b7280",
                }}
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !ticker.trim() || !racional.trim()}
          className="ml-auto px-4 py-2 rounded text-xs font-medium transition-all disabled:opacity-50"
          style={{ backgroundColor: "#26A69A", color: "#0F1117" }}
        >
          {loading ? "..." : "Registrar"}
        </button>
      </div>

      {error && (
        <p className="text-xs text-[#EF5350] bg-[#EF5350]/10 rounded p-2">{error}</p>
      )}
      {success && (
        <p className="text-xs text-[#26A69A] bg-[#26A69A]/10 rounded p-2">
          Decisão registrada!
        </p>
      )}
    </form>
  );
}
