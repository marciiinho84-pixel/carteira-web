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
      className="rounded-lg border p-4 my-2 space-y-3"
      style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Registrar Tese</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-faint)" }}>Ticker *</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="WEGE3"
            className="w-full rounded px-3 py-1.5 text-xs border focus:outline-none"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}
            required
          />
        </div>
        <div>
          <label className="block text-xs mb-1" style={{ color: "var(--text-faint)" }}>Horizonte</label>
          <select
            value={horizonte}
            onChange={(e) => setHorizonte(e.target.value)}
            className="w-full rounded px-3 py-1.5 text-xs border focus:outline-none"
            style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)" }}
          >
            <option value="curto prazo">Curto prazo</option>
            <option value="médio prazo">Médio prazo</option>
            <option value="longo prazo">Longo prazo</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs mb-1" style={{ color: "var(--text-faint)" }}>Tese *</label>
        <textarea
          value={tese}
          onChange={(e) => setTese(e.target.value)}
          placeholder="Por que você acredita neste ativo?"
          rows={3}
          className="w-full rounded px-3 py-1.5 text-xs border focus:outline-none resize-none"
          style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)" }}
          required
        />
      </div>

      <div>
        <label className="block text-xs mb-1" style={{ color: "var(--text-faint)" }}>Critério de invalidação</label>
        <textarea
          value={invalidacao}
          onChange={(e) => setInvalidacao(e.target.value)}
          placeholder="Quando você sairia? Qual evento invalidaria a tese?"
          rows={2}
          className="w-full rounded px-3 py-1.5 text-xs border focus:outline-none resize-none"
          style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)" }}
        />
      </div>

      <div>
        <label className="block text-xs mb-2" style={{ color: "var(--text-faint)" }}>
          Convicção: <span className="font-medium" style={{ color: "var(--positive)" }}>{convicao}/5</span>
        </label>
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setConvicao(n)}
              className="w-8 h-8 rounded-full border text-xs font-medium transition-all"
              style={{
                borderColor: n <= convicao ? "var(--positive)" : "var(--border)",
                backgroundColor: n <= convicao ? "rgba(74,124,89,0.14)" : "transparent",
                color: n <= convicao ? "var(--positive)" : "var(--text-faint)",
              }}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="text-xs rounded p-2" style={{ color: "var(--negative)", background: "rgba(180,68,44,0.08)" }}>{error}</p>
      )}
      {success && (
        <p className="text-xs rounded p-2" style={{ color: "var(--positive)", background: "rgba(74,124,89,0.08)" }}>
          Tese registrada com sucesso!
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !ticker.trim() || !tese.trim()}
        className="w-full py-2 rounded text-xs font-semibold transition-all disabled:opacity-50"
        style={{
          background: "var(--accent)",
          color: "var(--bg-card)",
        }}
      >
        {loading ? "Salvando..." : "Registrar Tese"}
      </button>
    </form>
  );
}
