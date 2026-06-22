"use client";

import React, { useState } from "react";
import { apiFetch } from "@/lib/api";

interface FormularioTeseProps {
  tickerInicial?: string;
  onSuccess?: () => void;
}

interface TesePayload {
  ticker: string;
  tese: string;
  invalidacao: string;
  convicao: number;
  horizonte?: string;
}

export default function FormularioTese({ tickerInicial = "", onSuccess }: FormularioTeseProps) {
  const [ticker, setTicker] = useState(tickerInicial);
  const [tese, setTese] = useState("");
  const [invalidacao, setInvalidacao] = useState("");
  const [convicao, setConvicao] = useState(3);
  const [horizonte, setHorizonte] = useState("médio prazo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim() || !tese.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const payload: TesePayload = {
        ticker: ticker.toUpperCase().trim(),
        tese: tese.trim(),
        invalidacao: invalidacao.trim(),
        convicao,
        horizonte,
      };
      await apiFetch("/teses", { method: "POST", body: JSON.stringify(payload) });
      setSuccess(true);
      setTese("");
      setInvalidacao("");
      setConvicao(3);
      onSuccess?.();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar tese");
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
        <span className="text-sm font-medium text-[#D1D4DC]">Registrar Tese</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Ticker *</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="WEGE3"
            className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] font-mono placeholder-[#6b7280] focus:outline-none focus:border-[#26A69A]"
            required
          />
        </div>
        <div>
          <label className="block text-xs text-[#6b7280] mb-1">Horizonte</label>
          <select
            value={horizonte}
            onChange={(e) => setHorizonte(e.target.value)}
            className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]"
          >
            <option value="curto prazo">Curto prazo</option>
            <option value="médio prazo">Médio prazo</option>
            <option value="longo prazo">Longo prazo</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-1">Tese *</label>
        <textarea
          value={tese}
          onChange={(e) => setTese(e.target.value)}
          placeholder="Por que você acredita neste ativo?"
          rows={3}
          className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] placeholder-[#6b7280] focus:outline-none focus:border-[#26A69A] resize-none"
          required
        />
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-1">Critério de invalidação</label>
        <textarea
          value={invalidacao}
          onChange={(e) => setInvalidacao(e.target.value)}
          placeholder="Quando você sairia? Qual evento invalidaria a tese?"
          rows={2}
          className="w-full bg-[#0F1117] border border-[#2A2D3A] rounded px-3 py-1.5 text-xs text-[#D1D4DC] placeholder-[#6b7280] focus:outline-none focus:border-[#26A69A] resize-none"
        />
      </div>

      <div>
        <label className="block text-xs text-[#6b7280] mb-2">
          Convicção: <span className="text-[#26A69A] font-medium">{convicao}/5</span>
        </label>
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setConvicao(n)}
              className="w-8 h-8 rounded-full border text-xs font-medium transition-all"
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

      {error && (
        <p className="text-xs text-[#EF5350] bg-[#EF5350]/10 rounded p-2">{error}</p>
      )}
      {success && (
        <p className="text-xs text-[#26A69A] bg-[#26A69A]/10 rounded p-2">
          Tese registrada com sucesso!
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !ticker.trim() || !tese.trim()}
        className="w-full py-2 rounded text-xs font-medium transition-all disabled:opacity-50"
        style={{
          backgroundColor: "#26A69A",
          color: "#0F1117",
        }}
      >
        {loading ? "Salvando..." : "Registrar Tese"}
      </button>
    </form>
  );
}
