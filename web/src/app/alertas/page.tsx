"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("carteira_token");
}

interface Alerta {
  id: number;
  tipo: "RSI" | "banda_IPS" | "preco" | "invalidacao";
  ativo?: string | null;
  condicao: string;
  valor_gatilho?: number | null;
  habilitado: boolean;
  disparado_em?: string | null;
  criado_em?: string | null;
}

const TIPO_META: Record<string, { label: string; icon: string; cor: string }> = {
  RSI:         { label: "RSI",        icon: "📈", cor: "#A78BFA" },
  preco:       { label: "Preço",      icon: "💲", cor: "#26A69A" },
  banda_IPS:   { label: "Banda IPS",  icon: "⚖️", cor: "#F59E0B" },
  invalidacao: { label: "Invalidação", icon: "🔬", cor: "#EF5350" },
};

function fmtData(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "2-digit" });
}

function descreveCondicao(a: Alerta): string {
  const alvo = a.ativo ?? "—";
  const v = a.valor_gatilho;
  if (a.tipo === "RSI") return `${alvo} RSI ${a.condicao} ${v ?? ""}`.trim();
  if (a.tipo === "preco") return `${alvo} preço ${a.condicao} ${v != null ? "R$ " + v : ""}`.trim();
  if (a.tipo === "banda_IPS") return `Bloco ${alvo} ${a.condicao}`;
  if (a.tipo === "invalidacao") return `Tese #${alvo} — ${a.condicao}`;
  return a.condicao;
}

export default function Alertas() {
  const router = useRouter();
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<Alerta[]>("/alertas");
      setAlertas(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar";
      if (msg.includes("401") || msg.includes("Unauthorized")) {
        clearToken();
        router.replace("/login");
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const token = getToken();
    if (!token) { router.replace("/login"); return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function toggle(a: Alerta) {
    setBusy(a.id);
    const token = getToken();
    try {
      await fetch(`${API_BASE}/alertas/${a.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ habilitado: !a.habilitado }),
      });
      await load();
    } finally {
      setBusy(null);
    }
  }

  async function excluir(a: Alerta) {
    if (!confirm(`Excluir o alerta de ${a.ativo ?? a.tipo}?`)) return;
    setBusy(a.id);
    const token = getToken();
    try {
      await fetch(`${API_BASE}/alertas/${a.id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      await load();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <span>🔔</span> Alertas
            </h1>
            <p className="text-xs text-[#6b7280] mt-1">
              Gatilhos monitorados. Cadastre novos pelo{" "}
              <Link href="/maestro" className="text-[#26A69A] hover:underline">Maestro</Link>{" "}
              (ex: &quot;cria um alerta de RSI da WEGE3 ≥ 70&quot;).
            </p>
          </div>
          <button
            onClick={load}
            className="rounded-lg px-3 py-2 text-sm border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
          >
            ↻ Atualizar
          </button>
        </div>

        {loading && (
          <div className="animate-pulse space-y-2">
            <div className="h-14 rounded-xl bg-[#1A1D27]" />
            <div className="h-14 rounded-xl bg-[#1A1D27]" />
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {!loading && !error && alertas.length === 0 && (
          <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-10 text-center">
            <p className="text-3xl mb-2">🔕</p>
            <p className="text-sm text-[#D1D4DC]">Nenhum alerta cadastrado.</p>
            <p className="text-xs text-[#6b7280] mt-1">
              Peça ao Maestro para criar um gatilho de RSI, preço, banda IPS ou invalidação de tese.
            </p>
          </div>
        )}

        {!loading && alertas.length > 0 && (
          <div className="space-y-2">
            {alertas.map((a) => {
              const meta = TIPO_META[a.tipo] ?? { label: a.tipo, icon: "🔔", cor: "#6b7280" };
              const disparado = !!a.disparado_em;
              return (
                <div
                  key={a.id}
                  className={`rounded-xl border bg-[#1A1D27] px-4 py-3 flex items-center gap-4 flex-wrap transition ${
                    disparado ? "border-[#F59E0B]/50" : "border-[#2A2D3A]"
                  } ${!a.habilitado ? "opacity-50" : ""}`}
                >
                  {/* Tipo */}
                  <div className="flex items-center gap-2 min-w-[110px]">
                    <span className="text-lg">{meta.icon}</span>
                    <span
                      className="rounded-md px-2 py-0.5 text-[10px] font-bold border"
                      style={{ color: meta.cor, borderColor: meta.cor + "55", background: meta.cor + "15" }}
                    >
                      {meta.label}
                    </span>
                  </div>

                  {/* Condição */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#D1D4DC] truncate">{descreveCondicao(a)}</p>
                    <p className="text-[10px] text-[#6b7280] mt-0.5">
                      Criado em {fmtData(a.criado_em)}
                      {disparado && (
                        <span className="text-[#F59E0B]"> · ⚠️ disparou em {fmtData(a.disparado_em)}</span>
                      )}
                    </p>
                  </div>

                  {/* Status */}
                  <div className="text-right">
                    {disparado ? (
                      <span className="text-[11px] font-semibold text-[#F59E0B]">Disparado</span>
                    ) : a.habilitado ? (
                      <span className="text-[11px] font-semibold text-[#26A69A]">Monitorando</span>
                    ) : (
                      <span className="text-[11px] font-semibold text-[#6b7280]">Pausado</span>
                    )}
                  </div>

                  {/* Ações */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggle(a)}
                      disabled={busy === a.id}
                      className="rounded-lg px-2.5 py-1 text-xs border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition disabled:opacity-40"
                      title={a.habilitado ? "Pausar" : "Reativar"}
                    >
                      {a.habilitado ? "⏸ Pausar" : "▶ Reativar"}
                    </button>
                    <button
                      onClick={() => excluir(a)}
                      disabled={busy === a.id}
                      className="rounded-lg px-2.5 py-1 text-xs border border-[#2A2D3A] text-[#6b7280] hover:text-[#EF5350] hover:border-[#EF5350]/50 transition disabled:opacity-40"
                      title="Excluir"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
