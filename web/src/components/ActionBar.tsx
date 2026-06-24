"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function ActionBar() {
  const [updating, setUpdating] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  function flash(msg: string, isErr = false) {
    if (isErr) { setErr(msg); setTimeout(() => setErr(null), 5000); }
    else { setOk(msg); setTimeout(() => setOk(null), 5000); }
  }

  async function atualizar() {
    setUpdating(true); setErr(null);
    try {
      await apiFetch("/calcular", { method: "POST" });
      flash("Cotações atualizadas e carteira recalculada!");
    } catch (e) { flash(e instanceof Error ? e.message : "Erro", true); }
    finally { setUpdating(false); }
  }

  async function recalcular() {
    setRecalculating(true); setErr(null);
    try {
      await apiFetch("/calcular?no_api=true", { method: "POST" });
      flash("Carteira recalculada!");
    } catch (e) { flash(e instanceof Error ? e.message : "Erro", true); }
    finally { setRecalculating(false); }
  }

  const busy = updating || recalculating;

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-[#2A2D3A] bg-[#0F1117]/80 backdrop-blur sticky top-0 z-30">
      {ok && <span className="text-xs text-[#26A69A]">✓ {ok}</span>}
      {err && <span className="text-xs text-[#EF5350]">✕ {err}</span>}
      {!ok && !err && <span className="text-xs text-[#6b7280]">Dados ao vivo</span>}
      <div className="ml-auto flex gap-2">
        <button
          onClick={atualizar}
          disabled={busy}
          className="rounded px-3 py-1.5 text-xs font-medium border border-[#26A69A]/40 text-[#26A69A] bg-[#26A69A]/10 hover:bg-[#26A69A]/20 disabled:opacity-40 transition"
        >
          {updating ? "Atualizando…" : "⟳ Atualizar cotações"}
        </button>
        <button
          onClick={recalcular}
          disabled={busy}
          className="rounded px-3 py-1.5 text-xs font-medium border border-[#2A2D3A] text-[#D1D4DC] bg-[#1A1D27] hover:bg-[#2A2D3A] disabled:opacity-40 transition"
        >
          {recalculating ? "Recalculando…" : "⚡ Recalcular"}
        </button>
      </div>
    </div>
  );
}
