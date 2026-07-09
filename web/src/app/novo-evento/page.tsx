"use client";

export const dynamic = "force-dynamic";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";

const TIPOS = [
  "COMPRA", "VENDA", "DIVIDENDO", "JCP", "RENDIMENTO",
  "BONIFICACAO", "AMORTIZACAO", "APORTE_EXTERNO", "RESGATE_EXTERNO",
  "CONTRIBUICAO", "RESGATE", "APORTE",
];

const BLOCOS_IPS = ["SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"];

interface AtivoInfo { ticker: string; classe?: string; bloco_ips?: string; composite: string }
interface Evento { id: number; linha: number; data: string; ativo: string; tipo: string; qtd?: number; preco?: number; valor: number; obs?: string }

const inputClass = "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none transition";
const inputStyle = { background: "var(--bg-app)", borderColor: "var(--border)", color: "var(--text-body)" } as const;
const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>
        {label}{required && <span className="ml-0.5" style={{ color: "var(--negative)" }}>*</span>}
      </label>
      {children}
    </div>
  );
}

function brl(n: number | null | undefined): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

type Tab = "formulario" | "historico" | "importar";

export default function NovoEvento() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("formulario");

  // ── Form state ────────────────────────────────────────────────────
  const [tipo, setTipo] = useState("COMPRA");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [ativo, setAtivo] = useState("");
  const [qtd, setQtd] = useState("");
  const [preco, setPreco] = useState("");
  const [valor, setValor] = useState("");
  const [obs, setObs] = useState("");
  const [blocoIps, setBlocoIps] = useState("");
  const [debitarCaixa, setDebitarCaixa] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [toastErr, setToastErr] = useState<string | null>(null);

  // ── Autocomplete tickers ──────────────────────────────────────────
  const [ativos, setAtivos] = useState<AtivoInfo[]>([]);
  const [showSugest, setShowSugest] = useState(false);
  const ativoRef = useRef<HTMLInputElement>(null);

  // ── Histórico ────────────────────────────────────────────────────
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [loadingEvts, setLoadingEvts] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editObs, setEditObs] = useState("");

  // ── Importação ───────────────────────────────────────────────────
  interface ImportEvento {
    data: string; ativo: string; tipo: string;
    qtd?: number | null; preco?: number | null; valor: number; obs?: string;
    duplicata?: boolean; ignorar?: boolean;
  }
  interface ImportPreview {
    status: string;
    importacao_id?: number;
    eventos: ImportEvento[];
    duplicatas: number;
    custo_api_usd: number;
    tipo_identificado?: string;
    tipo_documento?: string;
    confianca?: string;
    justificativa?: string;
    raw_claude_response?: string;
    arquivo_path?: string;
    arquivo_hash?: string;
    nome_arquivo?: string;
    reconciliacao?: { alerta_criado?: boolean; alerta_mensagem?: string; patrimonio_calculado?: number };
  }
  interface ConflitoCota { data: string; valor_existente: number; valor_novo: number; diferenca_pct: number }
  interface ImpHistorico {
    id: number; data_upload: string; arquivo_nome: string;
    tipo_identificado_ia?: string; confianca_ia?: string; status: string;
    total_eventos_extraidos?: number; total_eventos_gravados?: number; custo_api_usd?: number;
  }

  const TIPO_LABELS: Record<string, string> = {
    auto: "Detectar automaticamente", funcef: "FUNCEF — Extrato",
    b3_custodia: "B3 — Custódia", b3_movimentacoes: "B3 — Movimentações",
    caixa_rv: "Caixa RV", caixa_lci: "Caixa LCI", caixa_ouro: "Caixa Ouro",
    caixa_fic_func: "Caixa FIC Funcionários", tesouro_direto: "Tesouro Direto",
  };
  const CONFIANCA_ICON: Record<string, string> = { alta: "🟢", media: "🟡", baixa: "🔴" };

  const [impFile, setImpFile] = useState<File | null>(null);
  const [impTipo, setImpTipo] = useState("auto");
  const [impDryRun, setImpDryRun] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [selecionados, setSelecionados] = useState<boolean[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [conflitos, setConflitos] = useState<ConflitoCota[]>([]);
  const [conflitosBodyRef, setConflitosBodyRef] = useState<Record<string, unknown> | null>(null);
  const [impOk, setImpOk] = useState<string | null>(null);
  const [impErr, setImpErr] = useState<string | null>(null);
  const [impReconAlerta, setImpReconAlerta] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [reprocessTipo, setReprocessTipo] = useState("");
  const [reprocessing, setReprocessing] = useState(false);
  const [historico, setHistorico] = useState<ImpHistorico[]>([]);
  const [loadingHist, setLoadingHist] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    apiFetch<AtivoInfo[]>("/ativos").then(setAtivos).catch(() => {});
  }, [router]);

  const loadEventos = useCallback(async () => {
    setLoadingEvts(true);
    try {
      const ev = await apiFetch<Evento[]>("/eventos?limit=20");
      setEventos(ev);
    } catch { /* ignore */ }
    finally { setLoadingEvts(false); }
  }, []);

  useEffect(() => {
    if (tab === "historico") loadEventos();
  }, [tab, loadEventos]);

  function flash(msg: string, isErr = false) {
    if (isErr) { setToastErr(msg); setTimeout(() => setToastErr(null), 5000); }
    else { setToast(msg); setTimeout(() => setToast(null), 4000); }
  }

  // Preenche bloco_ips automaticamente ao selecionar ativo existente
  function selectAtivo(ticker: string) {
    setAtivo(ticker);
    setShowSugest(false);
    const info = ativos.find((a) => a.ticker === ticker);
    if (info?.bloco_ips) setBlocoIps(info.bloco_ips);
  }

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!ativo.trim()) errs.ativo = "Ativo obrigatório";
    if (!data || isNaN(Date.parse(data))) errs.data = "Data inválida";
    if (!tipo) errs.tipo = "Tipo obrigatório";
    if (qtd && Number(qtd) <= 0) errs.qtd = "Qtd deve ser > 0";
    const v = Number(valor);
    if (!valor && valor !== "0") errs.valor = "Valor obrigatório";
    else if (isNaN(v)) errs.valor = "Valor inválido";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      const payload = {
        data,
        ativo: ativo.trim().toUpperCase(),
        tipo,
        qtd: qtd ? Number(qtd) : null,
        preco: preco ? Number(preco) : null,
        valor: Number(valor),
        obs: obs.trim(),
      };
      await apiFetch("/eventos", { method: "POST", body: JSON.stringify(payload) });

      // 8a: se debitarCaixa, cria evento de saída no CAIXA FIC FUNCIONÁRIOS
      if (debitarCaixa && ["COMPRA"].includes(tipo) && Number(valor) > 0) {
        const caixaTicker = "CAIXA FIC FUNC";
        await apiFetch("/eventos", {
          method: "POST",
          body: JSON.stringify({
            data,
            ativo: caixaTicker,
            tipo: "RESGATE",
            qtd: null,
            preco: null,
            valor: -Math.abs(Number(valor)),
            obs: `Débito automático — compra ${ativo.trim().toUpperCase()}`,
          }),
        }).catch(() => {}); // non-blocking
      }

      flash("Evento registrado com sucesso!");
      setAtivo(""); setQtd(""); setPreco(""); setValor(""); setObs(""); setBlocoIps(""); setDebitarCaixa(false);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao registrar";
      if (msg.includes("401")) { clearToken(); router.replace("/login"); return; }
      setErrors({ submit: msg });
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteEvento(id: number) {
    if (!confirm("Excluir este evento?")) return;
    await apiFetch(`/eventos/${id}`, { method: "DELETE" }).catch(() => {});
    setEventos((prev) => prev.filter((e) => e.id !== id));
  }

  async function saveEdit(id: number) {
    await apiFetch(`/eventos/${id}`, { method: "PATCH", body: JSON.stringify({ obs: editObs }) }).catch(() => {});
    setEventos((prev) => prev.map((e) => e.id === id ? { ...e, obs: editObs } : e));
    setEditId(null);
  }

  const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1";

  function authHeaders(): Record<string, string> {
    const token = localStorage.getItem("carteira_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async function loadHistorico() {
    setLoadingHist(true);
    try {
      const data = await apiFetch<ImpHistorico[]>("/importacoes");
      setHistorico(data ?? []);
    } catch { setHistorico([]); }
    finally { setLoadingHist(false); }
  }

  useEffect(() => {
    if (tab === "importar") { loadHistorico(); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  function handlePreviewOk(data: ImportPreview) {
    const ev = data.eventos ?? [];
    setSelecionados(ev.map((e) => !e.duplicata && !e.ignorar));
    setPreview(data);
    setReprocessTipo(data.tipo_identificado ?? "");
    setShowRawJson(false);
    setConflitos([]); setConflitosBodyRef(null); setImpReconAlerta(null);
  }

  async function uploadExtrato() {
    if (!impFile) return;
    setUploading(true);
    setImpErr(null); setImpOk(null); setPreview(null); setConflitos([]);
    try {
      const fd = new FormData();
      fd.append("arquivo", impFile);
      fd.append("tipo_documento", impTipo);
      fd.append("dry_run", impDryRun ? "true" : "false");
      const res = await fetch(`${API_BASE}/importacao/upload`, {
        method: "POST", headers: authHeaders(), body: fd,
      });
      const data = await res.json();
      if (res.status === 409) throw new Error(data.detail ?? "Arquivo já importado anteriormente.");
      if (!res.ok) throw new Error(data.detail ?? `HTTP ${res.status}`);
      handlePreviewOk(data as ImportPreview);
    } catch (e: unknown) {
      setImpErr(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setUploading(false);
    }
  }

  async function reprocessar() {
    if (!preview?.importacao_id || !reprocessTipo) return;
    setReprocessing(true); setImpErr(null);
    try {
      const res = await fetch(`${API_BASE}/importacao/${preview.importacao_id}/reprocessar`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ tipo_documento: reprocessTipo }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Erro ao reprocessar");
      handlePreviewOk(data as ImportPreview);
    } catch (e: unknown) {
      setImpErr(e instanceof Error ? e.message : "Erro ao reprocessar");
    } finally {
      setReprocessing(false);
    }
  }

  function _processarResultadoConfirmacao(result: Record<string, unknown>, bodyOriginal: Record<string, unknown>, endpoint: string) {
    const gravados = (result.eventos_gravados as number) ?? 0;
    const cotas = (result.cotas_inseridas as number) ?? 0;
    const cotas_conflito = (result.cotas_conflito as ConflitoCota[]) ?? [];
    const rec = (result.reconciliacao as ImportPreview["reconciliacao"]) ?? {};

    if (rec?.alerta_criado) {
      setImpReconAlerta(rec.alerta_mensagem ?? "FUNCEF: divergência detectada.");
    }

    if (cotas_conflito.length) {
      setConflitos(cotas_conflito);
      setConflitosBodyRef({ ...bodyOriginal, _endpoint: endpoint });
      setImpOk(`${gravados} evento(s) gravado(s). ${cotas_conflito.length} conflito(s) de cota FUNCEF — veja abaixo.`);
    } else {
      let msg = `✅ ${gravados} evento(s) gravado(s) com sucesso!`;
      if (cotas) msg += ` | ${cotas} cota(s) FUNCEF salva(s).`;
      setImpOk(msg);
      setPreview(null); setSelecionados([]); setImpFile(null);
      loadHistorico();
    }
  }

  async function confirmarImport() {
    if (!preview) return;
    setConfirming(true); setImpErr(null);
    try {
      const indices = selecionados.map((s, i) => s ? i : -1).filter((i) => i >= 0);

      let url: string;
      let body: Record<string, unknown>;

      if (preview.status === "DRY_RUN") {
        url = `${API_BASE}/importacao/confirmar-direto`;
        body = {
          eventos: preview.eventos,
          indices_aprovados: indices,
          arquivo_path: preview.arquivo_path ?? "",
          arquivo_hash: preview.arquivo_hash ?? "",
          nome_arquivo: preview.nome_arquivo ?? impFile?.name ?? "",
          tipo_documento: preview.tipo_documento ?? impTipo,
          custo_api_usd: preview.custo_api_usd ?? 0,
          meta: {
            tipo_identificado: preview.tipo_identificado,
            confianca: preview.confianca,
            justificativa: preview.justificativa,
          },
        };
      } else {
        if (!preview.importacao_id) return;
        url = `${API_BASE}/importacao/${preview.importacao_id}/confirmar`;
        body = { indices_aprovados: indices };
      }

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail ?? "Erro ao confirmar");
      _processarResultadoConfirmacao(result, body, url.replace(API_BASE + "/", ""));
    } catch (e: unknown) {
      setImpErr(e instanceof Error ? e.message : "Erro ao confirmar");
    } finally {
      setConfirming(false);
    }
  }

  async function forcarCotas() {
    if (!conflitosBodyRef) return;
    setConfirming(true); setImpErr(null);
    try {
      const { _endpoint, ...bodyRest } = conflitosBodyRef as Record<string, unknown> & { _endpoint: string };
      const endpoint = _endpoint;
      const body = { ...bodyRest, force_update_cotas: true };
      const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}/${endpoint}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(body),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail ?? "Erro ao forçar");
      setImpOk(`✅ ${(result.cotas_inseridas as number) ?? 0} cota(s) atualizada(s) com sucesso!`);
      setPreview(null); setSelecionados([]); setImpFile(null); setConflitos([]); setConflitosBodyRef(null);
      loadHistorico();
    } catch (e: unknown) {
      setImpErr(e instanceof Error ? e.message : "Erro ao forçar atualização");
    } finally {
      setConfirming(false);
    }
  }

  async function cancelarImport() {
    if (preview?.importacao_id) {
      await fetch(`${API_BASE}/importacao/${preview.importacao_id}`, {
        method: "DELETE", headers: authHeaders(),
      }).catch(() => {});
    }
    resetImport();
  }

  function resetImport() {
    setPreview(null); setSelecionados([]); setImpFile(null);
    setImpErr(null); setImpOk(null); setImpReconAlerta(null);
    setConflitos([]); setConflitosBodyRef(null); setShowRawJson(false);
  }

  const sugestTickers = ativo.length >= 1
    ? ativos.map((a) => a.ticker).filter((t) => t.toUpperCase().startsWith(ativo.toUpperCase())).slice(0, 8)
    : [];

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto">
        <div className="px-4 py-4 md:px-8 md:py-6 max-w-3xl space-y-4">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Novo Evento
          </h1>

          {/* Tabs */}
          <div className="flex gap-1 border-b" style={{ borderColor: "var(--border)" }}>
            {([["formulario", "Registrar"], ["historico", "Últimos 20"], ["importar", "Importar Extrato"]] as [Tab, string][]).map(([t, label]) => {
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

          {/* Toast */}
          {toast && (
            <div
              className="rounded-xl border px-4 py-2.5 text-sm flex items-center justify-between"
              style={{ borderColor: "rgba(74,124,89,0.4)", background: "rgba(74,124,89,0.08)", color: "var(--positive)" }}
            >
              {toast}
              <button onClick={() => setToast(null)} className="ml-4 text-xs">✕</button>
            </div>
          )}
          {toastErr && (
            <div
              className="rounded-xl border px-4 py-2.5 text-sm flex items-center justify-between"
              style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
            >
              {toastErr}
              <button onClick={() => setToastErr(null)} className="ml-4 text-xs">✕</button>
            </div>
          )}

          {/* ── Tab Formulário ──────────────────────────────────────── */}
          {tab === "formulario" && (
            <form
              onSubmit={submit}
              className="rounded-xl border px-5 py-5 space-y-4"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="grid grid-cols-2 gap-4">
                <Field label="Tipo" required>
                  <select value={tipo} onChange={(e) => setTipo(e.target.value)} className={inputClass} style={inputStyle}>
                    {TIPOS.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </Field>
                <Field label="Data" required>
                  <input type="date" value={data} onChange={(e) => setData(e.target.value)} className={inputClass} style={inputStyle} />
                  {errors.data && <p className="text-xs mt-1" style={{ color: "var(--negative)" }}>{errors.data}</p>}
                </Field>
              </div>

              {/* Ativo com autocomplete */}
              <Field label="Ativo (ticker)" required>
                <div className="relative">
                  <input
                    ref={ativoRef} type="text" value={ativo}
                    onChange={(e) => { setAtivo(e.target.value.toUpperCase()); setShowSugest(true); }}
                    onBlur={() => setTimeout(() => setShowSugest(false), 150)}
                    onFocus={() => setShowSugest(true)}
                    placeholder="Ex: ITSA4" className={inputClass} style={inputStyle} autoComplete="off"
                  />
                  {showSugest && sugestTickers.length > 0 && (
                    <div
                      className="absolute top-full left-0 w-full z-20 rounded-lg border mt-1 overflow-hidden"
                      style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: "0 4px 16px rgba(61,54,41,0.14)" }}
                    >
                      {sugestTickers.map((t) => (
                        <button
                          key={t} type="button" onMouseDown={() => selectAtivo(t)}
                          className="w-full text-left px-3 py-2 text-sm transition"
                          style={{ color: "var(--text-body)" }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {errors.ativo && <p className="text-xs mt-1" style={{ color: "var(--negative)" }}>{errors.ativo}</p>}
              </Field>

              {/* 8b: Bloco IPS */}
              <Field label="Bloco IPS (opcional)">
                <select value={blocoIps} onChange={(e) => setBlocoIps(e.target.value)} className={inputClass} style={inputStyle}>
                  <option value="">— sem bloco —</option>
                  {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                </select>
                <p className="text-[10px] mt-1" style={{ color: "var(--text-faint)" }}>Preencha para novos ativos não cadastrados</p>
              </Field>

              <div className="grid grid-cols-3 gap-4">
                <Field label="Qtd">
                  <input type="number" step="0.0001" min="0" value={qtd} onChange={(e) => setQtd(e.target.value)} placeholder="0" className={inputClass} style={inputStyle} />
                  {errors.qtd && <p className="text-xs mt-1" style={{ color: "var(--negative)" }}>{errors.qtd}</p>}
                </Field>
                <Field label="Preço">
                  <input type="number" step="0.01" min="0" value={preco} onChange={(e) => setPreco(e.target.value)} placeholder="0.00" className={inputClass} style={inputStyle} />
                </Field>
                <Field label="Valor R$" required>
                  <input type="number" step="0.01" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="0.00" className={inputClass} style={inputStyle} />
                  {errors.valor && <p className="text-xs mt-1" style={{ color: "var(--negative)" }}>{errors.valor}</p>}
                </Field>
              </div>

              <Field label="Notas / Racional">
                <textarea value={obs} onChange={(e) => setObs(e.target.value)} rows={3} placeholder="Por que este evento?" className={`${inputClass} resize-none`} style={inputStyle} />
              </Field>

              {/* 8a: Debitar CAIXA FIC */}
              {tipo === "COMPRA" && (
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <input
                    type="checkbox" checked={debitarCaixa} onChange={(e) => setDebitarCaixa(e.target.checked)}
                    className="w-4 h-4" style={{ accentColor: "var(--accent)" }}
                  />
                  <span className="text-sm" style={{ color: "var(--text-body)" }}>
                    Debitar <span className="font-medium" style={{ color: "var(--warning)" }}>CAIXA FIC FUNCIONÁRIOS</span> (gera saída automática)
                  </span>
                </label>
              )}

              {errors.submit && (
                <p
                  className="text-sm rounded border px-3 py-2"
                  style={{ color: "var(--negative)", borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)" }}
                >
                  {errors.submit}
                </p>
              )}

              <div className="flex gap-3">
                <button
                  type="submit" disabled={submitting}
                  className="rounded-lg px-5 py-2 text-sm font-semibold transition disabled:opacity-50"
                  style={{ whiteSpace: "nowrap", background: "var(--accent)", color: "var(--bg-card)" }}
                >
                  {submitting ? "Registrando…" : "Registrar Evento"}
                </button>
                <button
                  type="button" onClick={() => router.back()}
                  className="rounded-lg px-4 py-2 text-sm border transition"
                  style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                >
                  Cancelar
                </button>
              </div>
            </form>
          )}

          {/* ── Tab Histórico (8c) ──────────────────────────────────── */}
          {tab === "historico" && (
            <section
              className="rounded-xl border overflow-hidden"
              style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
            >
              <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border-soft)" }}>
                <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Últimos 20 Eventos</h2>
                <button onClick={loadEventos} className="text-xs transition" style={{ color: "var(--text-faint)" }}>↺ Atualizar</button>
              </div>
              {loadingEvts ? (
                <div className="animate-pulse p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded" style={{ background: "var(--bg-card-alt)" }} />)}</div>
              ) : eventos.length === 0 ? (
                <p className="px-5 py-4 text-sm" style={{ color: "var(--text-faint)" }}>Nenhum evento encontrado</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                        <th className="px-3 py-2 text-left">Data</th>
                        <th className="px-3 py-2 text-left">Ativo</th>
                        <th className="px-3 py-2 text-left">Tipo</th>
                        <th className="px-3 py-2 text-right">Qtd</th>
                        <th className="px-3 py-2 text-right">Valor</th>
                        <th className="px-3 py-2 text-left">Obs</th>
                        <th className="px-3 py-2 text-center">Ações</th>
                      </tr>
                    </thead>
                    <tbody>
                      {eventos.map((e) => (
                        <React.Fragment key={e.id}>
                          <tr
                            className="border-b transition"
                            style={{ borderColor: "var(--border-soft)" }}
                            onMouseEnter={(ev) => (ev.currentTarget.style.background = "var(--bg-card-alt)")}
                            onMouseLeave={(ev) => (ev.currentTarget.style.background = "transparent")}
                          >
                            <td className="px-3 py-2" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{String(e.data)}</td>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{e.ativo}</td>
                            <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{e.tipo}</td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{e.qtd != null ? e.qtd.toFixed(4) : "—"}</td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(e.valor)}</td>
                            <td className="px-3 py-2 max-w-[120px] truncate" style={{ color: "var(--text-faint)" }}>{e.obs ?? "—"}</td>
                            <td className="px-3 py-2 text-center">
                              <div className="flex gap-2 justify-center">
                                <button onClick={() => { setEditId(e.id); setEditObs(e.obs ?? ""); }} className="hover:underline text-[10px]" style={{ color: "var(--purple-accent)" }}>Editar</button>
                                <button onClick={() => deleteEvento(e.id)} className="hover:underline text-[10px]" style={{ color: "var(--negative)" }}>Excluir</button>
                              </div>
                            </td>
                          </tr>
                          {editId === e.id && (
                            <tr className="border-b" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                              <td colSpan={7} className="px-3 py-2">
                                <div className="flex gap-2">
                                  <input
                                    value={editObs} onChange={(ev) => setEditObs(ev.target.value)}
                                    placeholder="Observação" className="flex-1 rounded border px-2 py-1 text-xs focus:outline-none"
                                    style={{ background: "var(--bg-card)", borderColor: "var(--border)", color: "var(--text-body)" }}
                                  />
                                  <button onClick={() => saveEdit(e.id)} className="text-xs px-3 py-1 rounded border" style={{ background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}>Salvar</button>
                                  <button onClick={() => setEditId(null)} className="text-xs px-2 py-1 rounded border" style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>Cancelar</button>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* ── Tab Importar ────────────────────────────────────────── */}
          {tab === "importar" && (
            <div className="space-y-4">

              {/* Mensagens globais */}
              {impOk && (
                <div
                  className="rounded-xl border px-4 py-2.5 text-sm flex items-center justify-between"
                  style={{ borderColor: "rgba(74,124,89,0.4)", background: "rgba(74,124,89,0.08)", color: "var(--positive)" }}
                >
                  {impOk}<button onClick={() => setImpOk(null)} className="ml-4 text-xs flex-shrink-0">✕</button>
                </div>
              )}
              {impReconAlerta && (
                <div
                  className="rounded-xl border px-4 py-2.5 text-sm flex items-center justify-between"
                  style={{ borderColor: "rgba(201,134,43,0.4)", background: "rgba(201,134,43,0.08)", color: "var(--warning)" }}
                >
                  ⚠ {impReconAlerta}<button onClick={() => setImpReconAlerta(null)} className="ml-4 text-xs flex-shrink-0">✕</button>
                </div>
              )}
              {impErr && (
                <div
                  className="rounded-xl border px-4 py-2.5 text-sm flex items-center justify-between"
                  style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
                >
                  {impErr}<button onClick={() => setImpErr(null)} className="ml-4 text-xs flex-shrink-0">✕</button>
                </div>
              )}

              {/* ── Passo 1: Upload ─────────────────────────────────── */}
              {!preview && (
                <section
                  className="rounded-xl border px-5 py-5 space-y-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Importar Extrato</h2>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>PDF, JPEG, PNG, XLSX ou CSV. O Claude identifica o tipo e extrai os eventos automaticamente (~15-60s).</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Arquivo</label>
                      <input
                        type="file" accept=".pdf,.jpg,.jpeg,.png,.xlsx,.xls,.csv"
                        onChange={(e) => setImpFile(e.target.files?.[0] ?? null)}
                        className="mt-1 block w-full text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:text-xs file:cursor-pointer"
                        style={{ color: "var(--text-body)" }}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] uppercase" style={{ color: "var(--text-faint)" }}>Tipo do documento</label>
                      <select value={impTipo} onChange={(e) => setImpTipo(e.target.value)} className={`mt-1 ${inputClass}`} style={inputStyle}>
                        {Object.entries(TIPO_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </div>
                  </div>
                  <label className="flex items-center gap-3 cursor-pointer select-none">
                    <input
                      type="checkbox" checked={impDryRun} onChange={(e) => setImpDryRun(e.target.checked)}
                      className="w-4 h-4" style={{ accentColor: "var(--purple-accent)" }}
                    />
                    <span className="text-sm" style={{ color: "var(--text-body)" }}>Modo de teste — extrair sem gravar no banco</span>
                  </label>
                  <button
                    onClick={uploadExtrato} disabled={uploading || !impFile}
                    className="rounded-lg px-5 py-2 text-sm font-semibold transition disabled:opacity-40"
                    style={{ whiteSpace: "nowrap", background: "var(--purple-accent)", color: "var(--bg-card)" }}
                  >
                    {uploading ? "Processando com Claude (~30s)…" : impDryRun ? "🧪 Testar com Claude (sem gravar)" : "🤖 Processar com Claude"}
                  </button>
                </section>
              )}

              {/* ── Passo 2: Preview ────────────────────────────────── */}
              {preview && (
                <section
                  className="rounded-xl border overflow-hidden"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >

                  {/* Banner modo de teste */}
                  {preview.status === "DRY_RUN" && (
                    <div className="px-5 py-2.5 border-b text-xs" style={{ background: "rgba(108,99,196,0.08)", borderColor: "rgba(108,99,196,0.25)", color: "var(--purple-accent)" }}>
                      🧪 Modo de teste — os dados abaixo foram extraídos pelo Claude, mas <strong>nada foi gravado</strong> no banco.
                    </div>
                  )}

                  {/* Banner identificação Claude */}
                  {preview.tipo_identificado && preview.confianca && (
                    <div className="px-5 py-3 border-b flex items-start justify-between gap-4 flex-wrap" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
                      <div>
                        <p className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
                          🤖 Identificado pelo Claude: {CONFIANCA_ICON[preview.confianca] ?? "⚪"}{" "}
                          <span style={{ color: "var(--warning)" }}>{TIPO_LABELS[preview.tipo_identificado] ?? preview.tipo_identificado}</span>
                          <span className="ml-2" style={{ color: "var(--text-faint)" }}>(confiança {preview.confianca})</span>
                        </p>
                        {preview.justificativa && (
                          <p className="text-[10px] mt-0.5" style={{ color: "var(--text-faint)" }}>{preview.justificativa}</p>
                        )}
                      </div>
                      {/* Reprocessar com outro tipo */}
                      {preview.status === "PREVIEW" && (
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <select
                            value={reprocessTipo} onChange={(e) => setReprocessTipo(e.target.value)}
                            className="text-xs rounded border px-2 py-1 focus:outline-none"
                            style={inputStyle}
                          >
                            {Object.entries(TIPO_LABELS).filter(([v]) => v !== "auto").map(([v, l]) => (
                              <option key={v} value={v}>{l}</option>
                            ))}
                          </select>
                          {reprocessTipo !== preview.tipo_identificado && (
                            <button
                              onClick={reprocessar} disabled={reprocessing}
                              className="text-xs rounded px-2 py-1 border disabled:opacity-50 transition"
                              style={{ whiteSpace: "nowrap", background: "rgba(108,99,196,0.10)", color: "var(--purple-accent)", borderColor: "rgba(108,99,196,0.3)" }}
                            >
                              {reprocessing ? "…" : "🔄 Reprocessar"}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Header com métricas */}
                  <div className="px-5 py-3 border-b flex items-center justify-between flex-wrap gap-2" style={{ borderColor: "var(--border-soft)" }}>
                    <div className="flex items-center gap-4 text-xs" style={{ color: "var(--text-muted)" }}>
                      <span className="font-medium" style={{ color: "var(--text-primary)" }}>{preview.eventos.length} eventos</span>
                      {preview.duplicatas > 0 && <span style={{ color: "var(--negative)" }}>{preview.duplicatas} duplicata(s)</span>}
                      <span>Custo API: ${preview.custo_api_usd.toFixed(4)}</span>
                    </div>
                    <button
                      onClick={cancelarImport}
                      className="text-xs border rounded px-2 py-1 transition"
                      style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
                    >
                      {preview.status === "DRY_RUN" ? "🗑️ Descartar" : "❌ Cancelar"}
                    </button>
                  </div>

                  {/* Tabela de eventos */}
                  <div className="px-5 py-2 text-xs" style={{ color: "var(--text-faint)" }}>
                    {preview.status === "DRY_RUN"
                      ? "Revise os eventos extraídos. Desmarque os que não devem ser gravados. Quando estiver tudo certo, clique em Confirmar e Gravar."
                      : "Desmarque eventos que não devem ser importados. Duplicatas já estão desmarcadas."}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)", background: "var(--bg-app)" }}>
                          <th className="px-3 py-2 text-center w-8">
                            <input
                              type="checkbox"
                              checked={selecionados.length > 0 && selecionados.every(Boolean)}
                              onChange={(e) => setSelecionados(selecionados.map(() => e.target.checked))}
                              style={{ accentColor: "var(--accent)" }}
                            />
                          </th>
                          <th className="px-3 py-2 text-left">Status</th>
                          <th className="px-3 py-2 text-left">Data</th>
                          <th className="px-3 py-2 text-left">Ativo</th>
                          <th className="px-3 py-2 text-left">Tipo</th>
                          <th className="px-3 py-2 text-right">Qtd</th>
                          <th className="px-3 py-2 text-right">Valor</th>
                          <th className="px-3 py-2 text-left">Obs</th>
                        </tr>
                      </thead>
                      <tbody>
                        {preview.eventos.map((ev, i) => (
                          <tr
                            key={i}
                            className="border-b transition"
                            style={{ borderColor: "var(--border-soft)", opacity: ev.duplicata ? 0.5 : 1 }}
                            onMouseEnter={(e) => { if (!ev.duplicata) e.currentTarget.style.background = "var(--bg-card-alt)"; }}
                            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                          >
                            <td className="px-3 py-2 text-center">
                              <input
                                type="checkbox"
                                checked={selecionados[i] ?? false}
                                onChange={(e) => setSelecionados(selecionados.map((s, j) => j === i ? e.target.checked : s))}
                                style={{ accentColor: "var(--accent)" }}
                              />
                            </td>
                            <td className="px-3 py-2 text-[10px]">
                              {ev.duplicata ? <span style={{ color: "var(--negative)" }}>⚠ Duplicata</span> : <span style={{ color: "var(--positive)" }}>✓ Novo</span>}
                            </td>
                            <td className="px-3 py-2" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{ev.data}</td>
                            <td className="px-3 py-2 font-bold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{ev.ativo}</td>
                            <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{ev.tipo}</td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{ev.qtd != null ? ev.qtd.toFixed(4) : "—"}</td>
                            <td className="px-3 py-2 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{brl(ev.valor)}</td>
                            <td className="px-3 py-2 max-w-[160px] truncate" style={{ color: "var(--text-faint)" }}>{ev.obs ?? ""}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Ver JSON bruto */}
                  {preview.raw_claude_response && (
                    <div className="border-t" style={{ borderColor: "var(--border-soft)" }}>
                      <button
                        onClick={() => setShowRawJson(!showRawJson)}
                        className="w-full px-5 py-2 text-left text-xs transition flex items-center gap-1"
                        style={{ color: "var(--text-muted)" }}
                      >
                        {showRawJson ? "▼" : "▶"} Ver JSON extraído pela IA
                      </button>
                      {showRawJson && (
                        <pre
                          className="px-5 pb-4 text-[10px] overflow-x-auto whitespace-pre-wrap max-h-64"
                          style={{ color: "var(--text-body)", background: "var(--bg-app)" }}
                        >
                          {preview.raw_claude_response}
                        </pre>
                      )}
                    </div>
                  )}

                  {/* Botões de confirmação */}
                  <div className="px-5 py-4 flex items-center gap-3 border-t" style={{ borderColor: "var(--border-soft)" }}>
                    <button
                      onClick={confirmarImport}
                      disabled={confirming || !selecionados.some(Boolean)}
                      className="rounded-lg px-5 py-2 text-sm font-medium border disabled:opacity-40 transition"
                      style={{ whiteSpace: "nowrap", background: "rgba(193,95,60,0.08)", color: "var(--accent-strong)", borderColor: "rgba(193,95,60,0.4)" }}
                    >
                      {confirming ? "Gravando…" : preview.status === "DRY_RUN"
                        ? `✅ Confirmar e gravar ${selecionados.filter(Boolean).length} evento(s)`
                        : `✅ Confirmar ${selecionados.filter(Boolean).length} evento(s)`}
                    </button>
                    <span className="text-xs" style={{ color: "var(--text-faint)" }}>{selecionados.filter(Boolean).length} de {preview.eventos.length} selecionado(s)</span>
                  </div>
                </section>
              )}

              {/* Conflitos de cotas FUNCEF */}
              {conflitos.length > 0 && (
                <section
                  className="rounded-xl border px-5 py-4 space-y-3"
                  style={{ borderColor: "rgba(201,134,43,0.4)", background: "rgba(201,134,43,0.06)" }}
                >
                  <h3 className="text-sm font-semibold" style={{ color: "var(--warning)" }}>⚠ {conflitos.length} cota(s) FUNCEF com valor divergente</h3>
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    Os valores abaixo já existem em HISTORICO_PRECOS com valor diferente. Clique em Forçar para sobrescrever com os valores do extrato.
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-[10px] uppercase border-b" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)" }}>
                          <th className="py-1 text-left">Data</th>
                          <th className="py-1 text-right">Valor atual</th>
                          <th className="py-1 text-right">Valor novo</th>
                          <th className="py-1 text-right">Diferença %</th>
                        </tr>
                      </thead>
                      <tbody>
                        {conflitos.map((c, i) => (
                          <tr key={i} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                            <td className="py-1.5" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{c.data}</td>
                            <td className="py-1.5 text-right" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{c.valor_existente.toFixed(8)}</td>
                            <td className="py-1.5 text-right" style={{ color: "var(--positive)", fontFamily: "var(--font-plex-mono)" }}>{c.valor_novo.toFixed(8)}</td>
                            <td className="py-1.5 text-right" style={{ color: "var(--warning)" }}>{c.diferenca_pct.toFixed(2)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex gap-3">
                    <button
                      onClick={forcarCotas} disabled={confirming}
                      className="rounded px-4 py-1.5 text-sm border disabled:opacity-40 transition"
                      style={{ background: "rgba(201,134,43,0.10)", color: "var(--warning)", borderColor: "rgba(201,134,43,0.4)" }}
                    >
                      {confirming ? "Atualizando…" : "🔄 Forçar atualização de cotas"}
                    </button>
                    <button
                      onClick={() => { setConflitos([]); setConflitosBodyRef(null); resetImport(); }}
                      className="rounded px-3 py-1.5 text-sm border transition"
                      style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
                    >
                      ⏭️ Ignorar conflitos (manter valores atuais)
                    </button>
                  </div>
                </section>
              )}

              {/* ── Histórico de importações ─────────────────────────── */}
              <section
                className="rounded-xl border overflow-hidden"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <div className="px-5 py-3 border-b flex items-center justify-between" style={{ borderColor: "var(--border-soft)" }}>
                  <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Histórico de Importações</h2>
                  <button onClick={loadHistorico} className="text-xs transition" style={{ color: "var(--text-faint)" }}>↺ Atualizar</button>
                </div>
                {loadingHist ? (
                  <div className="animate-pulse p-4 space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-7 rounded" style={{ background: "var(--bg-card-alt)" }} />)}</div>
                ) : historico.length === 0 ? (
                  <p className="px-5 py-4 text-sm" style={{ color: "var(--text-faint)" }}>Nenhuma importação registrada.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-faint)", background: "var(--bg-app)" }}>
                          <th className="px-3 py-2 text-left">ID</th>
                          <th className="px-3 py-2 text-left">Data</th>
                          <th className="px-3 py-2 text-left">Arquivo</th>
                          <th className="px-3 py-2 text-left">Tipo (IA)</th>
                          <th className="px-3 py-2 text-left">Confiança</th>
                          <th className="px-3 py-2 text-left">Status</th>
                          <th className="px-3 py-2 text-right">Extraídos</th>
                          <th className="px-3 py-2 text-right">Gravados</th>
                          <th className="px-3 py-2 text-right">Custo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {historico.map((h) => {
                          const statusIcons: Record<string, string> = {
                            CONFIRMED: "✅", PREVIEW: "🔍", PROCESSING: "⏳",
                            CANCELLED: "❌", ERROR: "🚨", UPLOADED: "📤",
                          };
                          const confIcons: Record<string, string> = { alta: "🟢", media: "🟡", baixa: "🔴" };
                          return (
                            <tr
                              key={h.id}
                              className="border-b transition"
                              style={{ borderColor: "var(--border-soft)" }}
                              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-card-alt)")}
                              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                            >
                              <td className="px-3 py-2" style={{ color: "var(--text-faint)" }}>#{h.id}</td>
                              <td className="px-3 py-2 text-[10px]" style={{ color: "var(--text-body)", fontFamily: "var(--font-plex-mono)" }}>{h.data_upload?.slice(0, 16).replace("T", " ")}</td>
                              <td className="px-3 py-2 max-w-[140px] truncate" style={{ color: "var(--text-body)" }}>{h.arquivo_nome}</td>
                              <td className="px-3 py-2" style={{ color: "var(--warning)" }}>{TIPO_LABELS[h.tipo_identificado_ia ?? ""] ?? h.tipo_identificado_ia ?? "—"}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{confIcons[h.confianca_ia ?? ""] ?? ""} {h.confianca_ia ?? "—"}</td>
                              <td className="px-3 py-2" style={{ color: "var(--text-muted)" }}>{statusIcons[h.status] ?? ""} {h.status}</td>
                              <td className="px-3 py-2 text-right" style={{ color: "var(--text-muted)" }}>{h.total_eventos_extraidos ?? "—"}</td>
                              <td className="px-3 py-2 text-right" style={{ color: "var(--positive)" }}>{h.total_eventos_gravados ?? "—"}</td>
                              <td className="px-3 py-2 text-right" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>${(h.custo_api_usd ?? 0).toFixed(4)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

            </div>
          )}
        </div>
      </main>
    </div>
  );
}
