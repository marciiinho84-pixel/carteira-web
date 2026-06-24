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
const green = "#26A69A", red = "#EF5350", amber = "#F59E0B", purple = "#6366F1";
const valColor = (n: number | null | undefined) => (n == null ? "#D1D4DC" : n >= 0 ? green : red);

function KPI({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-4 py-3">
      <p className="text-[10px] text-[#6b7280] uppercase tracking-wider">{label}</p>
      <p className="text-base font-bold font-mono mt-0.5" style={{ color: color ?? "#D1D4DC" }}>{value}</p>
      {sub && <p className="text-[10px] text-[#6b7280] mt-0.5">{sub}</p>}
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
    <div className="flex min-h-screen bg-[#0F1117] text-[#D1D4DC]">
      <Nav />
      <main className="flex-1 overflow-auto flex flex-col">
        <ActionBar />
        <div className="flex-1 px-4 py-4 md:px-8 md:py-6 space-y-4">
          <h1 className="text-lg font-bold text-white">Dashboard</h1>

          {loading && (
            <div className="animate-pulse space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{[...Array(8)].map((_, i) => <div key={i} className="h-16 rounded-xl bg-[#1A1D27]" />)}</div>
              <div className="h-40 rounded-xl bg-[#1A1D27]" />
            </div>
          )}

          {error && <div className="rounded-xl border border-red-800/50 bg-red-900/20 px-4 py-3 text-sm text-red-400">{error}</div>}

          {!loading && !error && data && (
            <>
              {/* Patrimônio */}
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                <h2 className="text-xs text-[#6b7280] uppercase tracking-wider mb-3">Patrimônio</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <KPI label="Total" value={brl(data.patrimonio_total)} color="#D1D4DC" />
                  <KPI label="Carteira Gerida" value={brl(data.patrimonio_gerida)} color={green} />
                  <KPI label="FUNCEF" value={brl(data.patrimonio_funcef)} color={amber} sub="excluída do IPS" />
                  <KPI label="Renda Variável" value={brl(data.patrimonio_rv)} color={purple} />
                </div>
                {data.var_dia != null && (
                  <div className="mt-3 flex flex-wrap gap-4 text-xs border-t border-[#2A2D3A] pt-3">
                    <span>Var. dia: <span className="font-mono font-bold" style={{ color: valColor(data.var_dia) }}>{brl(data.var_dia)}</span></span>
                    <span>Mercado: <span className="font-mono" style={{ color: valColor(data.var_mercado_dia) }}>{brl(data.var_mercado_dia)}</span></span>
                    {data.fluxo_dia != null && <span>Fluxo externo: <span className="font-mono text-[#6b7280]">{brl(data.fluxo_dia)}</span></span>}
                    <span>Var. % dia: <span className="font-mono font-bold" style={{ color: valColor(data.var_dia_pct) }}>{pct(data.var_dia_pct)}</span></span>
                  </div>
                )}
              </section>

              {/* Performance */}
              <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                <h2 className="text-xs text-[#6b7280] uppercase tracking-wider mb-3">Performance YTD</h2>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  <KPI label="TWR Gerida YTD" value={pct(data.twr_gerida_ytd)} color={valColor(data.twr_gerida_ytd)} />
                  <KPI label="TWR Total YTD" value={pct(data.twr_total_ytd)} color={valColor(data.twr_total_ytd)} />
                  <KPI label="CDI YTD" value={pct(data.cdi_ytd)} color="#D1D4DC" />
                  <KPI label="IBOV YTD" value={pct(data.ibov_ytd)} color={valColor(data.ibov_ytd)} />
                  <KPI label="S&P500 BRL YTD" value={pct(data.sp500_brl_ytd)} color={valColor(data.sp500_brl_ytd)} />
                  <KPI label="Excesso CDI" value={pct(data.excesso_cdi)} color={valColor(data.excesso_cdi)} />
                </div>
              </section>

              {/* Risco e Renda */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                  <h2 className="text-xs text-[#6b7280] uppercase tracking-wider mb-3">Métricas de Risco</h2>
                  <div className="grid grid-cols-2 gap-3">
                    <KPI label="Sharpe" value={fmt(data.sharpe, 2)} />
                    <KPI label="Vol. anualizada" value={pct(data.vol_anualizada, 2)} />
                    <KPI label="Drawdown máx." value={pct(data.drawdown_max, 2)} color={data.drawdown_max != null ? red : "#D1D4DC"}
                      sub={data.drawdown_max_data ?? undefined} />
                    <KPI label="Beta vs IBOV" value={fmt(data.beta_ibov, 2)} />
                  </div>
                </section>
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-4">
                  <h2 className="text-xs text-[#6b7280] uppercase tracking-wider mb-3">Renda Estimada</h2>
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
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                  <div className="px-5 py-3 border-b border-[#2A2D3A]">
                    <h2 className="text-sm font-semibold text-white">{data.n_alertas} Alerta{data.n_alertas !== 1 ? "s" : ""}</h2>
                  </div>
                  <div className="divide-y divide-[#2A2D3A]">
                    {data.alertas.map((a, i) => (
                      <div key={i} className="flex items-start gap-3 px-5 py-3">
                        <span className="text-xs font-bold shrink-0 mt-0.5" style={{ color: nivelCor[a.nivel] ?? amber }}>{a.nivel}</span>
                        <span className="text-xs font-semibold text-white shrink-0">{a.ativo}</span>
                        <span className="text-xs text-[#D1D4DC]">{a.mensagem}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Vencimentos RF */}
              {data.vencimentos_rf.length > 0 && (
                <section className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27]">
                  <div className="px-5 py-3 border-b border-[#2A2D3A]">
                    <h2 className="text-sm font-semibold text-white">Vencimentos Renda Fixa</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#2A2D3A] text-[10px] text-[#6b7280] uppercase">
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
                          <tr key={v.ticker} className="border-b border-[#2A2D3A]">
                            <td className="px-4 py-2 font-bold text-white">{v.ticker}</td>
                            <td className="px-4 py-2 text-[#6b7280]">{v.familia ?? "—"}</td>
                            <td className="px-4 py-2 text-right font-mono">{v.data_vencimento}</td>
                            <td className="px-4 py-2 text-right font-mono" style={{ color: nivelCor[v.alerta] ?? "#D1D4DC" }}>{v.dias_restantes}d</td>
                            <td className="px-4 py-2 text-right font-mono">{brl(v.valor_atual)}</td>
                            <td className="px-4 py-2 text-right font-bold" style={{ color: nivelCor[v.alerta] ?? "#D1D4DC" }}>{v.alerta}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {/* P&L Vendas */}
              <div className="rounded-xl border border-[#2A2D3A] bg-[#1A1D27] px-5 py-3 flex items-center justify-between">
                <span className="text-xs text-[#6b7280]">P&L realizado RV (vendas)</span>
                <span className="font-mono font-bold text-sm" style={{ color: valColor(data.pnl_vendas_rv) }}>{brl(data.pnl_vendas_rv, 2)}</span>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
