"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signOut } from "next-auth/react";
import {
  salaDeComando,
  marcarObservacaoVisualizada,
  clearToken,
  auth,
  type SalaDeComandoData,
  type BlocoIPS,
  type Vies,
  type CategoriaObservacao,
} from "@/lib/api";
import { useAutomacao } from "@/lib/automacao";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";

// ─── Papel & Tinta — tokens em globals.css ────────────────────────────────────

const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

// ─── Helpers ─────────────────────────────────────────────────────────────────

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
  if (!tip) return <span style={{ color: "var(--text-body)" }}>{term}</span>;
  return (
    <span
      className="relative group cursor-help border-b border-dotted"
      style={{ borderColor: "var(--purple-accent)", color: "var(--text-body)" }}
    >
      {term}
      <span
        className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-72 rounded-lg border px-3 py-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity z-50 shadow-xl leading-relaxed"
        style={{ borderColor: "var(--border)", background: "var(--bg-card)", color: "var(--text-body)" }}
      >
        {tip}
      </span>
    </span>
  );
}

// ─── Semáforo ────────────────────────────────────────────────────────────────

function Semaforo({ nivel }: { nivel: string }) {
  const map: Record<string, string> = {
    VERDE: "var(--positive)",
    AMARELO: "var(--warning)",
    VERMELHO: "var(--negative)",
  };
  const color = map[nivel] ?? map.VERDE;
  return (
    <span
      title={nivel}
      className="inline-block shrink-0 rounded-full"
      style={{ width: 9, height: 9, background: color }}
    />
  );
}

// ─── Barra IPS ───────────────────────────────────────────────────────────────

function BarraIPS({ b }: { b: BlocoIPS }) {
  const real  = Math.round(b.pct_real * 100);
  const alvo  = Math.round(b.pct_alvo * 100);
  const bMin  = Math.round(b.banda_min * 100);
  const bMax  = Math.round(b.banda_max * 100);
  const color = b.status === "OK" ? "var(--positive)" : "var(--negative)";
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
        <span style={{ color: "var(--text-body)", whiteSpace: "nowrap" }}>{blocoLabel[b.bloco] ?? b.bloco}</span>
        <span style={{ fontFamily: "var(--font-plex-mono)", color }}>
          {real}% <span style={{ color: "var(--text-faint)" }}>/ alvo {alvo}%</span>
        </span>
      </div>
      <div className="relative rounded-full overflow-hidden" style={{ height: 6, background: "var(--border-soft)" }}>
        {/* banda */}
        <div
          className="absolute h-full"
          style={{
            left:  `${bMin / (bMax || 50) * 100}%`,
            right: `${100 - Math.min(100, bMax / (bMax || 50) * 100)}%`,
            background: "rgba(122,113,96,0.18)",
          }}
        />
        {/* real */}
        <div
          className="absolute h-full rounded-full transition-all"
          style={{ width: `${pctPos}%`, background: color }}
        />
      </div>
    </div>
  );
}

// ─── Círculo de coerência ────────────────────────────────────────────────────

function CoerenciaCircle({ score }: { score: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = score >= 70 ? "var(--positive)" : score >= 40 ? "var(--warning)" : "var(--negative)";

  return (
    <div className="relative shrink-0" style={{ width: 96, height: 96 }}>
      <svg width={96} height={96} className="-rotate-90">
        <circle cx={48} cy={48} r={r} fill="none" stroke="var(--border-soft)" strokeWidth={8} />
        <circle
          cx={48} cy={48} r={r} fill="none"
          stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-bold" style={{ fontSize: 22, color, fontFamily: "var(--font-plex-mono)" }}>{score}</span>
        <span style={{ fontSize: 9, color: "var(--text-faint)" }}>/ 100</span>
      </div>
    </div>
  );
}

// ─── Badge de categoria do feed da Orquestra ────────────────────────────────

const CATEGORIA_META: Record<CategoriaObservacao, { label: string; color: string; bg: string; border: string }> = {
  ALERTA:          { label: "🔔 Alerta",          color: "var(--warning)",       bg: "rgba(201,134,43,0.12)",  border: "rgba(201,134,43,0.3)" },
  TESE:            { label: "🔬 Tese invalidada", color: "var(--negative)",      bg: "rgba(180,68,44,0.12)",   border: "rgba(180,68,44,0.3)" },
  IPS:             { label: "⚖️ Banda IPS",        color: "var(--warning)",       bg: "rgba(201,134,43,0.12)",  border: "rgba(201,134,43,0.3)" },
  TECNICO:         { label: "📈 Técnico",         color: "var(--accent-strong)", bg: "rgba(193,95,60,0.12)",   border: "rgba(193,95,60,0.3)" },
  FUNDAMENTALISTA: { label: "📊 Fundamentalista", color: "var(--accent-strong)", bg: "rgba(193,95,60,0.12)",   border: "rgba(193,95,60,0.3)" },
  NOTICIA:         { label: "📰 Notícia",         color: "var(--purple-accent)", bg: "rgba(108,99,196,0.12)",  border: "rgba(108,99,196,0.3)" },
  MACRO:           { label: "🌍 Macro",           color: "var(--accent-strong)", bg: "rgba(193,95,60,0.12)",   border: "rgba(193,95,60,0.3)" },
};

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

  async function dispensar(id: number) {
    setData((prev) => (prev ? { ...prev, observacoes: prev.observacoes.filter((o) => o.id !== id) } : prev));
    try {
      await marcarObservacaoVisualizada(id);
    } catch {
      // silencioso — se falhar, o item volta a aparecer no próximo carregamento
    }
  }

  // ── Skeleton ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <main className="min-h-screen p-4 md:p-8" style={{ background: "var(--bg-app)" }}>
        <div className="mx-auto max-w-7xl space-y-4 animate-pulse">
          <div className="h-28 rounded-xl" style={{ background: "var(--bg-card)" }} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 h-64 rounded-xl" style={{ background: "var(--bg-card)" }} />
            <div className="h-64 rounded-xl" style={{ background: "var(--bg-card)" }} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="h-56 rounded-xl" style={{ background: "var(--bg-card)" }} />
            <div className="h-56 rounded-xl" style={{ background: "var(--bg-card)" }} />
          </div>
        </div>
      </main>
    );
  }

  const kpis = data?.kpis;
  const engineOk = kpis?.engine_ok === true;

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
      <ActionBar />
      <div className="mx-auto max-w-7xl px-4 py-4 md:px-8 md:py-6 space-y-4 flex-1">

        {/* ── 1. HEADER ─────────────────────────────────────────────────────── */}
        <header
          className="rounded-xl border px-5 py-4"
          style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            {/* título + badge */}
            <div className="flex items-center gap-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h1
                    className="text-lg font-bold"
                    style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
                  >
                    App Minha Carteira
                  </h1>
                  <span
                    className="rounded-md px-2 py-0.5 text-[10px] font-bold border"
                    style={{ whiteSpace: "nowrap", background: "rgba(193,95,60,0.14)", borderColor: "rgba(193,95,60,0.3)", color: "var(--accent-strong)" }}
                  >
                    {kpis?.nivel_automacao ?? "L2"}
                  </span>
                  <Link
                    href="/maestro"
                    className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold border transition-colors hover:opacity-80"
                    style={{ whiteSpace: "nowrap", background: "rgba(90,124,89,0.14)", borderColor: "rgba(90,124,89,0.3)", color: "var(--positive)" }}
                    title="Abrir Maestro"
                  >
                    Maestro {nivelMaximo !== "L1" ? nivelMaximo : ""}
                  </Link>
                </div>
                {email && (
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    Olá, <span style={{ color: "var(--accent-strong)" }}>{email}</span>
                    {kpis?.data_referencia && (
                      <span className="ml-2" style={{ color: "var(--text-faint)" }}>· ref. {kpis.data_referencia}</span>
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
                  subColor={kpis?.var_dia_pct != null && kpis.var_dia_pct >= 0 ? "var(--positive)" : "var(--negative)"}
                />
                <KpiBlock
                  label={<Tooltip term="TWR" />}
                  value={pct(kpis?.twr_ytd)}
                  valueColor={kpis?.twr_ytd != null && kpis.twr_ytd >= 0 ? "var(--positive)" : "var(--negative)"}
                  sub={"vs " + pct(kpis?.cdi_ytd) + " CDI"}
                />
                <KpiBlock
                  label={<Tooltip term="IBOV" />}
                  value={pct(kpis?.ibov_ytd)}
                  sub={"excesso " + pct(kpis?.excesso_cdi)}
                  subColor={kpis?.excesso_cdi != null && kpis.excesso_cdi >= 0 ? "var(--positive)" : "var(--negative)"}
                />
              </div>
            ) : (
              <div className="text-xs italic" style={{ color: "var(--text-muted)" }}>
                Engine não calculado — use POST /calcular no Streamlit para atualizar os dados.
              </div>
            )}

            <button
              onClick={logout}
              className="rounded-lg border px-3 py-1.5 text-xs transition self-start"
              style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--negative)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; }}
            >
              Sair
            </button>
          </div>
        </header>

        {error && (
          <div
            className="rounded-xl border px-4 py-3 text-sm"
            style={{ borderColor: "rgba(180,68,44,0.3)", background: "rgba(180,68,44,0.08)", color: "var(--negative)" }}
          >
            {error}
            <button onClick={load} className="ml-3 underline text-xs">tentar novamente</button>
          </div>
        )}

        {/* ── Grid principal ─────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* ── 2. ORQUESTRA ────────────────────────────────────────────────── */}
          <section
            className="md:col-span-2 rounded-xl border"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <SectionHeader icon="🎼" title="Orquestra" sub="Fatos novos e relevantes que você ainda não viu" />
            <div className="px-5 pb-5 space-y-3">
              {!data?.observacoes?.length ? (
                <p className="text-xs italic" style={{ color: "var(--text-faint)" }}>
                  Nenhum fato novo desde a última varredura pré-abertura de mercado. Tudo tranquilo.
                </p>
              ) : (
                data.observacoes.map((obs) => {
                  const meta = CATEGORIA_META[obs.categoria] ?? CATEGORIA_META.TECNICO;
                  const expanded = expandedObs === obs.id;
                  return (
                    <div
                      key={obs.id}
                      className="rounded-lg border p-3 space-y-1.5"
                      style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span
                            className="text-[10px] rounded px-1.5 py-0.5 font-medium border"
                            style={{ whiteSpace: "nowrap", background: meta.bg, borderColor: meta.border, color: meta.color }}
                          >
                            {meta.label}
                          </span>
                          <span
                            className="text-[9px] rounded-full px-1.5 py-0.5 font-bold"
                            style={{ background: "var(--accent-strong)", color: "#FFF8EE" }}
                          >
                            novo
                          </span>
                        </div>
                        <span className="text-[10px] shrink-0" style={{ color: "var(--text-faint)" }}>
                          {relativeTime(obs.criado_em)}
                        </span>
                      </div>
                      <p className={`text-xs leading-relaxed ${expanded ? "" : "line-clamp-3"}`} style={{ color: "var(--text-body)" }}>
                        {obs.conteudo}
                      </p>
                      {obs.ativos_relacionados.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {obs.ativos_relacionados.map((tkr) => (
                            <Link
                              key={tkr}
                              href={`/ativos/${tkr}`}
                              className="text-[10px] font-bold rounded px-1.5 py-0.5 border hover:underline"
                              style={{ fontFamily: "var(--font-plex-mono)", color: "var(--text-primary)", borderColor: "var(--border)" }}
                            >
                              {tkr}
                            </Link>
                          ))}
                        </div>
                      )}
                      <div className="flex items-center justify-between pt-0.5">
                        {obs.conteudo.length > 120 ? (
                          <button
                            onClick={() => setExpandedObs(expanded ? null : obs.id)}
                            className="text-[10px] hover:underline"
                            style={{ color: "var(--purple-accent)" }}
                          >
                            {expanded ? "▲ menos" : "▼ ver mais"}
                          </button>
                        ) : <span />}
                        <button
                          onClick={() => dispensar(obs.id)}
                          className="text-[10px] hover:underline"
                          style={{ color: "var(--text-faint)" }}
                        >
                          dispensar ✕
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </section>

          {/* ── 3. SEMÁFOROS DE TESES ───────────────────────────────────────── */}
          <section
            className="rounded-xl border"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <SectionHeader icon="🔬" title="Teses Ativas" sub="Semáforos de invalidação" />
            <div className="px-4 pb-4 space-y-2">
              {!data?.teses?.length ? (
                <p className="text-xs italic" style={{ color: "var(--text-faint)" }}>
                  Nenhuma tese ativa. Cadastre no Streamlit → Teses.
                </p>
              ) : (
                data.teses.map((t) => (
                  <div
                    key={t.id}
                    className="rounded-lg border px-3 py-2.5 space-y-1"
                    style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Semaforo nivel={t.nivel_invalidacao} />
                        <Link
                          href={`/ativos/${t.ticker}`}
                          className="font-bold text-sm hover:underline"
                          style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}
                        >
                          {t.ticker}
                        </Link>
                        {t.bloco_ips && (
                          <span
                            className="text-[9px] rounded px-1 py-0.5 border"
                            style={{ whiteSpace: "nowrap", color: "var(--text-faint)", borderColor: "var(--border)" }}
                          >
                            {t.bloco_ips.replace("_", " ")}
                          </span>
                        )}
                      </div>
                      {t.dias_desde_criacao != null && (
                        <span className="text-[9px]" style={{ color: "var(--text-faint)" }}>{t.dias_desde_criacao}d</span>
                      )}
                    </div>
                    {t.racional && (
                      <p className="text-[10px] line-clamp-2" style={{ color: "var(--text-muted)" }}>{t.racional}</p>
                    )}
                    {t.criterio_invalidacao && (
                      <p className="text-[10px]" style={{ color: "var(--negative)" }}>
                        ⚠ {t.criterio_invalidacao.slice(0, 80)}
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
          <section
            className="rounded-xl border"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <SectionHeader icon="🪞" title="Espelho Comportamental" sub="Coerência dito vs. feito" />
            <div className="px-5 pb-5 space-y-5">

              {/* Índice de coerência */}
              <div className="flex items-center gap-6">
                <CoerenciaCircle score={data?.comportamental?.indice_coerencia ?? 0} />
                <div className="flex-1 space-y-2">
                  {!data?.comportamental?.vieses?.length ? (
                    <p className="text-xs italic" style={{ color: "var(--text-faint)" }}>
                      Sem vieses calculados. Acesse a tool <code style={{ color: "var(--purple-accent)" }}>vieses_comportamentais</code> no Claude Desktop.
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
                <div className="space-y-3 pt-2 border-t" style={{ borderColor: "var(--border-soft)" }}>
                  <p className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>Alocação real vs. IPS (Gerida)</p>
                  {data.comportamental.blocos.map((b) => (
                    <BarraIPS key={b.bloco} b={b} />
                  ))}
                </div>
              ) : engineOk ? (
                <p className="text-xs italic pt-2 border-t" style={{ color: "var(--text-faint)", borderColor: "var(--border-soft)" }}>
                  Alocação por bloco IPS não disponível — recalcule o engine.
                </p>
              ) : null}
            </div>
          </section>

          {/* ── 5. PROGRESS-TO-GOAL ─────────────────────────────────────────── */}
          <section
            className="rounded-xl border"
            style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
          >
            <SectionHeader icon="🎯" title="Meta R$ 3M" sub="Progress-to-goal" />
            <div className="px-5 pb-5 space-y-5">
              {!data?.meta?.patrimonio_atual ? (
                <p className="text-xs italic" style={{ color: "var(--text-faint)" }}>Engine não calculado.</p>
              ) : (
                <>
                  {/* Barra de progresso */}
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(data.meta.patrimonio_atual)}</span>
                      <span style={{ color: "var(--text-faint)" }}>R$ 3.000.000</span>
                    </div>
                    <div className="rounded-full overflow-hidden" style={{ height: 14, background: "var(--border-soft)" }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${Math.min(100, (data.meta.pct_atingido ?? 0) * 100)}%`,
                          background: "linear-gradient(90deg, var(--accent), var(--accent-strong))",
                        }}
                      />
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="font-bold" style={{ color: "var(--positive)" }}>
                        {((data.meta.pct_atingido ?? 0) * 100).toFixed(1)}% atingido
                      </span>
                      <span style={{ color: "var(--text-faint)" }}>
                        Falta {brl(3_000_000 - (data.meta.patrimonio_atual ?? 0))}
                      </span>
                    </div>
                  </div>

                  {/* Métricas */}
                  <div className="grid grid-cols-2 gap-3">
                    <MetaBlock
                      label="Projeção"
                      value={data.meta.projecao_ano_meta ? `até ${data.meta.projecao_ano_meta}` : "—"}
                      color="var(--accent-strong)"
                    />
                    <MetaBlock
                      label={<Tooltip term="TWR" />}
                      value={pct(data.meta.twr_anualizado) + " a.a."}
                      color="var(--positive)"
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
                    <div className="pt-2 border-t space-y-1.5" style={{ borderColor: "var(--border-soft)" }}>
                      <p className="text-xs font-semibold" style={{ color: "var(--negative)" }}>⚠ Blocos fora da banda IPS</p>
                      {data.comportamental.blocos
                        .filter((b) => b.status !== "OK")
                        .map((b) => (
                          <div key={b.bloco} className="flex justify-between text-xs">
                            <span style={{ color: "var(--text-body)" }}>{b.bloco.replace("_", " ")}</span>
                            <span style={{ color: "var(--negative)" }}>
                              {Math.round(b.pct_real * 100)}% — {b.status === "ACIMA" ? "acima" : "abaixo"} da banda
                            </span>
                          </div>
                        ))}
                    </div>
                  ) : data?.comportamental?.blocos?.length ? (
                    <p className="text-xs pt-2 border-t" style={{ color: "var(--positive)", borderColor: "var(--border-soft)" }}>
                      ✓ Todos os blocos IPS dentro da banda
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </section>
        </div>

        {/* ── Rodapé ─────────────────────────────────────────────────────────── */}
        <footer className="text-center text-[10px] pb-4" style={{ color: "var(--text-faint)" }}>
          App Minha Carteira · v2.5.1 ·{" "}
          <a href="https://minhacarteira.duckdns.org" target="_blank" rel="noreferrer"
            className="hover:underline" style={{ color: "var(--accent-strong)" }}>Streamlit</a>
          {kpis?.calculado_em && (
            <span className="ml-2">· atualizado {relativeTime(kpis.calculado_em)}</span>
          )}
        </footer>
      </div>
      </main>
    </div>
  );
}

// ─── Sub-componentes ─────────────────────────────────────────────────────────

function SectionHeader({ icon, title, sub }: { icon: string; title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2 px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
      <span className="text-base">{icon}</span>
      <div>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{title}</h2>
        {sub && <p className="text-[10px]" style={{ color: "var(--text-faint)" }}>{sub}</p>}
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
      <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>{label}</p>
      <p className="text-lg font-bold" style={{ color: valueColor ?? "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{value}</p>
      {sub && <p className="text-[10px]" style={{ color: subColor ?? "var(--text-faint)", fontFamily: "var(--font-plex-mono)" }}>{sub}</p>}
    </div>
  );
}

function ViesCard({ v }: { v: Vies }) {
  const severityColor = v.detectado
    ? v.severidade === "CRITICO" ? "var(--negative)"
      : v.severidade === "ATENCAO" ? "var(--warning)"
      : "var(--positive)"
    : "var(--text-faint)";

  return (
    <div
      className="rounded border px-2 py-1.5"
      style={{ borderColor: "var(--border-soft)", opacity: v.detectado ? 1 : 0.5 }}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] font-semibold" style={{ color: severityColor }}>
          {v.detectado ? "● " : "○ "}<Tooltip term={v.nome_vies as keyof typeof GLOSSARIO} />
        </span>
        {v.detectado && (
          <span className="text-[9px] border rounded px-1" style={{ whiteSpace: "nowrap", color: severityColor, borderColor: severityColor }}>
            {v.severidade}
          </span>
        )}
      </div>
      {v.detectado && v.fato_mensuravel && (
        <p className="text-[9px] mt-0.5 leading-snug" style={{ color: "var(--text-muted)" }}>{v.fato_mensuravel}</p>
      )}
    </div>
  );
}

function MetaBlock({ label, value, color }: { label: React.ReactNode; value: string; color?: string }) {
  return (
    <div className="rounded-lg border px-3 py-2" style={{ borderColor: "var(--border-soft)", background: "var(--bg-app)" }}>
      <p className="text-[9px] uppercase tracking-wider" style={{ color: "var(--text-faint)" }}>{label}</p>
      <p className="text-sm font-bold mt-0.5" style={{ color: color ?? "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{value}</p>
    </div>
  );
}
