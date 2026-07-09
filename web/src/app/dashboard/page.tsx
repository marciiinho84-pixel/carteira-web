"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/Nav";
import ActionBar from "@/components/ActionBar";
import { apiFetch, clearToken } from "@/lib/api";

interface Alerta { nivel: string; ativo: string; mensagem: string }
interface VencRF { ticker: string; familia?: string; data_vencimento: string; dias_restantes: number; valor_atual?: number; alerta: string }

interface DashboardData {
  patrimonio_total: number;
  patrimonio_gerida: number;
  patrimonio_funcef: number;
  patrimonio_rv: number;
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

export default function Dashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, [router]);

  const nivelCor: Record<string, string> = { CRITICO: red, ATENCAO: amber, OK: green };

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
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  <KPI label="Carteira Gerida" value={brl(data.patrimonio_gerida)} color={green} />
                  <KPI label="FUNCEF" value={brl(data.patrimonio_funcef)} color={amber} sub="excluída do IPS" />
                  <KPI label="Renda Variável" value={brl(data.patrimonio_rv)} color={purple} />
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
                    <KPI label="Sharpe" value={fmt(data.sharpe, 2)} />
                    <KPI label="Vol. anualizada" value={pct(data.vol_anualizada, 2)} />
                    <KPI label="Drawdown máx." value={pct(data.drawdown_max, 2)} color={data.drawdown_max != null ? red : "var(--text-primary)"}
                      sub={data.drawdown_max_data ?? undefined} />
                    <KPI label="Beta vs IBOV" value={fmt(data.beta_ibov, 2)} />
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
                    <KPI label="Proventos próx. 30d" value={brl(data.proventos_30d)} color={green} />
                  </div>
                </section>
              </div>

              {/* Alertas */}
              {data.alertas.length > 0 && (
                <section
                  className="rounded-xl border overflow-hidden"
                  style={{ borderColor: "var(--border)", background: "var(--bg-card)", boxShadow: cardShadow }}
                >
                  <div className="px-5 py-3 border-b" style={{ borderColor: "var(--border-soft)" }}>
                    <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{data.n_alertas} Alerta{data.n_alertas !== 1 ? "s" : ""}</h2>
                  </div>
                  <div className="divide-y" style={{ borderColor: "var(--border-soft)" }}>
                    {data.alertas.map((a, i) => (
                      <div key={i} className="flex items-start gap-3 px-5 py-3">
                        <span className="text-xs font-bold shrink-0 mt-0.5" style={{ color: nivelCor[a.nivel] ?? amber }}>{a.nivel}</span>
                        <span className="text-xs font-semibold shrink-0" style={{ color: "var(--text-primary)", fontFamily: "var(--font-plex-mono)" }}>{a.ativo}</span>
                        <span className="text-xs" style={{ color: "var(--text-body)" }}>{a.mensagem}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

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
                            <td className="px-4 py-2 font-semibold" style={{ color: "var(--text-primary)" }}>{v.ticker}</td>
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
