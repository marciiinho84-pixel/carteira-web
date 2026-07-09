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
  RSI:         { label: "RSI",        icon: "📈", cor: "var(--purple-accent)" },
  preco:       { label: "Preço",      icon: "💲", cor: "var(--positive)" },
  banda_IPS:   { label: "Banda IPS",  icon: "⚖️", cor: "var(--warning)" },
  invalidacao: { label: "Invalidação", icon: "🔬", cor: "var(--negative)" },
};

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

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
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 space-y-4 overflow-auto">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1
              className="text-2xl font-semibold flex items-center gap-2"
              style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
            >
              <span>🔔</span> Alertas
            </h1>
            <p className="text-xs mt-1.5" style={{ color: "var(--text-muted)" }}>
              Gatilhos monitorados. Cadastre novos pelo{" "}
              <Link href="/maestro" className="hover:underline" style={{ color: "var(--accent-strong)" }}>Maestro</Link>{" "}
              (ex: &quot;cria um alerta de RSI da WEGE3 ≥ 70&quot;).
            </p>
          </div>
          <button
            onClick={load}
            className="rounded-lg px-3 py-2 text-sm border transition"
            style={{ whiteSpace: "nowrap", borderColor: "var(--border)", color: "var(--text-body)" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            ↻ Atualizar
          </button>
        </div>

        {loading && (
          <div className="animate-pulse space-y-2">
            <div className="h-14 rounded-xl" style={{ background: "var(--bg-card)" }} />
            <div className="h-14 rounded-xl" style={{ background: "var(--bg-card)" }} />
          </div>
        )}

        {error && (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
          >
            {error}
          </div>
        )}

        {!loading && !error && alertas.length === 0 && (
          <div
            className="rounded-xl border px-5 py-10 text-center"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <p className="text-3xl mb-2">🔕</p>
            <p className="text-sm" style={{ color: "var(--text-body)" }}>Nenhum alerta cadastrado.</p>
            <p className="text-xs mt-1" style={{ color: "var(--text-faint)" }}>
              Peça ao Maestro para criar um gatilho de RSI, preço, banda IPS ou invalidação de tese.
            </p>
          </div>
        )}

        {!loading && alertas.length > 0 && (
          <div className="space-y-2">
            {alertas.map((a) => {
              const meta = TIPO_META[a.tipo] ?? { label: a.tipo, icon: "🔔", cor: "var(--text-faint)" };
              const disparado = !!a.disparado_em;
              return (
                <div
                  key={a.id}
                  className="rounded-xl border px-4 py-3 flex items-center gap-4 flex-wrap transition"
                  style={{
                    borderColor: disparado ? "rgba(201,134,43,0.5)" : "var(--border)",
                    background: "var(--bg-card)",
                    boxShadow: cardShadow,
                    opacity: a.habilitado ? 1 : 0.55,
                  }}
                >
                  {/* Tipo */}
                  <div className="flex items-center gap-2 min-w-[110px]">
                    <span className="text-lg">{meta.icon}</span>
                    <span
                      className="rounded-md px-2 py-0.5 text-[10px] font-bold border"
                      style={{ whiteSpace: "nowrap", color: meta.cor, borderColor: meta.cor, background: "var(--bg-app)" }}
                    >
                      {meta.label}
                    </span>
                  </div>

                  {/* Condição */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: "var(--text-body)" }}>{descreveCondicao(a)}</p>
                    <p className="text-[10px] mt-0.5" style={{ color: "var(--text-faint)" }}>
                      Criado em {fmtData(a.criado_em)}
                      {disparado && (
                        <span style={{ color: "var(--warning)" }}> · ⚠ disparou em {fmtData(a.disparado_em)}</span>
                      )}
                    </p>
                  </div>

                  {/* Status */}
                  <div className="text-right">
                    {disparado ? (
                      <span className="text-[11px] font-semibold" style={{ whiteSpace: "nowrap", color: "var(--warning)" }}>Disparado</span>
                    ) : a.habilitado ? (
                      <span className="text-[11px] font-semibold" style={{ whiteSpace: "nowrap", color: "var(--positive)" }}>Monitorando</span>
                    ) : (
                      <span className="text-[11px] font-semibold" style={{ whiteSpace: "nowrap", color: "var(--text-faint)" }}>Pausado</span>
                    )}
                  </div>

                  {/* Ações */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => toggle(a)}
                      disabled={busy === a.id}
                      className="rounded-lg px-2.5 py-1 text-xs border transition disabled:opacity-40"
                      style={{ whiteSpace: "nowrap", borderColor: "var(--border)", color: "var(--text-body)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      title={a.habilitado ? "Pausar" : "Reativar"}
                    >
                      {a.habilitado ? "⏸ Pausar" : "▶ Reativar"}
                    </button>
                    <button
                      onClick={() => excluir(a)}
                      disabled={busy === a.id}
                      className="rounded-lg px-2.5 py-1 text-xs border transition disabled:opacity-40"
                      style={{ borderColor: "var(--border)", color: "var(--text-faint)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.color = "var(--negative)"; e.currentTarget.style.borderColor = "rgba(180,68,44,0.5)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-faint)"; e.currentTarget.style.borderColor = "var(--border)"; }}
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
