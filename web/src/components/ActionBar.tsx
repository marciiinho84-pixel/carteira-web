"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import { useRefreshSignal } from "@/lib/refresh-context";

export default function ActionBar() {
  const [updating, setUpdating] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { triggerRefresh } = useRefreshSignal();

  function flash(msg: string, isErr = false) {
    if (isErr) { setErr(msg); setTimeout(() => setErr(null), 5000); }
    else { setOk(msg); setTimeout(() => setOk(null), 5000); }
  }

  async function atualizar() {
    setUpdating(true); setErr(null);
    try {
      await apiFetch("/calcular", { method: "POST" });
      flash("Cotações atualizadas e carteira recalculada!");
      triggerRefresh();
    } catch (e) { flash(e instanceof Error ? e.message : "Erro", true); }
    finally { setUpdating(false); }
  }

  async function recalcular() {
    setRecalculating(true); setErr(null);
    try {
      await apiFetch("/calcular?no_api=true", { method: "POST" });
      flash("Carteira recalculada!");
      triggerRefresh();
    } catch (e) { flash(e instanceof Error ? e.message : "Erro", true); }
    finally { setRecalculating(false); }
  }

  const busy = updating || recalculating;

  return (
    <div
      className="flex items-center gap-3 px-4 py-2 border-b backdrop-blur sticky top-0 z-30"
      style={{ borderColor: "var(--border)", background: "rgba(244,238,226,0.85)" }}
    >
      {ok && <span className="text-xs" style={{ color: "var(--positive)" }}>✓ {ok}</span>}
      {err && <span className="text-xs" style={{ color: "var(--negative)" }}>✕ {err}</span>}
      {!ok && !err && <span className="text-xs" style={{ color: "var(--text-muted)" }}>Dados ao vivo</span>}
      <div className="ml-auto flex gap-2">
        <button
          onClick={atualizar}
          disabled={busy}
          className="rounded-lg px-3 py-1.5 text-xs font-medium border disabled:opacity-40 transition"
          style={{ borderColor: "rgba(193,95,60,0.4)", color: "var(--accent-strong)", background: "rgba(193,95,60,0.08)" }}
        >
          {updating ? "Atualizando…" : "⟳ Atualizar cotações"}
        </button>
        <button
          onClick={recalcular}
          disabled={busy}
          className="rounded-lg px-3 py-1.5 text-xs font-medium border disabled:opacity-40 transition"
          style={{ borderColor: "var(--border)", color: "var(--text-body)", background: "var(--bg-card)" }}
        >
          {recalculating ? "Recalculando…" : "⚡ Recalcular"}
        </button>
      </div>
    </div>
  );
}
