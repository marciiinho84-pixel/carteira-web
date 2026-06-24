"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState, useRef, useCallback } from "react";
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

const cls = "w-full rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2 text-sm text-[#D1D4DC] focus:outline-none focus:border-[#6366F1] transition";

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-[#6b7280] uppercase tracking-wider">{label}{required && <span className="text-[#EF5350] ml-0.5">*</span>}</label>
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
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

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

  async function uploadExtrato() {
    if (!file) return;
    setUploading(true);
    setImportResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const token = localStorage.getItem("carteira_token");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "https://minhacarteira.duckdns.org/api/v1"}/importacao/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "Erro no upload");
      setImportResult(JSON.stringify(data, null, 2));
    } catch (e: unknown) {
      setImportResult(`Erro: ${e instanceof Error ? e.message : "Desconhecido"}`);
    } finally {
      setUploading(false);
    }
  }

  const sugestTickers = ativo.length >= 1
    ? ativos.map((a) => a.ticker).filter((t) => t.toUpperCase().startsWith(ativo.toUpperCase())).slice(0, 8)
    : [];

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto">
        <div className="px-4 py-4 md:px-8 max-w-3xl space-y-4">
          <h1 className="text-lg font-bold text-white">Novo Evento</h1>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-[#2A2D3A]">
            {([["formulario", "Registrar"], ["historico", "Últimos 20"], ["importar", "Importar Extrato"]] as [Tab, string][]).map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ${tab === t ? "border-[#26A69A] text-[#26A69A]" : "border-transparent text-[#6b7280] hover:text-[#D1D4DC]"}`}>
                {label}
              </button>
            ))}
          </div>

          {/* Toast */}
          {toast && (
            <div className="rounded-xl border border-[#26A69A]/50 bg-[#26A69A]/10 px-4 py-2.5 text-sm text-[#26A69A] flex items-center justify-between">
              {toast}
              <button onClick={() => setToast(null)} className="ml-4 text-xs">✕</button>
            </div>
          )}
          {toastErr && (
            <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-2.5 text-sm text-red-400 flex items-center justify-between">
              {toastErr}
              <button onClick={() => setToastErr(null)} className="ml-4 text-xs">✕</button>
            </div>
          )}

          {/* ── Tab Formulário ──────────────────────────────────────── */}
          {tab === "formulario" && (
            <form onSubmit={submit} className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Tipo" required>
                  <select value={tipo} onChange={(e) => setTipo(e.target.value)} className={cls}>
                    {TIPOS.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </Field>
                <Field label="Data" required>
                  <input type="date" value={data} onChange={(e) => setData(e.target.value)} className={cls} />
                  {errors.data && <p className="text-xs text-[#EF5350] mt-1">{errors.data}</p>}
                </Field>
              </div>

              {/* Ativo com autocomplete */}
              <Field label="Ativo (ticker)" required>
                <div className="relative">
                  <input ref={ativoRef} type="text" value={ativo}
                    onChange={(e) => { setAtivo(e.target.value.toUpperCase()); setShowSugest(true); }}
                    onBlur={() => setTimeout(() => setShowSugest(false), 150)}
                    onFocus={() => setShowSugest(true)}
                    placeholder="Ex: ITSA4" className={cls} autoComplete="off" />
                  {showSugest && sugestTickers.length > 0 && (
                    <div className="absolute top-full left-0 w-full z-20 rounded-lg border border-[#2A2D3A] bg-[#1A1D27] shadow-xl mt-1 overflow-hidden">
                      {sugestTickers.map((t) => (
                        <button key={t} type="button" onMouseDown={() => selectAtivo(t)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-[#2A2D3A] transition">
                          {t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {errors.ativo && <p className="text-xs text-[#EF5350] mt-1">{errors.ativo}</p>}
              </Field>

              {/* 8b: Bloco IPS */}
              <Field label="Bloco IPS (opcional)">
                <select value={blocoIps} onChange={(e) => setBlocoIps(e.target.value)} className={cls}>
                  <option value="">— sem bloco —</option>
                  {BLOCOS_IPS.map((b) => <option key={b}>{b}</option>)}
                </select>
                <p className="text-[10px] text-[#6b7280] mt-1">Preencha para novos ativos não cadastrados</p>
              </Field>

              <div className="grid grid-cols-3 gap-4">
                <Field label="Qtd">
                  <input type="number" step="0.0001" min="0" value={qtd} onChange={(e) => setQtd(e.target.value)} placeholder="0" className={cls} />
                  {errors.qtd && <p className="text-xs text-[#EF5350] mt-1">{errors.qtd}</p>}
                </Field>
                <Field label="Preço">
                  <input type="number" step="0.01" min="0" value={preco} onChange={(e) => setPreco(e.target.value)} placeholder="0.00" className={cls} />
                </Field>
                <Field label="Valor R$" required>
                  <input type="number" step="0.01" value={valor} onChange={(e) => setValor(e.target.value)} placeholder="0.00" className={cls} />
                  {errors.valor && <p className="text-xs text-[#EF5350] mt-1">{errors.valor}</p>}
                </Field>
              </div>

              <Field label="Notas / Racional">
                <textarea value={obs} onChange={(e) => setObs(e.target.value)} rows={3} placeholder="Por que este evento?" className={`${cls} resize-none`} />
              </Field>

              {/* 8a: Debitar CAIXA FIC */}
              {tipo === "COMPRA" && (
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <input type="checkbox" checked={debitarCaixa} onChange={(e) => setDebitarCaixa(e.target.checked)}
                    className="w-4 h-4 accent-[#26A69A]" />
                  <span className="text-sm text-[#D1D4DC]">Debitar <span className="text-[#F59E0B] font-medium">CAIXA FIC FUNCIONÁRIOS</span> (gera saída automática)</span>
                </label>
              )}

              {errors.submit && <p className="text-sm text-[#EF5350] rounded bg-red-900/20 border border-red-800/50 px-3 py-2">{errors.submit}</p>}

              <div className="flex gap-3">
                <button type="submit" disabled={submitting}
                  className="rounded-lg px-5 py-2 text-sm font-medium bg-[#26A69A] text-white hover:bg-[#26A69A]/80 disabled:opacity-50 transition">
                  {submitting ? "Registrando…" : "Registrar Evento"}
                </button>
                <button type="button" onClick={() => router.back()}
                  className="rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#6b7280] hover:text-[#D1D4DC] hover:bg-[#2A2D3A] transition">
                  Cancelar
                </button>
              </div>
            </form>
          )}

          {/* ── Tab Histórico (8c) ──────────────────────────────────── */}
          {tab === "historico" && (
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] overflow-hidden">
              <div className="px-5 py-3 border-b border-[#2A2D3A] flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">Últimos 20 Eventos</h2>
                <button onClick={loadEventos} className="text-xs text-[#6b7280] hover:text-[#D1D4DC] transition">↺ Atualizar</button>
              </div>
              {loadingEvts ? (
                <div className="animate-pulse p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-8 rounded bg-[#2A2D3A]" />)}</div>
              ) : eventos.length === 0 ? (
                <p className="px-5 py-4 text-sm text-[#6b7280]">Nenhum evento encontrado</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
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
                        <>
                          <tr key={e.id} className="border-b border-[#2A2D3A] hover:bg-[#2A2D3A]/20">
                            <td className="px-3 py-2 font-mono">{String(e.data)}</td>
                            <td className="px-3 py-2 font-bold text-white">{e.ativo}</td>
                            <td className="px-3 py-2 text-[#6b7280]">{e.tipo}</td>
                            <td className="px-3 py-2 text-right font-mono">{e.qtd != null ? e.qtd.toFixed(4) : "—"}</td>
                            <td className="px-3 py-2 text-right font-mono">{brl(e.valor)}</td>
                            <td className="px-3 py-2 text-[#6b7280] max-w-[120px] truncate">{e.obs ?? "—"}</td>
                            <td className="px-3 py-2 text-center">
                              <div className="flex gap-2 justify-center">
                                <button onClick={() => { setEditId(e.id); setEditObs(e.obs ?? ""); }}
                                  className="text-[#6366F1] hover:underline text-[10px]">Editar</button>
                                <button onClick={() => deleteEvento(e.id)}
                                  className="text-[#EF5350] hover:underline text-[10px]">Excluir</button>
                              </div>
                            </td>
                          </tr>
                          {editId === e.id && (
                            <tr key={`edit-${e.id}`} className="border-b border-[#2A2D3A] bg-[#0F1117]/60">
                              <td colSpan={7} className="px-3 py-2">
                                <div className="flex gap-2">
                                  <input value={editObs} onChange={(ev) => setEditObs(ev.target.value)}
                                    placeholder="Observação" className="flex-1 rounded bg-[#1A1D27] border border-[#2A2D3A] px-2 py-1 text-xs text-[#D1D4DC] focus:outline-none focus:border-[#26A69A]" />
                                  <button onClick={() => saveEdit(e.id)} className="text-xs px-3 py-1 rounded bg-[#26A69A]/20 text-[#26A69A] border border-[#26A69A]/40">Salvar</button>
                                  <button onClick={() => setEditId(null)} className="text-xs px-2 py-1 rounded border border-[#2A2D3A] text-[#6b7280]">Cancelar</button>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          {/* ── Tab Importar (8d) ───────────────────────────────────── */}
          {tab === "importar" && (
            <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
              <h2 className="text-sm font-semibold text-white">Importar Extrato (PDF / Excel)</h2>
              <p className="text-xs text-[#6b7280]">Selecione o extrato do broker. O sistema irá interpretar e criar os eventos automaticamente.</p>
              <div className="space-y-3">
                <input type="file" accept=".pdf,.xlsx,.xls,.csv"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="block text-sm text-[#D1D4DC] file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:border-[#2A2D3A] file:text-xs file:bg-[#1A1D27] file:text-[#D1D4DC] hover:file:bg-[#2A2D3A] file:cursor-pointer" />
                <button onClick={uploadExtrato} disabled={uploading || !file}
                  className="rounded-lg px-5 py-2 text-sm font-medium bg-[#6366F1]/20 text-[#6366F1] border border-[#6366F1]/40 hover:bg-[#6366F1]/30 disabled:opacity-40 transition">
                  {uploading ? "Enviando…" : "Enviar e Processar"}
                </button>
              </div>
              {importResult && (
                <pre className="mt-3 p-3 rounded bg-[#0F1117] border border-[#2A2D3A] text-[10px] text-[#D1D4DC] overflow-x-auto whitespace-pre-wrap">
                  {importResult}
                </pre>
              )}
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
