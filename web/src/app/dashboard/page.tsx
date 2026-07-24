"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";
import { useRefreshSignal } from "@/lib/refresh-context";
import PatrimonioChart from "./PatrimonioChart";

interface Alerta { nivel: string; ativo: string; mensagem: string }
interface VencRF { ticker: string; familia?: string; data_vencimento: string; dias_restantes: number; valor_atual?: number; alerta: string }

interface DashboardData {
  patrimonio_total: number;
  patrimonio_gerida: number;
  patrimonio_funcef: number;
  patrimonio_rv: number;
  caixa_geral: number;
  twr_gerida_ytd: number;
  twr_total_ytd: number;
  twr_rv_ytd: number;
  cdi_ytd: number;
  ibov_ytd: number;
  sp500_brl_ytd: number;
  excesso_cdi: number;
  sharpe: number;
  pnl_vendas_rv: number;
  n_alertas: number;
  alertas: Alerta[];
  var_dia?: number | null;
  var_dia_pct?: number | null;
  var_mercado_dia?: number | null;
  fluxo_dia?: number | null;
  drawdown_max?: number | null;
  drawdown_max_data?: string | null;
  vol_anualizada?: number | null;
  beta_ibov?: number | null;
  yield_12m?: number | null;
  yield_12m_gerida?: number | null;
  renda_anual_est?: number | null;
  proventos_30d?: number | null;
  vencimentos_rf: VencRF[];
}

interface IrMensalRow {
  mes: string;
  gera_darf: boolean;
  ir_devido: number;
  darf_vencimento: string | null;
}

interface EvolucaoDiaria {
  data: string;
  patrimonio_total: number;
  twr_gerida: number;
  cdi_acum: number;
  ibov_acum: number;
}

interface Posicao {
  composite: string;
  classe?: string;
  valor_atual: number;
}

interface ProventoItem { data: string; valor: number }
interface ProventosProjetados {
  historico: ProventoItem[];
  projecao: ProventoItem[];
  total_historico: number;
  total_projetado_12m: number;
  aviso: string;
}

interface DecisaoPendente {
  ativo: string;
  acao: string;
  revisao_em: string | null;
}

function brl(n: number | null | undefined, digits = 0): string {
  if (n == null) return "—";
  return "R$ " + n.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
function pct(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  const sign = n >= 0 ? "+" : "";
  return sign + (n * 100).toFixed(d) + "%";
}
function fmt(n: number | null | undefined, d = 2): string {
  if (n == null) return "—";
  return n.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function dataCurta(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return iso ?? "—";
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}
function dataBr(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return "—";
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}
function sharpeInterp(v: number): string {
  return v < 0.5 ? "Defensivo" : v < 1.5 ? "Bom" : "Excelente";
}
function betaInterp(v: number): string {
  return v < 0.5 ? "Defensiva" : v < 0.8 ? "Moderada" : v < 1.2 ? "Alinhada" : "Agressiva";
}

const green = "var(--positive)", red = "var(--negative)", amber = "var(--warning)", purple = "var(--purple-accent)";
const valColor = (n: number | null | undefined) => (n == null ? "var(--text-primary)" : n >= 0 ? green : red);
const cardShadow = "0 1px 3px rgba(61,54,41,0.06)";

function KPI({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div
      className="rounded-xl border px-4 py-3"
      style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
    >
      <p className="text-[10px] uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>{label}</p>
      <p
        className="text-base font-semibold mt-0.5"
        style={{ color: color ?? "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}
      >
        {value}
      </p>
      {sub && <p className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>{sub}</p>}
    </div>
  );
}

// ─── Donut de alocação (mesma técnica de CoerenciaCircle — sala-de-comando) ──

const DONUT_CORES = ["var(--accent)", "var(--positive)", "var(--purple-accent)", "var(--warning)", "var(--text-muted)"];

function AlocacaoDonut({ dados }: { dados: { nome: string; valor: number }[] }) {
  const total = dados.reduce((s, d) => s + d.valor, 0);
  const r = 52;
  const circ = 2 * Math.PI * r;
  let acumulado = 0;
  const fatias = dados.map((d, i) => {
    const frac = total > 0 ? d.valor / total : 0;
    const dash = frac * circ;
    const offset = -acumulado;
    acumulado += dash;
    return { ...d, dash, offset, color: DONUT_CORES[i % DONUT_CORES.length], pct: frac * 100 };
  });

  return (
    <div className="flex items-center gap-4">
      <div className="relative shrink-0" style={{ width: 124, height: 124 }}>
        <svg width={124} height={124} className="-rotate-90">
          <circle cx={62} cy={62} r={r} fill="none" stroke="var(--border-soft)" strokeWidth={16} />
          {fatias.map((f, i) => (
            <circle
              key={i}
              cx={62} cy={62} r={r} fill="none"
              stroke={f.color} strokeWidth={16}
              strokeDasharray={`${f.dash} ${circ - f.dash}`}
              strokeDashoffset={f.offset}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center px-2 text-center">
          <span style={{ fontSize: 9, color: "var(--text-muted)" }}>Gerida</span>
          <span className="font-bold" style={{ fontSize: 12, color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{brl(total)}</span>
        </div>
      </div>
      <div className="flex flex-col gap-1.5 text-xs min-w-0">
        {fatias.map((f, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="shrink-0" style={{ width: 8, height: 8, borderRadius: 2, background: f.color }} />
            <span className="truncate" style={{ color: "var(--text-body)" }}>{f.nome}</span>
            <span className="shrink-0" style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{f.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const { refreshKey } = useRefreshSignal();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [evolucao, setEvolucao] = useState<EvolucaoDiaria[]>([]);
  const [posicoes, setPosicoes] = useState<Posicao[]>([]);
  const [irMensal, setIrMensal] = useState<IrMensalRow[]>([]);
  const [proventos, setProventos] = useState<ProventosProjetados | null>(null);
  const [decisoes, setDecisoes] = useState<DecisaoPendente[]>([]);

  useEffect(() => {
    const token = localStorage.getItem("carteira_token");
    if (!token) { router.replace("/login"); return; }
    apiFetch<DashboardData>("/dashboard")
      .then(setData)
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Erro";
        if (msg.includes("401")) { clearToken(); router.replace("/login"); return; }
        setError(msg);
      })
      .finally(() => setLoading(false));

    // Seções adicionais — falha isolada não derruba o Dashboard inteiro.
    apiFetch<EvolucaoDiaria[]>("/evolucao").then(setEvolucao).catch(() => setEvolucao([]));
    apiFetch<Posicao[]>("/posicoes").then(setPosicoes).catch(() => setPosicoes([]));
    apiFetch<IrMensalRow[]>("/ir-mensal").then(setIrMensal).catch(() => setIrMensal([]));
    apiFetch<ProventosProjetados>("/proventos-projetados").then(setProventos).catch(() => setProventos(null));
    apiFetch<DecisaoPendente[]>("/decisoes/pendentes").then(setDecisoes).catch(() => setDecisoes([]));
  }, [router, refreshKey]);

  const nivelCor: Record<string, string> = { CRITICO: red, ATENCAO: amber, OK: green };

  // ─── DARF do mês corrente ───────────────────────────────────────
  const mesAtual = new Date().toISOString().slice(0, 7);
  const darfMes = irMensal.find((r) => r.mes === mesAtual && r.gera_darf) ?? null;

  // ─── Próximos proventos (30d), com fallback pro histórico ───────
  let proximosProventos: { valor: number; sub: string } | null = null;
  if (proventos) {
    const hoje = new Date();
    const limite = new Date(hoje.getTime() + 30 * 86400000);
    const proximos = proventos.projecao.filter((p) => {
      const d = new Date(p.data);
      return d >= hoje && d <= limite;
    });
    if (proximos.length > 0) {
      const totalProximos = proximos.reduce((s, p) => s + p.valor, 0);
      proximosProventos = {
        valor: totalProximos,
        sub: `${proximos.length} evento${proximos.length > 1 ? "s" : ""} nos próximos 30 dias`,
      };
    } else if (proventos.historico.length > 0) {
      const recentes = proventos.historico.slice(0, 5);
      const totalRec = recentes.reduce((s, p) => s + p.valor, 0);
      proximosProventos = { valor: totalRec, sub: "histórico — sem previsão disponível" };
    }
  }

  // ─── Donut alocação Gerida por classe ────────────────────────────
  const alocacaoPorClasse: Record<string, number> = {};
  for (const p of posicoes) {
    if (p.composite !== "Gerida") continue;
    const classe = p.classe ?? "Outros";
    alocacaoPorClasse[classe] = (alocacaoPorClasse[classe] ?? 0) + (p.valor_atual || 0);
  }
  const dadosDonut = Object.entries(alocacaoPorClasse)
    .map(([nome, valor]) => ({ nome, valor }))
    .sort((a, b) => b.valor - a.valor);

  // ─── Séries do gráfico Patrimônio + TWR/CDI/IBOV ────────────────
  const serieP = evolucao.filter((r) => (r.patrimonio_total || 0) > 0).map((r) => ({ time: r.data, value: r.patrimonio_total }));
  const serieTwr = evolucao.map((r) => ({ time: r.data, value: Math.round(r.twr_gerida * 100 * 10000) / 10000 }));
  const serieCdi = evolucao.map((r) => ({ time: r.data, value: Math.round(r.cdi_acum * 100 * 10000) / 10000 }));
  const serieIbov = evolucao.map((r) => ({ time: r.data, value: Math.round(r.ibov_acum * 100 * 10000) / 10000 }));

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg-app)", color: "var(--text-body)" }}>
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)" }}
          >
            Dashboard
          </h1>

          {loading && (
            <div className="animate-pulse space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{[...Array(8)].map((_, i) => <div key={i} className="h-16 rounded-xl" style={{ background: "var(--bg-card)" }} />)}</div>
              <div className="h-40 rounded-xl" style={{ background: "var(--bg-card)" }} />
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

          {!loading && !error && data && (
            <>
              {/* Alerta DARF */}
              {darfMes && (
                <div
                  className="rounded-xl border px-5 py-3 flex items-center justify-between flex-wrap gap-2"
                  style={{ borderColor: "rgba(180,68,44,0.35)", background: "rgba(180,68,44,0.08)" }}
                >
                  <span className="text-sm font-semibold" style={{ color: "var(--negative)" }}>
                    DARF Código 6015 — IR sobre RV
                  </span>
                  <span className="text-sm" style={{ color: "var(--text-body)" }}>
                    <span className="font-semibold" style={{ fontFamily: "var(--font-plex-mono)", color: "var(--negative)" }}>{brl(darfMes.ir_devido, 2)}</span>
                    {" "}devido — vence em{" "}
                    <span className="font-semibold" style={{ fontFamily: "var(--font-plex-mono)" }}>{dataCurta(darfMes.darf_vencimento)}</span>
                  </span>
                </div>
              )}

              {/* Patrimônio */}
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Patrimônio</h2>
                <p
                  className="mb-3"
                  style={{ color: "var(--text-primary)", fontFamily: "var(--font-source-serif)", fontSize: 34, fontWeight: 600 }}
                >
                  {brl(data.patrimonio_total)}
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KPI label="Carteira Gerida" value={brl(data.patrimonio_gerida)} color={green} />
                  <KPI label="FUNCEF" value={brl(data.patrimonio_funcef)} color={amber} sub="excluída do IPS" />
                  <KPI label="Renda Variável" value={brl(data.patrimonio_rv)} color={purple} />
                  <KPI label="Caixa Geral" value={brl(data.caixa_geral)} />
                </div>
                {data.var_dia != null && (
                  <div className="mt-3 flex flex-wrap gap-4 text-xs border-t pt-3" style={{ borderColor: "var(--border-soft)" }}>
                    <span style={{ color: "var(--text-muted)" }}>Var. dia: <span className="font-semibold" style={{ color: valColor(data.var_dia), fontFamily: "var(--font-plex-mono)" }}>{brl(data.var_dia)}</span></span>
                    <span style={{ color: "var(--text-muted)" }}>Mercado: <span style={{ color: valColor(data.var_mercado_dia), fontFamily: "var(--font-plex-mono)" }}>{brl(data.var_mercado_dia)}</span></span>
                    {data.fluxo_dia != null && <span style={{ color: "var(--text-muted)" }}>Fluxo externo: <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-plex-mono)" }}>{brl(data.fluxo_dia)}</span></span>}
                    <span style={{ color: "var(--text-muted)" }}>Var. % dia: <span className="font-semibold" style={{ color: valColor(data.var_dia_pct), fontFamily: "var(--font-plex-mono)" }}>{pct(data.var_dia_pct)}</span></span>
                  </div>
                )}
              </section>

              {/* Gráfico Patrimônio + TWR/CDI/IBOV + Donut alocação */}
              <div className="grid grid-cols-1 lg:grid-cols-10 gap-4">
                <section
                  className="lg:col-span-7 rounded-xl border px-5 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Patrimônio &amp; Rentabilidade</h2>
                  {serieP.length > 0 ? (
                    <PatrimonioChart patrimonio={serieP} twr={serieTwr} cdi={serieCdi} ibov={serieIbov} />
                  ) : (
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>Dados de evolução indisponíveis.</p>
                  )}
                </section>
                <section
                  className="lg:col-span-3 rounded-xl border px-5 py-4 flex flex-col justify-center"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Alocação Gerida</h2>
                  {dadosDonut.length > 0 ? (
                    <AlocacaoDonut dados={dadosDonut} />
                  ) : (
                    <p className="text-sm" style={{ color: "var(--text-muted)" }}>Sem posições na carteira gerida.</p>
                  )}
                </section>
              </div>

              {/* Performance */}
              <section
                className="rounded-xl border px-5 py-4"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Performance YTD</h2>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <KPI label="TWR Gerida YTD" value={pct(data.twr_gerida_ytd)} color={valColor(data.twr_gerida_ytd)} />
                  <KPI label="TWR Total YTD" value={pct(data.twr_total_ytd)} color={valColor(data.twr_total_ytd)} />
                  <KPI label="CDI YTD" value={pct(data.cdi_ytd)} color="var(--text-primary)" />
                  <KPI label="IBOV YTD" value={pct(data.ibov_ytd)} color={valColor(data.ibov_ytd)} />
                  <KPI label="S&P500 BRL YTD" value={pct(data.sp500_brl_ytd)} color={valColor(data.sp500_brl_ytd)} />
                  <KPI label="Excesso CDI" value={pct(data.excesso_cdi)} color={valColor(data.excesso_cdi)} />
                </div>
              </section>

              {/* Risco e Renda */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <section
                  className="rounded-xl border px-5 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Métricas de Risco</h2>
                  <div className="grid grid-cols-2 gap-3">
                    <KPI label="Sharpe" value={fmt(data.sharpe, 2)} sub={data.sharpe != null ? sharpeInterp(data.sharpe) : undefined} />
                    <KPI label="Vol. anualizada" value={pct(data.vol_anualizada, 2)} />
                    <KPI label="Drawdown máx." value={pct(data.drawdown_max, 2)} color={data.drawdown_max != null ? red : "var(--text-primary)"}
                      sub={data.drawdown_max_data ?? undefined} />
                    <KPI label="Beta vs IBOV" value={fmt(data.beta_ibov, 2)} sub={data.beta_ibov != null ? betaInterp(data.beta_ibov) : undefined} />
                  </div>
                </section>
                <section
                  className="rounded-xl border px-5 py-4"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <h2 className="text-xs uppercase tracking-wider mb-3" style={{ color: "var(--text-muted)" }}>Renda Estimada</h2>
                  <div className="grid grid-cols-2 gap-3">
                    <KPI label="Yield 12m (total)" value={pct(data.yield_12m, 2)} color={green} />
                    <KPI label="Yield 12m (gerida)" value={pct(data.yield_12m_gerida, 2)} color={green} />
                    <KPI label="Renda anual est." value={brl(data.renda_anual_est)} color={green} />
                    <KPI
                      label="Próximos Proventos"
                      value={proximosProventos ? brl(proximosProventos.valor) : brl(data.proventos_30d)}
                      color={green}
                      sub={proximosProventos?.sub}
                    />
                  </div>
                </section>
              </div>

              {/* Alertas + Decisões pendentes */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <section
                  className="rounded-xl border overflow-hidden"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{data.n_alertas} Alerta{data.n_alertas !== 1 ? "s" : ""}</h2>
                  </div>
                  {data.alertas.length > 0 ? (
                    <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                      {data.alertas.map((a, i) => (
                        <div key={i} className="flex items-start gap-3 px-5 py-3">
                          <span className="text-xs font-bold shrink-0 mt-0.5" style={{ color: nivelCor[a.nivel] ?? amber }}>{a.nivel}</span>
                          <Link href={`/ativos/${a.ativo}`} className="text-xs font-semibold shrink-0 hover:underline" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{a.ativo}</Link>
                          <span className="text-xs" style={{ color: "var(--text-body)" }}>{a.mensagem}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="px-5 py-3 text-sm" style={{ color: "var(--text-muted)" }}>Nenhum alerta ativo.</p>
                  )}
                </section>

                <section
                  className="rounded-xl border overflow-hidden"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{decisoes.length} Decis{decisoes.length !== 1 ? "ões" : "ão"} pendente{decisoes.length !== 1 ? "s" : ""}</h2>
                  </div>
                  {decisoes.length > 0 ? (
                    <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                      {decisoes.map((d, i) => (
                        <div key={i} className="flex items-center gap-3 px-5 py-3 text-xs">
                          <Link href={`/ativos/${d.ativo}`} className="font-semibold shrink-0 hover:underline" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{d.ativo}</Link>
                          <span style={{ color: "var(--text-body)" }}>{d.acao}</span>
                          <span className="ml-auto" style={{ color: "var(--text-muted)" }}>revisão em {dataBr(d.revisao_em)}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="px-5 py-3 text-sm" style={{ color: "var(--text-muted)" }}>Nenhuma decisão pendente.</p>
                  )}
                </section>
              </div>

              {/* Vencimentos RF */}
              {data.vencimentos_rf.length > 0 && (
                <section
                  className="rounded-xl border overflow-hidden"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Vencimentos Renda Fixa</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b text-[10px] uppercase" style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}>
                          <th className="px-4 py-2 text-left">Ativo</th>
                          <th className="px-4 py-2 text-left">Família</th>
                          <th className="px-4 py-2 text-right">Vencimento</th>
                          <th className="px-4 py-2 text-right">Dias</th>
                          <th className="px-4 py-2 text-right">Valor</th>
                          <th className="px-4 py-2 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.vencimentos_rf.map((v) => (
                          <tr key={v.ticker} className="border-b" style={{ borderColor: "var(--border-soft)" }}>
                            <td className="px-4 py-2 font-semibold">
                              <Link href={`/ativos/${v.ticker}`} className="hover:underline" style={{ color: "var(--text-primary)" }}>{v.ticker}</Link>
                            </td>
                            <td className="px-4 py-2" style={{ color: "var(--text-muted)" }}>{v.familia ?? "—"}</td>
                            <td className="px-4 py-2 text-right" style={{ fontFamily: "var(--font-plex-mono)", color: "var(--text-body)" }}>{v.data_vencimento}</td>
                            <td className="px-4 py-2 text-right" style={{ fontFamily: "var(--font-plex-mono)", color: nivelCor[v.alerta] ?? "var(--text-primary)" }}>{v.dias_restantes}d</td>
                            <td className="px-4 py-2 text-right" style={{ fontFamily: "var(--font-plex-mono)", color: "var(--text-body)" }}>{brl(v.valor_atual)}</td>
                            <td className="px-4 py-2 text-right font-semibold" style={{ color: nivelCor[v.alerta] ?? "var(--text-primary)" }}>{v.alerta}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {/* P&L Vendas */}
              <div
                className="rounded-xl border px-5 py-3 flex items-center justify-between"
                style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
              >
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>P&L realizado RV (vendas)</span>
                <span className="font-semibold text-sm" style={{ color: valColor(data.pnl_vendas_rv), fontFamily: "var(--font-plex-mono)" }}>{brl(data.pnl_vendas_rv, 2)}</span>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
