"use client";

export const dynamic = "force-dynamic";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";
import AutomacaoSettings from "@/components/maestro/AutomacaoSettings";

// ── Types ──────────────────────────────────────────────────────────
interface Ativo {
  ticker: string;
  classe?: string;
  familia?: string;
  setor?: string;
  composite: string;
  bloco_ips?: string;
  observacao?: string;
  data_vencimento?: string;
}

interface PrecoManual { id: number; data: string; ticker: string; valor: number; fonte?: string }
interface RegraAporte { id: number; valor_mensal_alvo: number; tipo: string; criterio_oportunismo?: string; ativo: number; data_criacao: string }

const BLOCOS_IPS = ["SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];
const inputClass = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none transition";
const inputStyle = { background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" } as const;
const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

function relativeTime(iso: string | undefined): string {
  if (!iso) return "nunca";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}min atrás`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h atrás`;
  return `${Math.floor(hrs / 24)}d atrás`;
}

function brl(n: number | null | undefined): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function statusColor(s: string): string {
  return s.includes("Erro") ? "var(--negative)" : "var(--positive)";
}

type Tab = "sistema" | "ativos" | "precos" | "aportes";

export default function Configuracoes() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("sistema");

  // ── Sistema ──────────────────────────────────────────────────────
  const [email, setEmail] = useState<string | null>(null);
  const [kpis, setKpis] = useState<{ calculado_em?: string; nivel_automacao?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalcStatus, setRecalcStatus] = useState<string | null>(null);
  const [macroStatus, setMacroStatus] = useState<string | null>(null);

  // ── CAD_ATIVOS ────────────────────────────────────────────────────
  const [ativos, setAtivos] = useState<Ativo[]>([]);
  const [loadingAtivos, setLoadingAtivos] = useState(false);
  const [editAtivo, setEditAtivo] = useState<Ativo | null>(null);
  const [novoAtivo, setNovoAtivo] = useState<Partial<Ativo>>({ composite: "Gerida" });
  const [showNovoAtivo, setShowNovoAtivo] = useState(false);
  const [ativoStatus, setAtivoStatus] = useState<string | null>(null);
  const [ativoSearch, setAtivoSearch] = useState("");

  // ── Preços Manuais ───────────────────────────────────────────────
  const [precos, setPrecos] = useState<PrecoManual[]>([]);
  const [loadingPrecos, setLoadingPrecos] = useState(false);
  const [novoPreco, setNovoPreco] = useState({ ticker: "", data: new Date().toISOString().slice(0, 10), valor: "", fonte: "Manual" });
  const [precoStatus, setPrecoStatus] = useState<string | null>(null);

  // ── Regra de Aportes ─────────────────────────────────────────────
  const [regraAtiva, setRegraAtiva] = useState<RegraAporte | null>(null);
  const [novaRegra, setNovaRegra] = useState({ valor_mensal_alvo: "", tipo: "PROGRAMADO", criterio_oportunismo: "" });
  const [regraStatus, setRegraStatus] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    async function load() {
      try {
        const [me, sd] = await Promise.all([
          apiFetch<{ email: string }>("/auth/me"),
          apiFetch<{ kpis?: typeof kpis }>("/sala-de-comando").catch(() => null),
        ]);
        setEmail(me.email);
        if (sd?.kpis) setKpis(sd.kpis);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "";
        if (msg.includes("401")) { clearToken(); router.replace("/login"); }
      } finally { setLoading(false); }
    }
    load();
  }, [router]);

  const loadAtivos = useCallback(async () => {
    setLoadingAtivos(true);
    try { setAtivos(await apiFetch<Ativo[]>("/ativos")); }
    catch { /* ignore */ }
    finally { setLoadingAtivos(false); }
  }, []);

  const loadPrecos = useCallback(async () => {
    setLoadingPrecos(true);
    try { setPrecos(await apiFetch<PrecoManual[]>("/precos-manuais")); }
    catch { /* ignore */ }
    finally { setLoadingPrecos(false); }
  }, []);

  const loadRegra = useCallback(async () => {
    try { setRegraAtiva(await apiFetch<RegraAporte>("/regra-aportes/ativa")); }
    catch { /* ignore */ }
  }, []);

  useEffect(() => {
    if (tab === "ativos") loadAtivos();
    if (tab === "precos") loadPrecos();
    if (tab === "aportes") loadRegra();
  }, [tab, loadAtivos, loadPrecos, loadRegra]);

  // ── Sistema actions ───────────────────────────────────────────────
  async function recalcular() {
    setRecalcStatus("Recalculando…");
    try {
      await apiFetch("/calcular", { method: "POST" });
      const sd = await apiFetch<{ kpis?: typeof kpis }>("/sala-de-comando");
      if (sd?.kpis) setKpis(sd.kpis);
      setRecalcStatus("Engine recalculado com sucesso.");
    } catch (e: unknown) { setRecalcStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  async function coletarMacro() {
    setMacroStatus("Coletando…");
    try {
      await apiFetch("/macro/coletar", { method: "POST" });
      setMacroStatus("Coleta concluída.");
    } catch (e: unknown) { setMacroStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  // ── Ativos actions ────────────────────────────────────────────────
  async function saveAtivo() {
    if (!editAtivo) return;
    try {
      await apiFetch(`/ativos/${editAtivo.ticker}`, {
        method: "PATCH",
        body: JSON.stringify({
          classe: editAtivo.classe, familia: editAtivo.familia, setor: editAtivo.setor,
          composite: editAtivo.composite, bloco_ips: editAtivo.bloco_ips || null,
          observacao: editAtivo.observacao, data_vencimento: editAtivo.data_vencimento || null,
        }),
      });
      setAtivoStatus("Salvo!");
      setEditAtivo(null);
      loadAtivos();
    } catch (e: unknown) { setAtivoStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  async function createAtivo() {
    if (!novoAtivo.ticker) return;
    try {
      await apiFetch("/ativos", { method: "POST", body: JSON.stringify({ ...novoAtivo, ticker: novoAtivo.ticker!.toUpperCase() }) });
      setAtivoStatus("Ativo criado!");
      setNovoAtivo({ composite: "Gerida" });
      setShowNovoAtivo(false);
      loadAtivos();
    } catch (e: unknown) { setAtivoStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  async function deleteAtivo(ticker: string) {
    if (!confirm(`Excluir ativo ${ticker}?`)) return;
    try {
      await apiFetch(`/ativos/${ticker}`, { method: "DELETE" });
      setAtivos((prev) => prev.filter((a) => a.ticker !== ticker));
    } catch (e: unknown) { setAtivoStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  // ── Preços Manuais actions ────────────────────────────────────────
  async function addPreco() {
    if (!novoPreco.ticker || !novoPreco.valor) return;
    try {
      await apiFetch("/precos-manuais", {
        method: "POST",
        body: JSON.stringify({ ticker: novoPreco.ticker.toUpperCase(), data: novoPreco.data, valor: Number(novoPreco.valor), fonte: novoPreco.fonte }),
      });
      setPrecoStatus("Preço salvo!");
      setNovoPreco({ ticker: "", data: new Date().toISOString().slice(0, 10), valor: "", fonte: "Manual" });
      loadPrecos();
    } catch (e: unknown) { setPrecoStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  // ── Regra Aporte action ───────────────────────────────────────────
  async function criarRegra() {
    if (!novaRegra.valor_mensal_alvo) return;
    try {
      const r = await apiFetch<RegraAporte>("/regra-aportes", {
        method: "POST",
        body: JSON.stringify({
          valor_mensal_alvo: Number(novaRegra.valor_mensal_alvo),
          tipo: novaRegra.tipo,
          criterio_oportunismo: novaRegra.criterio_oportunismo || null,
        }),
      });
      setRegraAtiva(r);
      setRegraStatus("Regra criada!");
      setNovaRegra({ valor_mensal_alvo: "", tipo: "PROGRAMADO", criterio_oportunismo: "" });
    } catch (e: unknown) { setRegraStatus("Erro: " + (e instanceof Error ? e.message : "falha")); }
  }

  const ativosFiltrados = ativos.filter((a) =>
    !ativoSearch || a.ticker.includes(ativoSearch.toUpperCase()) || (a.setor ?? "").toLowerCase().includes(ativoSearch.toLowerCase())
  );

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto">
        <div className="px-4 py-4 md:px-8 md:py-6 max-w-4xl space-y-4">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Configurações
          </h1>

          {/* Tabs */}
          <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
            {([["sistema", "Sistema"], ["ativos", "CAD_ATIVOS"], ["precos", "Preços Manuais"], ["aportes", "Regra Aportes"]] as [Tab, string][]).map(([t, label]) => {
              const active = tab === t;
              return (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className="px-4 py-2 text-sm font-medium border-b-2 transition -mb-px"
                  style={{
                    whiteSpace: "nowrap",
                    borderColor: active ? "var(--accent)" : "transparent",
                    color: active ? "var(--accent-strong)" : "var(--text-muted)",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* ── Tab Sistema ─────────────────────────────────────── */}
          {tab === "sistema" && (
            <>
              {loading && <div className="animate-pulse h-48 rounded-xl" style={{ background: "var(--bg-card)" }} />}
              {!loading && (
                <>
                  <section
                    className="rounded-xl border px-5 py-4 space-y-3"
                    style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Conta</h2>
                    {[
                      ["Email", email ?? "—"],
                      ["Versão", "v2.5.1"],
                      ["Engine calculado", relativeTime(kpis?.calculado_em)],
                      ["Nível de automação", kpis?.nivel_automacao ?? "—"],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between text-sm">
                        <span style={{ color: "var(--text-muted)" }}>{k}</span>
                        <span style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{v}</span>
                      </div>
                    ))}
                  </section>

                  <section
                    className="rounded-xl border px-5 py-4 space-y-3"
                    style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Automação L1-L4</h2>
                    <AutomacaoSettings />
                  </section>

                  <section
                    className="rounded-xl border px-5 py-4 space-y-3"
                    style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Coleta de Dados Macro</h2>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>Coleta BCB SGS, Focus e yfinance. Pode levar até 30s.</p>
                    <button
                      onClick={coletarMacro}
                      className="rounded-lg px-4 py-2 text-sm font-medium border transition"
                      style={{ borderColor: "var(--border)", color: "var(--text-body)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      Coletar macro agora
                    </button>
                    {macroStatus && <p className="text-xs" style={{ color: statusColor(macroStatus) }}>{macroStatus}</p>}
                  </section>

                  <section
                    className="rounded-xl border px-5 py-4 space-y-3"
                    style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                  >
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Engine de Cálculo</h2>
                    <p className="text-xs" style={{ color: "var(--text-muted)" }}>Recalcula posições, TWR, P&amp;L e benchmarks a partir do event log.</p>
                    <div className="flex items-center gap-4">
                      <button
                        onClick={recalcular}
                        className="rounded-lg px-4 py-2 text-sm font-semibold transition"
                        style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
                      >
                        Recalcular engine
                      </button>
                      {kpis?.calculado_em && <span className="text-xs" style={{ color: "var(--text-faint)" }}>Último: {relativeTime(kpis.calculado_em)}</span>}
                    </div>
                    {recalcStatus && <p className="text-xs" style={{ color: statusColor(recalcStatus) }}>{recalcStatus}</p>}
                  </section>
                </>
              )}
            </>
          )}

          {/* ── Tab CAD_ATIVOS ──────────────────────────────────── */}
          {tab === "ativos" && (
            <>
              <div className="flex gap-3 items-center flex-wrap">
                <input
                  value={ativoSearch}
                  onChange={(e) => setAtivoSearch(e.target.value)}
                  placeholder="Buscar ticker ou setor…"
                  className={`${inputClass} w-56`}
                  style={inputStyle}
                />
                <button
                  onClick={() => setShowNovoAtivo((s) => !s)}
                  className="ml-auto rounded-lg px-3 py-2 text-sm font-medium border transition"
                  style={{ whiteSpace: "nowrap", background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                >
                  + Novo ativo
                </button>
                {ativoStatus && <span className="text-xs" style={{ color: statusColor(ativoStatus) }}>{ativoStatus}</span>}
              </div>

              {/* Formulário novo ativo */}
              {showNovoAtivo && (
                <div
                  className="rounded-xl border px-5 py-4 space-y-3"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Novo Ativo</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {(["ticker", "classe", "familia", "setor"] as const).map((f) => (
                      <div key={f}>
                        <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>{f}{f === "ticker" ? " *" : ""}</label>
                        <input
                          value={(novoAtivo as Record<string, string>)[f] ?? ""}
                          onChange={(e) => setNovoAtivo((p) => ({ ...p, [f]: e.target.value }))}
                          className={inputClass} style={inputStyle} placeholder={f === "ticker" ? "Ex: ITSA4" : ""}
                        />
                      </div>
                    ))}
                    <div>
                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Composite</label>
                      <select value={novoAtivo.composite ?? "Gerida"} onChange={(e) => setNovoAtivo((p) => ({ ...p, composite: e.target.value }))} className={inputClass} style={inputStyle}>
                        <option>Gerida</option><option>FUNCEF</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Bloco IPS</label>
                      <select value={novoAtivo.bloco_ips ?? ""} onChange={(e) => setNovoAtivo((p) => ({ ...p, bloco_ips: e.target.value }))} className={inputClass} style={inputStyle}>
                        <option value="">— sem bloco —</option>
                        {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={createAtivo}
                      className="rounded px-4 py-1.5 text-sm border transition"
                      style={{ background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                    >
                      Criar
                    </button>
                    <button
                      onClick={() => setShowNovoAtivo(false)}
                      className="rounded px-3 py-1.5 text-sm border transition"
                      style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                    >
                      Cancelar
                    </button>
                  </div>
                </div>
              )}

              <section
                className="rounded-xl border overflow-hidden"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                {loadingAtivos ? (
                  <div className="animate-pulse p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded" style={{ background: "var(--bg-card-alt)" }} />)}</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="px-3 py-2 text-left">Ticker</th>
                          <th className="px-3 py-2 text-left">Classe</th>
                          <th className="px-3 py-2 text-left">Família</th>
                          <th className="px-3 py-2 text-left">Setor</th>
                          <th className="px-3 py-2 text-left">Composite</th>
                          <th className="px-3 py-2 text-left">Bloco IPS</th>
                          <th className="px-3 py-2 text-center">Ações</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ativosFiltrados.map((a) => (
                          <React.Fragment key={a.ticker}>
                            <tr
                              className="border-b transition"
                              style={{ borderColor: "var(--border-soft)" }}
                              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                            >
                              <td className="px-3 py-2 font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{a.ticker}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{a.classe ?? "—"}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{a.familia ?? "—"}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{a.setor ?? "—"}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-body)" }}>{a.composite}</td>
                              <td className="px-3 py-2" style={{ color: "var(--purple-accent)", whiteSpace: "nowrap" }}>{a.bloco_ips ?? "—"}</td>
                              <td className="px-3 py-2 text-center">
                                <div className="flex gap-2 justify-center">
                                  <button
                                    onClick={() => setEditAtivo(editAtivo?.ticker === a.ticker ? null : { ...a })}
                                    className="hover:underline text-[10px]"
                                    style={{ color: "var(--purple-accent)" }}
                                  >
                                    Editar
                                  </button>
                                  <button
                                    onClick={() => deleteAtivo(a.ticker)}
                                    className="hover:underline text-[10px]"
                                    style={{ color: "var(--negative)" }}
                                  >
                                    Excluir
                                  </button>
                                </div>
                              </td>
                            </tr>
                            {editAtivo?.ticker === a.ticker && (
                              <tr className="border-b" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                                <td colSpan={7} className="px-3 py-3">
                                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                    {(["classe", "familia", "setor"] as (keyof Ativo)[]).map((f) => (
                                      <div key={String(f)}>
                                        <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>{String(f)}</label>
                                        <input
                                          value={(editAtivo as unknown as Record<string, string>)[f as string] ?? ""}
                                          onChange={(e) => setEditAtivo((p) => p ? { ...p, [f]: e.target.value } : p)}
                                          className={inputClass} style={inputStyle}
                                        />
                                      </div>
                                    ))}
                                    <div>
                                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Composite</label>
                                      <select value={editAtivo.composite} onChange={(e) => setEditAtivo((p) => p ? { ...p, composite: e.target.value } : p)} className={inputClass} style={inputStyle}>
                                        <option>Gerida</option><option>FUNCEF</option>
                                      </select>
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Bloco IPS</label>
                                      <select value={editAtivo.bloco_ips ?? ""} onChange={(e) => setEditAtivo((p) => p ? { ...p, bloco_ips: e.target.value || undefined } : p)} className={inputClass} style={inputStyle}>
                                        <option value="">— sem bloco —</option>
                                        {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                                      </select>
                                    </div>
                                    <div>
                                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Vencimento</label>
                                      <input
                                        type="date"
                                        value={editAtivo.data_vencimento ?? ""}
                                        onChange={(e) => setEditAtivo((p) => p ? { ...p, data_vencimento: e.target.value || undefined } : p)}
                                        className={inputClass} style={inputStyle}
                                      />
                                    </div>
                                  </div>
                                  <div className="flex gap-2 mt-3">
                                    <button
                                      onClick={saveAtivo}
                                      className="rounded px-4 py-1.5 text-sm border transition"
                                      style={{ background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                                    >
                                      Salvar
                                    </button>
                                    <button
                                      onClick={() => setEditAtivo(null)}
                                      className="rounded px-3 py-1.5 text-sm border transition"
                                      style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                                    >
                                      Cancelar
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-[10px] px-3 py-2" style={{ color: "var(--text-faint)" }}>{ativosFiltrados.length} de {ativos.length} ativos</p>
                  </div>
                )}
              </section>
            </>
          )}

          {/* ── Tab Preços Manuais ──────────────────────────────── */}
          {tab === "precos" && (
            <>
              <section
                className="rounded-xl border px-5 py-4 space-y-3"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Adicionar Preço Manual</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Para ativos sem cotação pública (CDBs, fundos fechados, FUNCEF). Upsert por ticker + data.</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Ticker *</label>
                    <input value={novoPreco.ticker} onChange={(e) => setNovoPreco((p) => ({ ...p, ticker: e.target.value.toUpperCase() }))} className={inputClass} style={inputStyle} placeholder="Ex: CAIXA FIC FUNC" />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Data *</label>
                    <input type="date" value={novoPreco.data} onChange={(e) => setNovoPreco((p) => ({ ...p, data: e.target.value }))} className={inputClass} style={inputStyle} />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Valor (cota) *</label>
                    <input type="number" step="0.000001" value={novoPreco.valor} onChange={(e) => setNovoPreco((p) => ({ ...p, valor: e.target.value }))} className={inputClass} style={inputStyle} placeholder="0.000000" />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Fonte</label>
                    <input value={novoPreco.fonte} onChange={(e) => setNovoPreco((p) => ({ ...p, fonte: e.target.value }))} className={inputClass} style={inputStyle} />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={addPreco}
                    className="rounded px-4 py-1.5 text-sm border transition"
                    style={{ background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                  >
                    Salvar preço
                  </button>
                  {precoStatus && <span className="text-xs" style={{ color: statusColor(precoStatus) }}>{precoStatus}</span>}
                </div>
              </section>

              <section
                className="rounded-xl border overflow-hidden"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border-soft)" }}>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Preços salvos ({precos.length})</h2>
                  <button onClick={loadPrecos} className="text-xs transition" style={{ color: "var(--text-faint)" }}>↺</button>
                </div>
                {loadingPrecos ? <div className="p-4 text-xs" style={{ color: "var(--text-faint)" }}>Carregando…</div> : (
                  <div className="overflow-x-auto max-h-80">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase sticky top-0" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)", background: "var(--bg-card)" }}>
                          <th className="px-3 py-2 text-left">Ticker</th>
                          <th className="px-3 py-2 text-left">Data</th>
                          <th className="px-3 py-2 text-right">Valor</th>
                          <th className="px-3 py-2 text-left">Fonte</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...precos].reverse().map((p) => (
                          <tr key={p.id} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                            <td className="px-3 py-1.5 font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{p.ticker}</td>
                            <td className="px-3 py-1.5" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{String(p.data)}</td>
                            <td className="px-3 py-1.5 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{p.valor.toLocaleString("pt-BR", { minimumFractionDigits: 6, maximumFractionDigits: 6 })}</td>
                            <td className="px-3 py-1.5" style={{ color: "var(--text-muted)" }}>{p.fonte ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            </>
          )}

          {/* ── Tab Regra de Aportes ────────────────────────────── */}
          {tab === "aportes" && (
            <>
              {regraAtiva && (
                <section
                  className="rounded-xl border px-5 py-4 space-y-2"
                  style={{ borderColor: "rgba(74,124,89,0.4)", background: "rgba(74,124,89,0.06)" }}
                >
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Regra Ativa</h2>
                  {[
                    ["Valor mensal alvo", brl(regraAtiva.valor_mensal_alvo)],
                    ["Tipo", regraAtiva.tipo],
                    ["Critério oportunismo", regraAtiva.criterio_oportunismo ?? "—"],
                    ["Criada em", String(regraAtiva.data_criacao)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span style={{ color: "var(--text-muted)" }}>{k}</span>
                      <span style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{v}</span>
                    </div>
                  ))}
                </section>
              )}

              <section
                className="rounded-xl border px-5 py-4 space-y-3"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Nova Regra de Aporte</h2>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Criar nova regra desativa a anterior automaticamente.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Valor mensal alvo (R$) *</label>
                    <input type="number" step="100" value={novaRegra.valor_mensal_alvo}
                      onChange={(e) => setNovaRegra((p) => ({ ...p, valor_mensal_alvo: e.target.value }))} className={inputClass} style={inputStyle} placeholder="2000" />
                  </div>
                  <div>
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Tipo</label>
                    <select value={novaRegra.tipo} onChange={(e) => setNovaRegra((p) => ({ ...p, tipo: e.target.value }))} className={inputClass} style={inputStyle}>
                      <option>PROGRAMADO</option><option>OPORTUNISTICO</option><option>MISTO</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Critério de oportunismo (opcional)</label>
                    <input value={novaRegra.criterio_oportunismo}
                      onChange={(e) => setNovaRegra((p) => ({ ...p, criterio_oportunismo: e.target.value }))}
                      className={inputClass} style={inputStyle} placeholder="Ex: IBOV < -5% no mês" />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={criarRegra}
                    className="rounded px-4 py-1.5 text-sm font-semibold transition"
                    style={{ background: "var(--purple-accent)", color: "var(--bg-card)" }}
                  >
                    Criar regra
                  </button>
                  {regraStatus && <span className="text-xs" style={{ color: statusColor(regraStatus) }}>{regraStatus}</span>}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
