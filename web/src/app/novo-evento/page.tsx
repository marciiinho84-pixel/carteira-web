"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import { apiFetch, clearToken } from "@/lib/api";

const TIPOS = [
  "COMPRA", "VENDA", "DIVIDENDO", "JCP", "RENDIMENTO",
  "BONIFICACAO", "AMORTIZACAO", "APORTE_EXTERNO", "RESGATE_EXTERNO",
  "CONTRIBUICAO", "RESGATE", "APORTE",
];

interface Posicao { ticker: string }

interface EventoPayload {
  data: string;
  ativo: string;
  tipo: string;
  qtd: number | null;
  preco: number | null;
  valor: number;
  obs: string;
}

function InputField({
  label, required, children,
}: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-[#6b7280] uppercase tracking-wider">
        {label}{required && <span className="text-[#EF5350] ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

const cls = "w-full rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2 text-sm text-[#D1D4DC] focus:outline-none focus:border-[#6366F1] transition";

export default function NovoEvento() {
  const router = useRouter();
  const [tipo, setTipo] = useState("COMPRA");
  const [data, setData] = useState(() => new Date().toISOString().slice(0, 10));
  const [ativo, setAtivo] = useState("");
  const [qtd, setQtd] = useState("");
  const [preco, setPreco] = useState("");
  const [valor, setValor] = useState("");
  const [obs, setObs] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [tickers, setTickers] = useState<string[]>([]);
  const [showSugest, setShowSugest] = useState(false);
  const ativoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    apiFetch<Posicao[]>("/posicoes").then((pos) => {
      setTickers(pos.map((p) => p.ticker).sort());
    }).catch(() => {});
  }, [router]);

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!ativo.trim()) errs.ativo = "Ativo obrigatório";
    if (!data) errs.data = "Data obrigatória";
    else if (isNaN(Date.parse(data))) errs.data = "Data inválida";
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
      const payload: EventoPayload = {
        data,
        ativo: ativo.trim().toUpperCase(),
        tipo,
        qtd: qtd ? Number(qtd) : null,
        preco: preco ? Number(preco) : null,
        valor: Number(valor),
        obs: obs.trim(),
      };
      await apiFetch("/eventos", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setToast("Evento registrado com sucesso!");
      // reset
      setAtivo("");
      setQtd("");
      setPreco("");
      setValor("");
      setObs("");
      setTimeout(() => setToast(null), 4000);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao registrar evento";
      setErrors({ submit: msg });
    } finally {
      setSubmitting(false);
    }
  }

  const sugestTickers = ativo.length >= 1
    ? tickers.filter((t) => t.startsWith(ativo.toUpperCase())).slice(0, 8)
    : [];

  return (
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 px-4 py-6 md:px-8 max-w-2xl space-y-4">
        <h1 className="text-lg font-bold text-white">Registrar Evento</h1>

        {toast && (
          <div className="rounded-xl border border-[#26A69A]/50 bg-[#26A69A]/10 px-4 py-3 text-sm text-[#26A69A]">
            {toast}
            <button
              onClick={() => setToast(null)}
              className="ml-4 text-xs underline"
            >
              ✕
            </button>
          </div>
        )}

        <form onSubmit={submit} className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-5 space-y-4">
          {/* Tipo e data */}
          <div className="grid grid-cols-2 gap-4">
            <InputField label="Tipo" required>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value)}
                className={cls}
              >
                {TIPOS.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              {errors.tipo && <p className="text-xs text-[#EF5350] mt-1">{errors.tipo}</p>}
            </InputField>
            <InputField label="Data" required>
              <input
                type="date"
                value={data}
                onChange={(e) => setData(e.target.value)}
                className={cls}
              />
              {errors.data && <p className="text-xs text-[#EF5350] mt-1">{errors.data}</p>}
            </InputField>
          </div>

          {/* Ativo com autocomplete */}
          <InputField label="Ativo (ticker)" required>
            <div className="relative">
              <input
                ref={ativoRef}
                type="text"
                value={ativo}
                onChange={(e) => { setAtivo(e.target.value.toUpperCase()); setShowSugest(true); }}
                onBlur={() => setTimeout(() => setShowSugest(false), 150)}
                onFocus={() => setShowSugest(true)}
                placeholder="Ex: ITSA4"
                className={cls}
                autoComplete="off"
              />
              {showSugest && sugestTickers.length > 0 && (
                <div className="absolute top-full left-0 w-full z-20 rounded-lg border border-[#2A2D3A] bg-[#1A1D27] shadow-xl mt-1 overflow-hidden">
                  {sugestTickers.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onMouseDown={() => { setAtivo(t); setShowSugest(false); }}
                      className="w-full text-left px-3 py-2 text-sm text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {errors.ativo && <p className="text-xs text-[#EF5350] mt-1">{errors.ativo}</p>}
          </InputField>

          {/* Qtd, Preço, Valor */}
          <div className="grid grid-cols-3 gap-4">
            <InputField label="Qtd">
              <input
                type="number"
                step="0.0001"
                min="0"
                value={qtd}
                onChange={(e) => setQtd(e.target.value)}
                placeholder="0"
                className={cls}
              />
              {errors.qtd && <p className="text-xs text-[#EF5350] mt-1">{errors.qtd}</p>}
            </InputField>
            <InputField label="Preço">
              <input
                type="number"
                step="0.01"
                min="0"
                value={preco}
                onChange={(e) => setPreco(e.target.value)}
                placeholder="0.00"
                className={cls}
              />
            </InputField>
            <InputField label="Valor R$" required>
              <input
                type="number"
                step="0.01"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                placeholder="0.00"
                className={cls}
              />
              {errors.valor && <p className="text-xs text-[#EF5350] mt-1">{errors.valor}</p>}
            </InputField>
          </div>

          {/* Observações (racional) */}
          <InputField label="Notas / Racional da decisão">
            <textarea
              value={obs}
              onChange={(e) => setObs(e.target.value)}
              rows={3}
              placeholder="Por que este evento? Contexto de mercado, convicção…"
              className={`${cls} resize-none`}
            />
          </InputField>

          {errors.submit && (
            <p className="text-sm text-[#EF5350] rounded bg-red-900/20 border border-red-800/50 px-3 py-2">
              {errors.submit}
            </p>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg px-5 py-2 text-sm font-medium bg-[#26A69A] text-white hover:bg-[#26A69A]/80 disabled:opacity-50 transition"
            >
              {submitting ? "Registrando…" : "Registrar Evento"}
            </button>
            <button
              type="button"
              onClick={() => router.back()}
              className="rounded-lg px-4 py-2 text-sm border border-[#2A2D3A] text-[#6b7280] hover:text-[#D1D4DC] hover:bg-[#2A2D3A] transition"
            >
              Cancelar
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
