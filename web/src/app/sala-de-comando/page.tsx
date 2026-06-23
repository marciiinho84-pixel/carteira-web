"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signOut } from "next-auth/react";
import {
  salaDeComando,
  clearToken,
  auth,
  type SalaDeComandoData,
  type BlocoIPS,
  type Vies,
} from "@/lib/api";
import { useAutomacao } from "@/lib/automacao";

// ─── Paleta TradingView ───────────────────────────────────────────────────────
// bg: #0F1117   card: #1A1D27   border: #2A2D3A
// teal: #26A69A  red: #EF5350   text: #D1D4DC   purple: #6366F1

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmt(n: number | undefined | null, digits = 2): string {
  if (n == null) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function pct(n: number | undefined | null, digits = 2): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(digits) + "%";
}

function brl(n: number | undefined | null): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function relativeTime(iso: string | undefined): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}min atrás`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h atrás`;
  return `${Math.floor(hrs / 24)}d atrás`;
}

// ─── Tooltip do Glossário ────────────────────────────────────────────────────

const GLOSSARIO: Record<string, string> = {
  TWR: "Time-Weighted Return — retorno ponderado pelo tempo, que elimina o efeito de aportes e resgates. Mede a qualidade das decisões de investimento.",
  CDI: "Certificado de Depósito Interbancário — taxa de referência de renda fixa no Brasil. Proxy do custo de oportunidade de liquidez.",
  IBOV: "Índice Bovespa — benchmark da Bolsa brasileira. Cartilha: superar o IBOV ajustado ao risco.",
  "Efeito Disposição": "Tendência de vender ganhadores cedo e segurar perdedores. Detectado quando ganhos são realizados em tempo muito menor que perdas.",
  HHI: "Herfindahl-Hirschman — soma dos quadrados dos pesos de cada ativo. Quanto maior, mais concentrada a carteira. Acima de 15: concentrado.",
  Drawdown: "Perda percentual do pico ao vale. Mede a queda máxima sofrida antes de recuperação.",
  "Coerência": "Índice que cruza comportamento real (o que foi feito) com estratégia declarada (IPS + teses). 100% = alinhamento total.",
};

function Tooltip({ term }: { term: string }) {
  const tip = GLOSSARIO[term];
  if (!tip) return <span className="text-[#D1D4DC]">{term}</span>;
  return (
    <span className="relative group cursor-help border-b border-dotted border-[#6366F1] text-[#D1D4DC]">
      {term}
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 rounded-lg border border-[#2A2D3A] bg-[#1A1D27] px-3 py-2 text-xs text-[#D1D4DC] opacity-0 group-hover:opacity-100 transition-opacity z-50 shadow-xl leading-relaxed">
        {tip}
      </span>
    </span>
  );
}

// ─── Semáforo ────────────────────────────────────────────────────────────────

function Semaforo({ nivel }: { nivel: string }) {
  const map: Record<string, { color: string; label: string }> = {
    VERDE:    { color: "#26A69A", label: "🟢" },
    AMARELO:  { color: "#F59E0B", label: "🟡" },
    VERMELHO: { color: "#EF5350", label: "🔴" },
  };
  const s = map[nivel] ?? map.VERDE;
  return <span title={nivel} style={{ color: s.color }} className="text-lg">{s.label}</span>;
}

// ─── Barra IPS ───────────────────────────────────────────────────────────────

function BarraIPS({ b }: { b: BlocoIPS }) {
  const real  = Math.round(b.pct_real * 100);
  const alvo  = Math.round(b.pct_alvo * 100);
  const bMin  = Math.round(b.banda_min * 100);
  const bMax  = Math.round(b.banda_max * 100);
  const color = b.status === "OK" ? "#26A69A" : "#EF5350";
  const pctPos = Math.min(100, Math.max(0, b.pct_real / (b.banda_max || 0.5) * 100));

  const blocoLabel: Record<string, string> = {
    SWING_TRADE: "Swing Trade",
    GROWTH:      "Growth",
    DEFENSIVOS:  "Defensivos",
    RENDA_FIXA:  "Renda Fixa",
    FORA_IPS:    "Fora IPS",
  };

  return (
    <div className="space-y-1 cursor-pointer" onClick={() => { if (typeof window !== "undefined") window.location.href = `/blocos/${b.bloco}`; }}>
      <div className="flex justify-between items-center text-xs">
        <span className="text-[#D1D4DC] font-medium hover:text-[#26A69A] transition">{blocoLabel[b.bloco] ?? b.bloco}</span>
        <span className="font-mono" style={{ color }}>
          {real}% <span className="text-[#6b7280]">/ alvo {alvo}%</span>
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-[#2A2D3A] overflow-hidden">
        {/* banda */}
        <div
          className="absolute h-full opacity-20"
          style={{
            left:  `${bMin / (bMax || 50) * 100}%`,
            right: `${100 - Math.min(100, bMax / (bMax || 50) * 100)}%`,
            backgroundColor: "#26A69A",
          }}
        />
        {/* real */}
        <div
          className="absolute h-full rounded-full transition-all"
          style={{ width: `${pctPos}%`, backgroundColor: color }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-[#6b7280]">
        <span>{bMin}%</span>
        <span>{bMax}%</span>
      </div>
    </div>
  );
}

// ─── Círculo de coerência ────────────────────────────────────────────────────

function CoerenciaCircle({ score }: { score: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 70 ? "#26A69A" : score >= 40 ? "#F59E0B" : "#EF5350";

  return (
    <div className="flex flex-col items-center">
      <svg width={96} height={96} className="-rotate-90">
        <circle cx={48} cy={48} r={r} fill="none" stroke="#2A2D3A" strokeWidth={8} />
        <circle
          cx={48} cy={48} r={r} fill="none"
          stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="mt-[-72px] flex flex-col items-center pointer-events-none">
        <span className="text-2xl font-bold" style={{ color }}>{score}</span>
        <span className="text-[10px] text-[#6b7280] mt-[-2px]">/ 100</span>
      </div>
      <p className="mt-8 text-xs text-[#6b7280]">
        <Tooltip term="Coerência" />
      </p>
    </div>
  );
}

// ─── Tag de instrumentista ────────────────────────────────────────────────────

function instrTag(content: string): string {
  if (/fundament|múltiplo|P\/L|ROE|DY|EBITDA/i.test(content)) return "📊 Fundamentalista";
  if (/técnic|RSI|MACD|média móvel|candlestick|bollinger/i.test(content)) return "📈 Técnico";
  if (/macro|Selic|IPCA|câmbio|Focus|juros/i.test(content)) return "🌍 Macro";
  if (/notícia|news|evento|corporativo/i.test(content)) return "📰 Notícias";
  if (/comportament|viés|disposição|overtrading|coerência/i.test(content)) return "🪞 Comportamental";
  return "🎼 Maestro";
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function SalaDeComando() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [data, setData] = useState<SalaDeComandoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedObs, setExpandedObs] = useState<number | null>(null);
  const { nivelMaximo } = useAutomacao();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [me, sd] = await Promise.all([auth.me(), salaDeComando()]);
      setEmail(me.email);
      setData(sd);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erro ao carregar dados";
      if (
        msg.includes("401") || msg.includes("Unauthorized") ||
        msg.includes("inválido") || msg.includes("expirado") || msg.includes("Token")
      ) {
        clearToken();
        router.replace("/login");
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    load();
  }, [router, load]);

  function logout() {
    clearToken();
    signOut({ callbackUrl: "/login" });
  }

  // ── Skeleton ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <main className="min-h-screen bg-[#0F1117] p-4 md:p-8">
        <div className="mx-auto max-w-7xl space-y-4 animate-pulse">
          <div className="h-28 rounded-xl bg-[#1A1D27]" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 h-64 rounded-xl bg-[#1A1D27]" />
            <div className="h-64 rounded-xl bg-[#1A1D27]" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="h-56 rounded-xl bg-[#1A1D27]" />
            <div className="h-56 rounded-xl bg-[#1A1D27]" />
          </div>
        </div>
      </main>
    );
  }

  const kpis = data?.kpis;
  const engineOk = kpis?.engine_ok === true;

  return (
    <main className="min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <div className="mx-auto max-w-7xl px-4 py-4 md:px-8 md:py-6 space-y-4">

        {/* ── 1. HEADER ─────────────────────────────────────────────────────── */}
        <header className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            {/* título + badge */}
            <div className="flex items-center gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg font-bold text-white">App Minha Carteira</h1>
                  <span className="rounded-md bg-[#6366F1]/20 px-2 py-0.5 text-[10px] font-bold text-[#6366F1] border border-[#6366F1]/30">
                    {kpis?.nivel_automacao ?? "L2"}
                  </span>
                  <Link
                    href="/maestro"
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold border transition-colors hover:opacity-80"
                    style={{
                      backgroundColor: "#6366F1" + "20",
                      borderColor: "#6366F1" + "50",
                      color: "#6366F1",
                    }}
                    title="Abrir Maestro"
                  >
                    Maestro {nivelMaximo !== "L1" ? nivelMaximo : ""}
                  </Link>
                </div>
                {email && (
                  <p className="text-xs text-[#6b7280] mt-0.5">
                    Olá, <span className="text-[#26A69A]">{email}</span>
                    {kpis?.data_referencia && (
                      <span className="ml-2 text-[#4b5563]">· ref. {kpis.data_referencia}</span>
                    )}
                  </p>
                )}
              </div>
            </div>

            {/* KPIs numéricos */}
            {engineOk ? (
              <div className="flex flex-wrap gap-4 md:gap-6">
                <KpiBlock
                  label="Patrimônio Total"
                  value={brl(kpis?.patrimonio_total)}
                  sub={kpis?.var_dia_pct != null ? pct(kpis.var_dia_pct) + " hoje" : undefined}
                  subColor={kpis?.var_dia_pct != null && kpis.var_dia_pct >= 0 ? "#26A69A" : "#EF5350"}
                />
                <KpiBlock
                  label={<Tooltip term="TWR" />}
                  value={pct(kpis?.twr_ytd)}
                  valueColor={kpis?.twr_ytd != null && kpis.twr_ytd >= 0 ? "#26A69A" : "#EF5350"}
                  sub={"vs " + pct(kpis?.cdi_ytd) + " CDI"}
                />
                <KpiBlock
                  label={<Tooltip term="IBOV" />}
                  value={pct(kpis?.ibov_ytd)}
                  sub={"excesso " + pct(kpis?.excesso_cdi)}
                  subColor={kpis?.excesso_cdi != null && kpis.excesso_cdi >= 0 ? "#26A69A" : "#EF5350"}
                />
              </div>
            ) : (
              <div className="text-xs text-[#6b7280] italic">
                Engine não calculado — use POST /calcular no Streamlit para atualizar os dados.
              </div>
            )}

            <button
              onClick={logout}
              className="rounded-lg border border-[#2A2D3A] px-3 py-1.5 text-xs text-[#6b7280] hover:border-[#4b5563] hover:text-[#D1D4DC] transition self-start"
            >
              Sair
            </button>
          </div>
        </header>

        {error && (
          <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">
            {error}
            <button onClick={load} className="ml-3 underline text-xs">tentar novamente</button>
          </div>
        )}

        {/* ── Grid principal ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* ── 2. ORQUESTRA ────────────────────────────────────────────────── */}
          <section className="md:col-span-2 rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
            <SectionHeader icon="🎼" title="Orquestra" sub="Últimas observações do maestro" />
            <div className="px-5 pb-5 space-y-3">
              {!data?.observacoes?.length ? (
                <p className="text-xs text-[#4b5563] italic">
                  Nenhuma observação ainda. Converse com o maestro no Streamlit para alimentar esta seção.
                </p>
              ) : (
                data.observacoes.map((obs) => {
                  const tag = instrTag(obs.content);
                  const expanded = expandedObs === obs.id;
                  return (
                    <div
                      key={obs.id}
                      className="rounded-lg border border-[#2A2D3A] bg-[#0F1117] p-3 space-y-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] rounded bg-[#6366F1]/15 border border-[#6366F1]/30 px-1.5 py-0.5 text-[#6366F1] font-medium">
                          {tag}
                        </span>
                        <span className="text-[10px] text-[#4b5563] shrink-0">
                          {relativeTime(obs.criada_em)}
                        </span>
                      </div>
                      <p className={`text-xs text-[#D1D4DC] leading-relaxed ${expanded ? "" : "line-clamp-3"}`}>
                        {obs.content}
                      </p>
                      {obs.content.length > 120 && (
                        <button
                          onClick={() => setExpandedObs(expanded ? null : obs.id)}
                          className="text-[10px] text-[#6366F1] hover:underline"
                        >
                          {expanded ? "▲ menos" : "▼ Por quê? ver mais"}
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </section>

          {/* ── 3. SEMÁFOROS DE TESES ───────────────────────────────────────── */}
          <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
            <SectionHeader icon="🔬" title="Teses Ativas" sub="Semáforos de invalidação" />
            <div className="px-4 pb-4 space-y-2">
              {!data?.teses?.length ? (
                <p className="text-xs text-[#4b5563] italic">
                  Nenhuma tese ativa. Cadastre no Streamlit → Teses.
                </p>
              ) : (
                data.teses.map((t) => (
                  <div
                    key={t.id}
                    className="rounded-lg border border-[#2A2D3A] bg-[#0F1117] px-3 py-2.5 space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Semaforo nivel={t.nivel_invalidacao} />
                        <span className="font-bold text-sm text-white">{t.ticker}</span>
                        {t.bloco_ips && (
                          <span className="text-[9px] text-[#6b7280] border border-[#2A2D3A] rounded px-1 py-0.5">
                            {t.bloco_ips.replace("_", " ")}
                          </span>
                        )}
                      </div>
                      {t.dias_desde_criacao != null && (
                        <span className="text-[9px] text-[#4b5563]">{t.dias_desde_criacao}d</span>
                      )}
                    </div>
                    {t.racional && (
                      <p className="text-[10px] text-[#6b7280] line-clamp-2">{t.racional}</p>
                    )}
                    {t.criterio_invalidacao && (
                      <p className="text-[10px] text-[#F59E0B]">
                        ⚠️ {t.criterio_invalidacao.slice(0, 80)}
                        {t.criterio_invalidacao.length > 80 ? "…" : ""}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>
        </div>

        {/* ── Grid inferior ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          {/* ── 4. ESPELHO COMPORTAMENTAL ───────────────────────────────────── */}
          <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
            <SectionHeader icon="🪞" title="Espelho Comportamental" sub="Coerência dito vs. feito" />
            <div className="px-5 pb-5 space-y-5">

              {/* Índice de coerência */}
              <div className="flex items-center gap-6">
                <CoerenciaCircle score={data?.comportamental?.indice_coerencia ?? 0} />
                <div className="flex-1 space-y-2">
                  {!data?.comportamental?.vieses?.length ? (
                    <p className="text-xs text-[#4b5563] italic">
                      Sem vieses calculados. Acesse a tool <code className="text-[#6366F1]">vieses_comportamentais</code> no Claude Desktop.
                    </p>
                  ) : (
                    data.comportamental.vieses.map((v) => (
                      <ViesCard key={v.nome_vies} v={v} />
                    ))
                  )}
                </div>
              </div>

              {/* Alocação vs IPS */}
              {data?.comportamental?.blocos?.length ? (
                <div className="space-y-3 pt-2 border-t border-[#2A2D3A]">
                  <p className="text-xs font-medium text-[#6b7280]">Alocação real vs. IPS (Gerida)</p>
                  {data.comportamental.blocos.map((b) => (
                    <BarraIPS key={b.bloco} b={b} />
                  ))}
                </div>
              ) : engineOk ? (
                <p className="text-xs text-[#4b5563] italic pt-2 border-t border-[#2A2D3A]">
                  Alocação por bloco IPS não disponível — recalcule o engine.
                </p>
              ) : null}
            </div>
          </section>

          {/* ── 5. PROGRESS-TO-GOAL ─────────────────────────────────────────── */}
          <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
            <SectionHeader icon="🎯" title="Meta R$ 3M" sub="Progress-to-goal" />
            <div className="px-5 pb-5 space-y-5">
              {!data?.meta?.patrimonio_atual ? (
                <p className="text-xs text-[#4b5563] italic">Engine não calculado.</p>
              ) : (
                <>
                  {/* Barra de progresso */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-[#D1D4DC] font-medium">{brl(data.meta.patrimonio_atual)}</span>
                      <span className="text-[#6b7280]">R$ 3.000.000</span>
                    </div>
                    <div className="h-4 rounded-full bg-[#2A2D3A] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#26A69A] to-[#6366F1] transition-all"
                        style={{ width: `${Math.min(100, (data.meta.pct_atingido ?? 0) * 100)}%` }}
                      />
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-[#26A69A] font-bold">
                        {((data.meta.pct_atingido ?? 0) * 100).toFixed(1)}% atingido
                      </span>
                      <span className="text-[#6b7280]">
                        Falta {brl(3_000_000 - (data.meta.patrimonio_atual ?? 0))}
                      </span>
                    </div>
                  </div>

                  {/* Métricas */}
                  <div className="grid grid-cols-2 gap-3">
                    <MetaBlock
                      label="Projeção"
                      value={data.meta.projecao_ano_meta ? `até ${data.meta.projecao_ano_meta}` : "—"}
                      color="#6366F1"
                    />
                    <MetaBlock
                      label={<Tooltip term="TWR" />}
                      value={pct(data.meta.twr_anualizado) + " a.a."}
                      color="#26A69A"
                    />
                    <MetaBlock
                      label="Aporte atual / mês"
                      value={brl(data.meta.ritmo_mensal_atual)}
                    />
                    <MetaBlock
                      label="Necessário / mês"
                      value={brl(data.meta.ritmo_mensal_necessario)}
                    />
                  </div>

                  {/* Drift alerts */}
                  {data?.comportamental?.blocos?.filter((b) => b.status !== "OK").length ? (
                    <div className="pt-2 border-t border-[#2A2D3A] space-y-1.5">
                      <p className="text-xs font-medium text-[#EF5350]">⚠️ Blocos fora da banda IPS</p>
                      {data.comportamental.blocos
                        .filter((b) => b.status !== "OK")
                        .map((b) => (
                          <div key={b.bloco} className="flex justify-between text-xs">
                            <span className="text-[#D1D4DC]">{b.bloco.replace("_", " ")}</span>
                            <span className="text-[#EF5350]">
                              {Math.round(b.pct_real * 100)}% — {b.status === "ACIMA" ? "acima" : "abaixo"} da banda
                            </span>
                          </div>
                        ))}
                    </div>
                  ) : data?.comportamental?.blocos?.length ? (
                    <p className="text-xs text-[#26A69A] pt-2 border-t border-[#2A2D3A]">
                      ✓ Todos os blocos IPS dentro da banda
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </section>
        </div>

        {/* ── Rodapé ─────────────────────────────────────────────────────────── */}
        <footer className="text-center text-[10px] text-[#4b5563] pb-4">
          App Minha Carteira · v2.5.1 ·{" "}
          <a href="https://minhacarteira.duckdns.org" target="_blank" rel="noreferrer"
            className="text-[#26A69A] hover:underline">Streamlit</a>
          {kpis?.calculado_em && (
            <span className="ml-2">· atualizado {relativeTime(kpis.calculado_em)}</span>
          )}
        </footer>
      </div>
    </main>
  );
}

// ─── Sub-componentes ─────────────────────────────────────────────────────────

function SectionHeader({ icon, title, sub }: { icon: string; title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2A2D3A]">
      <span className="text-base">{icon}</span>
      <div>
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {sub && <p className="text-[10px] text-[#6b7280]">{sub}</p>}
      </div>
    </div>
  );
}

function KpiBlock({
  label, value, sub, valueColor, subColor,
}: {
  label: React.ReactNode;
  value: string;
  sub?: string;
  valueColor?: string;
  subColor?: string;
}) {
  return (
    <div className="text-right md:text-left">
      <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">{label}</p>
      <p className="text-lg font-bold font-mono" style={{ color: valueColor ?? "#D1D4DC" }}>{value}</p>
      {sub && <p className="text-[10px] font-mono" style={{ color: subColor ?? "#6b7280" }}>{sub}</p>}
    </div>
  );
}

function ViesCard({ v }: { v: Vies }) {
  const severityColor = v.detectado
    ? v.severidade === "CRITICO" ? "#EF5350"
      : v.severidade === "ATENCAO" ? "#F59E0B"
      : "#26A69A"
    : "#4b5563";

  return (
    <div className={`rounded border px-2 py-1.5 ${v.detectado ? "border-[#2A2D3A]" : "border-[#1e2030] opacity-50"}`}>
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] font-semibold" style={{ color: severityColor }}>
          {v.detectado ? "● " : "○ "}<Tooltip term={v.nome_vies as keyof typeof GLOSSARIO} />
        </span>
        {v.detectado && (
          <span className="text-[9px] border rounded px-1" style={{ color: severityColor, borderColor: severityColor + "40" }}>
            {v.severidade}
          </span>
        )}
      </div>
      {v.detectado && v.fato_mensuravel && (
        <p className="text-[9px] text-[#6b7280] mt-0.5 leading-snug">{v.fato_mensuravel}</p>
      )}
    </div>
  );
}

function MetaBlock({ label, value, color }: { label: React.ReactNode; value: string; color?: string }) {
  return (
    <div className="rounded-lg bg-[#0F1117] border border-[#2A2D3A] px-3 py-2">
      <p className="text-[9px] text-[#6b7280] uppercase tracking-wider">{label}</p>
      <p className="text-sm font-bold font-mono mt-0.5" style={{ color: color ?? "#D1D4DC" }}>{value}</p>
    </div>
  );
}
