"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";
import AutomacaoSettings from "@/components/maestro/AutomacaoSettings";

interface KpiInfo {
  calculado_em?: string;
  nivel_automacao?: string;
}

function relativeTime(iso: string | undefined): string {
  if (!iso) return "nunca";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}min atrás`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h atrás`;
  return `${Math.floor(hrs / 24)}d atrás`;
}

interface MacroStatusData {
  coletas?: { timestamp?: string }[];
  ultimo_timestamp?: string;
}

export default function Configuracoes() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [kpis, setKpis] = useState<KpiInfo | null>(null);
  const [macroTs, setMacroTs] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalcStatus, setRecalcStatus] = useState<string | null>(null);
  const [macroStatus, setMacroStatus] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      setLoading(true);
      try {
        const [me, sd] = await Promise.all([
          apiFetch<{ email: string }>("/auth/me"),
          apiFetch<{ kpis?: KpiInfo }>("/sala-de-comando").catch(() => null),
        ]);
        setEmail(me.email);
        if (sd?.kpis) setKpis(sd.kpis);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "";
        if (msg.includes("401") || msg.includes("Unauthorized")) {
          clearToken();
          router.replace("/login");
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  async function recalcular() {
    setRecalcStatus("Recalculando…");
    try {
      await apiFetch("/calcular", { method: "POST" });
      const sd = await apiFetch<{ kpis?: KpiInfo }>("/sala-de-comando");
      if (sd?.kpis) setKpis(sd.kpis);
      setRecalcStatus("Engine recalculado com sucesso.");
    } catch (e: unknown) {
      setRecalcStatus("Erro: " + (e instanceof Error ? e.message : "falha"));
    }
  }

  async function coletarMacro() {
    setMacroStatus("Coletando dados macro…");
    try {
      const res = await apiFetch<MacroStatusData>("/macro/coletar", { method: "POST" });
      const ts = res?.ultimo_timestamp ?? (res?.coletas?.[0]?.timestamp);
      setMacroTs(ts ?? null);
      setMacroStatus("Coleta concluída.");
    } catch (e: unknown) {
      setMacroStatus("Erro: " + (e instanceof Error ? e.message : "falha"));
    }
  }

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 max-w-2xl space-y-6 overflow-auto">
        <h1 className="text-lg font-bold text-white">Configurações</h1>

        {loading && <div className="animate-pulse h-48 rounded-xl bg-[#1A1D27]" />}

        {!loading && (
          <>
            {/* Info do usuário */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Conta</h2>
              <div className="flex justify-between text-sm">
                <span className="text-[#6b7280]">Email</span>
                <span className="text-[#26A69A]">{email ?? "—"}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#6b7280]">Versão</span>
                <span className="font-mono text-[#D1D4DC]">v2.5.1</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#6b7280]">Engine calculado</span>
                <span className="text-[#D1D4DC] font-mono text-xs">{relativeTime(kpis?.calculado_em)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-[#6b7280]">Nível de automação</span>
                <span className="text-[#6366F1] font-bold">{kpis?.nivel_automacao ?? "—"}</span>
              </div>
            </section>

            {/* Automação L1-L4 */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Automação L1-L4</h2>
              <AutomacaoSettings />
            </section>

            {/* Coleta de dados */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Coleta de Dados Macro</h2>
              <p className="text-xs text-[#6b7280]">
                Coleta dados do BCB (SGS), Focus e yfinance. Pode levar até 30s.
              </p>
              <div className="flex items-center gap-4">
                <button
                  onClick={coletarMacro}
                  className="rounded-lg px-4 py-2 text-sm font-medium bg-[#1A1D27] border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
                >
                  Coletar macro agora
                </button>
                {macroTs && (
                  <span className="text-xs text-[#6b7280]">Última coleta: {relativeTime(macroTs)}</span>
                )}
              </div>
              {macroStatus && (
                <p className={`text-xs ${macroStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>
                  {macroStatus}
                </p>
              )}
            </section>

            {/* Recalcular engine */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Engine de Cálculo</h2>
              <p className="text-xs text-[#6b7280]">
                Recalcula posições, TWR, P&amp;L e benchmarks a partir do event log.
              </p>
              <div className="flex items-center gap-4">
                <button
                  onClick={recalcular}
                  className="rounded-lg px-4 py-2 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 transition"
                >
                  Recalcular engine
                </button>
                {kpis?.calculado_em && (
                  <span className="text-xs text-[#6b7280]">
                    Último cálculo: {relativeTime(kpis.calculado_em)}
                  </span>
                )}
              </div>
              {recalcStatus && (
                <p className={`text-xs ${recalcStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>
                  {recalcStatus}
                </p>
              )}
            </section>

            {/* Paleta */}
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Paleta de Cores (TradingView-inspired)</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  { label: "Background", hex: "#0F1117" },
                  { label: "Card", hex: "#1A1D27" },
                  { label: "Borda", hex: "#2A2D3A" },
                  { label: "Teal", hex: "#26A69A" },
                  { label: "Vermelho", hex: "#EF5350" },
                  { label: "Texto", hex: "#D1D4DC" },
                  { label: "Roxo", hex: "#6366F1" },
                  { label: "Âmbar", hex: "#F59E0B" },
                ].map((c) => (
                  <div key={c.label} className="flex items-center gap-2 text-xs">
                    <div className="w-5 h-5 rounded border border-[#2A2D3A]" style={{ backgroundColor: c.hex }} />
                    <div>
                      <p className="text-[#D1D4DC]">{c.label}</p>
                      <p className="text-[#6b7280] font-mono">{c.hex}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
