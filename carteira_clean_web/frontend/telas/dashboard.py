"""
Página: Dashboard — KPIs executivos + gráfico TWR vs benchmarks.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("🏠 Dashboard")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    dash = api.get("dashboard")
    evo_data = api.get("evolucao")
    ir_data = api.get("ir-mensal") or []

    if dash is None:
        return

    # ─── Alerta DARF (se houver IR a pagar este mês) ─────────────
    if ir_data:
        mes_atual = pd.Timestamp.today().strftime("%Y-%m")
        ir_mes = next((r for r in ir_data if r["mes"] == mes_atual and r["gera_darf"]), None)
        if ir_mes:
            venc = ir_mes.get("darf_vencimento", "?")
            venc_fmt = f"{venc[8:10]}/{venc[5:7]}" if venc and len(venc) >= 10 else venc
            st.error(
                f"🔴 **DARF Código 6015** — "
                f"IR sobre RV: **{fmt.moeda(ir_mes['ir_devido'])}** — "
                f"Vence em **{venc_fmt}** (último dia útil do mês seguinte)"
            )

    # ─── Variação no dia (KPI destaque) ──────────────────────────
    var_dia = dash.get("var_dia")
    var_dia_pct = dash.get("var_dia_pct")
    if var_dia is not None:
        seta = "↑" if var_dia >= 0 else "↓"
        cor_var = "#2ecc71" if var_dia >= 0 else "#e74c3c"
        var_texto = f"{seta} {fmt.moeda(abs(var_dia), sinal=False)} ({fmt.pct(abs(var_dia_pct), casas=2)})"
        st.markdown(
            f"<div style='background: linear-gradient(135deg,rgba(30,34,50,0.9),rgba(20,24,38,0.9));"
            f"border-left:4px solid {cor_var};padding:12px 20px;border-radius:8px;margin-bottom:16px;'>"
            f"<span style='color:#aaa;font-size:0.85em;'>VARIAÇÃO HOJE (D-1 → D)</span><br>"
            f"<span style='color:{cor_var};font-size:1.5em;font-weight:700;'>{var_texto}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("ℹ️ Variação diária indisponível (modo sem preços de mercado ou 1º cálculo).")

    # ─── KPIs principais ─────────────────────────────────────────
    st.subheader("Patrimônio & Performance")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        fmt.card_kpi("Patrimônio Total", fmt.moeda(dash["patrimonio_total"]))
    with c2:
        cor = "#2ecc71" if dash["twr_gerida_ytd"] >= 0 else "#e74c3c"
        fmt.card_kpi(
            "TWR Gerida (YTD)",
            fmt.pct(dash["twr_gerida_ytd"]),
            delta=f"CDI: {fmt.pct(dash['cdi_ytd'])}",
            cor_delta=cor,
        )
    with c3:
        excesso = dash["excesso_cdi"]
        cor = "#2ecc71" if excesso >= 0 else "#e74c3c"
        fmt.card_kpi(
            "Excesso s/ CDI",
            fmt.pct(excesso, sinal=True),
            cor_delta=cor,
        )
    with c4:
        fmt.card_kpi("Sharpe", f"{dash['sharpe']:.2f}")
    with c5:
        pnl = dash["pnl_vendas_rv"]
        cor = "#2ecc71" if pnl >= 0 else "#e74c3c"
        fmt.card_kpi("P&L Vendas RV", fmt.moeda(pnl, sinal=True), cor_delta=cor)

    st.divider()

    # ─── KPIs secundários ────────────────────────────────────────
    st.subheader("Composição do Patrimônio")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        fmt.card_kpi("Carteira Gerida", fmt.moeda(dash["patrimonio_gerida"]))
    with d2:
        fmt.card_kpi("FUNCEF", fmt.moeda(dash["patrimonio_funcef"]))
    with d3:
        fmt.card_kpi("Sub-portfolio RV", fmt.moeda(dash["patrimonio_rv"]))
    with d4:
        pct_funcef = dash["patrimonio_funcef"] / dash["patrimonio_total"] if dash["patrimonio_total"] > 0 else 0
        fmt.card_kpi("% FUNCEF", fmt.pct(pct_funcef, casas=1))

    st.divider()

    # ─── Gráfico TWR vs Benchmarks ────────────────────────────────
    st.subheader("Evolução TWR vs Benchmarks (YTD)")

    if evo_data:
        df = pd.DataFrame(evo_data)
        df["data"] = pd.to_datetime(df["data"])

        fig = go.Figure()

        traces = [
            ("twr_gerida", "TWR Gerida", "#1a5fad", "solid", 2.5),
            ("twr_rv", "TWR RV", "#4a9eff", "dot", 1.8),
            ("cdi_acum", "CDI", "#2ecc71", "dash", 1.5),
            ("ibov_acum", "IBOV", "#f39c12", "dashdot", 1.5),
            ("sp500_brl_acum", "S&P500 BRL", "#95a5a6", "longdash", 1.5),
        ]

        for col, nome, cor, dash_style, width in traces:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["data"],
                    y=df[col] * 100,
                    name=nome,
                    line=dict(color=cor, dash=dash_style, width=width),
                    hovertemplate=f"<b>{nome}</b><br>%{{x|%d/%m/%Y}}<br>%{{y:+.2f}}%<extra></extra>",
                ))

        fig.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.2)", line_width=1)
        fig.update_layout(
            height=420,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,22,36,0.8)",
            font_color="white",
            xaxis=dict(gridcolor="rgba(255,255,255,0.08)", title=""),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                title="Retorno Acumulado (%)",
                ticksuffix="%",
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="right", x=1,
            ),
            hovermode="x unified",
            margin=dict(t=10, b=40, l=60, r=20),
        )
        st.plotly_chart(fig, width='stretch')

    st.divider()

    # ─── Benchmarks lado a lado ───────────────────────────────────
    st.subheader("Benchmarks YTD")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        fmt.card_kpi("CDI", fmt.pct(dash["cdi_ytd"]))
    with b2:
        cor = "#2ecc71" if dash["ibov_ytd"] >= 0 else "#e74c3c"
        fmt.card_kpi("IBOV", fmt.pct(dash["ibov_ytd"]), cor_delta=cor)
    with b3:
        cor = "#2ecc71" if dash["sp500_brl_ytd"] >= 0 else "#e74c3c"
        fmt.card_kpi("S&P500 BRL", fmt.pct(dash["sp500_brl_ytd"]), cor_delta=cor)
    with b4:
        twr_rv = dash.get("twr_rv_ytd", 0)
        cor = "#2ecc71" if twr_rv >= 0 else "#e74c3c"
        fmt.card_kpi("TWR RV", fmt.pct(twr_rv), cor_delta=cor)

    st.divider()

    # ─── Alertas ativos ───────────────────────────────────────────
    alertas = dash.get("alertas", [])
    if alertas:
        st.subheader(f"🔔 Alertas ({len(alertas)})")
        for a in alertas:
            nivel = a["nivel"]
            msg = f"**{a['ativo']}**: {a['mensagem']}"
            if nivel == "ERRO":
                st.error(f"🔴 {msg}")
            elif nivel == "AVISO":
                st.warning(f"🟡 {msg}")
            else:
                st.info(f"🔵 {msg}")
