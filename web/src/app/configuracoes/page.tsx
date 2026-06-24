"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState, useCallback } from "react";
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
const cls = "w-full rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2 text-sm text-[#D1D4DC] focus:outline-none focus:border-[#6366F1] transition";

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
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto">
        <div className="px-4 py-4 md:px-8 max-w-4xl space-y-4">
          <h1 className="text-lg font-bold text-white">Configurações</h1>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-[#2A2D3A]">
            {([["sistema", "Sistema"], ["ativos", "CAD_ATIVOS"], ["precos", "Preços Manuais"], ["aportes", "Regra Aportes"]] as [Tab, string][]).map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ${tab === t ? "border-[#26A69A] text-[#26A69A]" : "border-transparent text-[#6b7280] hover:text-[#D1D4DC]"}`}>
                {label}
              </button>
            ))}
          </div>

          {/* ── Tab Sistema ─────────────────────────────────────── */}
          {tab === "sistema" && (
            <>
              {loading && <div className="animate-pulse h-48 rounded-xl bg-[#1A1D27]" />}
              {!loading && (
                <>
                  <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                    <h2 className="text-sm font-semibold text-white">Conta</h2>
                    {[
                      ["Email", email ?? "—"],
                      ["Versão", "v2.5.1"],
                      ["Engine calculado", relativeTime(kpis?.calculado_em)],
                      ["Nível de automação", kpis?.nivel_automacao ?? "—"],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between text-sm">
                        <span className="text-[#6b7280]">{k}</span>
                        <span className="font-mono text-[#D1D4DC]">{v}</span>
                      </div>
                    ))}
                  </section>

                  <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                    <h2 className="text-sm font-semibold text-white">Automação L1-L4</h2>
                    <AutomacaoSettings />
                  </section>

                  <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                    <h2 className="text-sm font-semibold text-white">Coleta de Dados Macro</h2>
                    <p className="text-xs text-[#6b7280]">Coleta BCB SGS, Focus e yfinance. Pode levar até 30s.</p>
                    <button onClick={coletarMacro}
                      className="rounded-lg px-4 py-2 text-sm font-medium border border-[#2A2D3A] text-[#D1D4DC] hover:bg-[#2A2D3A] transition">
                      Coletar macro agora
                    </button>
                    {macroStatus && <p className={`text-xs ${macroStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>{macroStatus}</p>}
                  </section>

                  <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                    <h2 className="text-sm font-semibold text-white">Engine de Cálculo</h2>
                    <p className="text-xs text-[#6b7280]">Recalcula posições, TWR, P&amp;L e benchmarks a partir do event log.</p>
                    <div className="flex items-center gap-4">
                      <button onClick={recalcular}
                        className="rounded-lg px-4 py-2 text-sm font-medium bg-[#6366F1] text-white hover:bg-[#6366F1]/80 transition">
                        Recalcular engine
                      </button>
                      {kpis?.calculado_em && <span className="text-xs text-[#6b7280]">Último: {relativeTime(kpis.calculado_em)}</span>}
                    </div>
                    {recalcStatus && <p className={`text-xs ${recalcStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>{recalcStatus}</p>}
                  </section>
                </>
              )}
            </>
          )}

          {/* ── Tab CAD_ATIVOS ──────────────────────────────────── */}
          {tab === "ativos" && (
            <>
              <div className="flex gap-3 items-center">
                <input value={ativoSearch} onChange={(e) => setAtivoSearch(e.target.value)}
                  placeholder="Buscar ticker ou setor…"
                  className="rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2 text-sm text-[#D1D4DC] focus:outline-none focus:border-[#26A69A] w-56" />
                <button onClick={() => setShowNovoAtivo((s) => !s)}
                  className="ml-auto rounded-lg px-3 py-2 text-sm font-medium bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40 hover:bg-[#26A69A]/30 transition">
                  + Novo ativo
                </button>
                {ativoStatus && <span className={`text-xs ${ativoStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>{ativoStatus}</span>}
              </div>

              {/* Formulário novo ativo */}
              {showNovoAtivo && (
                <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                  <h3 className="text-sm font-semibold text-white">Novo Ativo</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {(["ticker", "classe", "familia", "setor"] as const).map((f) => (
                      <div key={f}>
                        <label className="text-[10px] text-[#6b7280] uppercase">{f}{f === "ticker" ? " *" : ""}</label>
                        <input value={(novoAtivo as Record<string, string>)[f] ?? ""} onChange={(e) => setNovoAtivo((p) => ({ ...p, [f]: e.target.value }))}
                          className={cls} placeholder={f === "ticker" ? "Ex: ITSA4" : ""} />
                      </div>
                    ))}
                    <div>
                      <label className="text-[10px] text-[#6b7280] uppercase">Composite</label>
                      <select value={novoAtivo.composite ?? "Gerida"} onChange={(e) => setNovoAtivo((p) => ({ ...p, composite: e.target.value }))} className={cls}>
                        <option>Gerida</option><option>FUNCEF</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-[#6b7280] uppercase">Bloco IPS</label>
                      <select value={novoAtivo.bloco_ips ?? ""} onChange={(e) => setNovoAtivo((p) => ({ ...p, bloco_ips: e.target.value }))} className={cls}>
                        <option value="">— sem bloco —</option>
                        {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={createAtivo} className="rounded px-4 py-1.5 text-sm bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40 hover:bg-[#26A69A]/30 transition">Criar</button>
                    <button onClick={() => setShowNovoAtivo(false)} className="rounded px-3 py-1.5 text-sm border border-[#2A2D3A] text-[#6b7280] hover:bg-[#2A2D3A] transition">Cancelar</button>
                  </div>
                </div>
              )}

              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] overflow-hidden">
                {loadingAtivos ? (
                  <div className="animate-pulse p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded bg-[#2A2D3A]" />)}</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
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
                          <>
                            <tr key={a.ticker} className="border-b border-[#2A2D3A] hover:bg-[#2A2D3A]/20">
                              <td className="px-3 py-2 font-bold text-white">{a.ticker}</td>
                              <td className="px-3 py-2 text-[#6b7280]">{a.classe ?? "—"}</td>
                              <td className="px-3 py-2 text-[#6b7280]">{a.familia ?? "—"}</td>
                              <td className="px-3 py-2 text-[#6b7280]">{a.setor ?? "—"}</td>
                              <td className="px-3 py-2">{a.composite}</td>
                              <td className="px-3 py-2 text-[#6366F1]">{a.bloco_ips ?? "—"}</td>
                              <td className="px-3 py-2 text-center">
                                <div className="flex gap-2 justify-center">
                                  <button onClick={() => setEditAtivo(editAtivo?.ticker === a.ticker ? null : { ...a })}
                                    className="text-[#6366F1] hover:underline text-[10px]">Editar</button>
                                  <button onClick={() => deleteAtivo(a.ticker)}
                                    className="text-[#EF5350] hover:underline text-[10px]">Excluir</button>
                                </div>
                              </td>
                            </tr>
                            {editAtivo?.ticker === a.ticker && (
                              <tr key={`edit-${a.ticker}`} className="border-b border-[#2A2D3A] bg-[#0F1117]/60">
                                <td colSpan={7} className="px-3 py-3">
                                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                    {(["classe", "familia", "setor"] as (keyof Ativo)[]).map((f) => (
                                      <div key={String(f)}>
                                        <label className="text-[10px] text-[#6b7280] uppercase">{String(f)}</label>
                                        <input value={(editAtivo as unknown as Record<string, string>)[f as string] ?? ""}
                                          onChange={(e) => setEditAtivo((p) => p ? { ...p, [f]: e.target.value } : p)}
                                          className={cls} />
                                      </div>
                                    ))}
                                    <div>
                                      <label className="text-[10px] text-[#6b7280] uppercase">Composite</label>
                                      <select value={editAtivo.composite} onChange={(e) => setEditAtivo((p) => p ? { ...p, composite: e.target.value } : p)} className={cls}>
                                        <option>Gerida</option><option>FUNCEF</option>
                                      </select>
                                    </div>
                                    <div>
                                      <label className="text-[10px] text-[#6b7280] uppercase">Bloco IPS</label>
                                      <select value={editAtivo.bloco_ips ?? ""} onChange={(e) => setEditAtivo((p) => p ? { ...p, bloco_ips: e.target.value || undefined } : p)} className={cls}>
                                        <option value="">— sem bloco —</option>
                                        {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                                      </select>
                                    </div>
                                    <div>
                                      <label className="text-[10px] text-[#6b7280] uppercase">Vencimento</label>
                                      <input type="date" value={editAtivo.data_vencimento ?? ""}
                                        onChange={(e) => setEditAtivo((p) => p ? { ...p, data_vencimento: e.target.value || undefined } : p)} className={cls} />
                                    </div>
                                  </div>
                                  <div className="flex gap-2 mt-3">
                                    <button onClick={saveAtivo} className="rounded px-4 py-1.5 text-sm bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40 hover:bg-[#26A69A]/30 transition">Salvar</button>
                                    <button onClick={() => setEditAtivo(null)} className="rounded px-3 py-1.5 text-sm border border-[#2A2D3A] text-[#6b7280] hover:bg-[#2A2D3A] transition">Cancelar</button>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        ))}
                      </tbody>
                    </table>
                    <p className="text-[10px] text-[#6b7280] px-3 py-2">{ativosFiltrados.length} de {ativos.length} ativos</p>
                  </div>
                )}
              </section>
            </>
          )}

          {/* ── Tab Preços Manuais ──────────────────────────────── */}
          {tab === "precos" && (
            <>
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                <h2 className="text-sm font-semibold text-white">Adicionar Preço Manual</h2>
                <p className="text-xs text-[#6b7280]">Para ativos sem cotação pública (CDBs, fundos fechados, FUNCEF). Upsert por ticker + data.</p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Ticker *</label>
                    <input value={novoPreco.ticker} onChange={(e) => setNovoPreco((p) => ({ ...p, ticker: e.target.value.toUpperCase() }))} className={cls} placeholder="Ex: CAIXA FIC FUNC" />
                  </div>
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Data *</label>
                    <input type="date" value={novoPreco.data} onChange={(e) => setNovoPreco((p) => ({ ...p, data: e.target.value }))} className={cls} />
                  </div>
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Valor (cota) *</label>
                    <input type="number" step="0.000001" value={novoPreco.valor} onChange={(e) => setNovoPreco((p) => ({ ...p, valor: e.target.value }))} className={cls} placeholder="0.000000" />
                  </div>
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Fonte</label>
                    <input value={novoPreco.fonte} onChange={(e) => setNovoPreco((p) => ({ ...p, fonte: e.target.value }))} className={cls} />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={addPreco}
                    className="rounded px-4 py-1.5 text-sm bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40 hover:bg-[#26A69A]/30 transition">
                    Salvar preço
                  </button>
                  {precoStatus && <span className={`text-xs ${precoStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>{precoStatus}</span>}
                </div>
              </section>

              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] overflow-hidden">
                <div className="px-5 py-3 border-b border-[#2A2D3A] flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-white">Preços salvos ({precos.length})</h2>
                  <button onClick={loadPrecos} className="text-xs text-[#6b7280] hover:text-[#D1D4DC] transition">↺</button>
                </div>
                {loadingPrecos ? <div className="p-4 text-xs text-[#6b7280]">Carregando…</div> : (
                  <div className="overflow-x-auto max-h-80">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase sticky top-0 bg-[#1A1D27]">
                          <th className="px-3 py-2 text-left">Ticker</th>
                          <th className="px-3 py-2 text-left">Data</th>
                          <th className="px-3 py-2 text-right">Valor</th>
                          <th className="px-3 py-2 text-left">Fonte</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...precos].reverse().map((p) => (
                          <tr key={p.id} className="border-b border-[#2A2D3A]">
                            <td className="px-3 py-1.5 font-bold text-white">{p.ticker}</td>
                            <td className="px-3 py-1.5 font-mono">{String(p.data)}</td>
                            <td className="px-3 py-1.5 text-right font-mono">{p.valor.toLocaleString("pt-BR", { minimumFractionDigits: 6, maximumFractionDigits: 6 })}</td>
                            <td className="px-3 py-1.5 text-[#6b7280]">{p.fonte ?? "—"}</td>
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
                <section className="rounded-xl border border-[#26A69A]/40 bg-[#26A69A]/5 px-5 py-4 space-y-2">
                  <h2 className="text-sm font-semibold text-white">Regra Ativa</h2>
                  {[
                    ["Valor mensal alvo", brl(regraAtiva.valor_mensal_alvo)],
                    ["Tipo", regraAtiva.tipo],
                    ["Critério oportunismo", regraAtiva.criterio_oportunismo ?? "—"],
                    ["Criada em", String(regraAtiva.data_criacao)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span className="text-[#6b7280]">{k}</span>
                      <span className="font-mono text-[#D1D4DC]">{v}</span>
                    </div>
                  ))}
                </section>
              )}

              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4 space-y-3">
                <h2 className="text-sm font-semibold text-white">Nova Regra de Aporte</h2>
                <p className="text-xs text-[#6b7280]">Criar nova regra desativa a anterior automaticamente.</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Valor mensal alvo (R$) *</label>
                    <input type="number" step="100" value={novaRegra.valor_mensal_alvo}
                      onChange={(e) => setNovaRegra((p) => ({ ...p, valor_mensal_alvo: e.target.value }))} className={cls} placeholder="2000" />
                  </div>
                  <div>
                    <label className="text-[10px] text-[#6b7280] uppercase">Tipo</label>
                    <select value={novaRegra.tipo} onChange={(e) => setNovaRegra((p) => ({ ...p, tipo: e.target.value }))} className={cls}>
                      <option>PROGRAMADO</option><option>OPORTUNISTICO</option><option>MISTO</option>
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="text-[10px] text-[#6b7280] uppercase">Critério de oportunismo (opcional)</label>
                    <input value={novaRegra.criterio_oportunismo}
                      onChange={(e) => setNovaRegra((p) => ({ ...p, criterio_oportunismo: e.target.value }))}
                      className={cls} placeholder="Ex: IBOV < -5% no mês" />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={criarRegra}
                    className="rounded px-4 py-1.5 text-sm bg-[#6366F1]/20 text-[#6366F1] border border-[#6366F1]/40 hover:bg-[#6366F1]/30 transition">
                    Criar regra
                  </button>
                  {regraStatus && <span className={`text-xs ${regraStatus.includes("Erro") ? "text-[#EF5350]" : "text-[#26A69A]"}`}>{regraStatus}</span>}
                </div>
              </section>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
