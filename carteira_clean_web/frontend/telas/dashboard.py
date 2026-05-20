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

        _gc = "rgba(255,255,255,0.08)" if fmt._dark() else "rgba(0,0,0,0.10)"
        fig.add_hline(y=0, line_dash="solid", line_color="rgba(150,150,150,0.3)", line_width=1)
        fig.update_layout(
            height=420,
            **fmt.plotly_theme(),
            xaxis=dict(gridcolor=_gc, title=""),
            yaxis=dict(gridcolor=_gc, title="Retorno Acumulado (%)", ticksuffix="%"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(t=10, b=40, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

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

    # ─── Métricas de risco e retorno ─────────────────────────────
    st.subheader("Risco e Retorno")
    r1, r2, r3, r4 = st.columns(4)

    with r1:
        dd = dash.get("drawdown_max")
        dd_data = dash.get("drawdown_max_data")
        if dd is not None:
            dt_str = pd.to_datetime(dd_data).strftime("%d/%m/%Y") if dd_data else ""
            cor_dd = "#e74c3c"
            fmt.card_kpi(
                "Drawdown Máx. YTD",
                fmt.pct(dd, casas=2),
                delta=dt_str,
                cor_delta="#aaa",
            )
        else:
            fmt.card_kpi("Drawdown Máx. YTD", "—")

    with r2:
        vol = dash.get("vol_anualizada")
        fmt.card_kpi(
            "Volatilidade a.a.",
            fmt.pct(vol, casas=1) if vol is not None else "—",
            delta="IBOV ~25% típico",
            cor_delta="#aaa",
        )

    with r3:
        beta = dash.get("beta_ibov")
        if beta is not None:
            if beta < 0.5:
                interp = "Defensiva"
            elif beta < 0.8:
                interp = "Moderada"
            elif beta < 1.2:
                interp = "Alinhada"
            else:
                interp = "Agressiva"
            fmt.card_kpi("Beta vs IBOV", f"{beta:.2f}", delta=interp, cor_delta="#aaa")
        else:
            fmt.card_kpi("Beta vs IBOV", "—", delta="< 20 obs.", cor_delta="#aaa")

    with r4:
        yield_12m = dash.get("yield_12m")
        yield_12m_gerida = dash.get("yield_12m_gerida")
        renda_anual = dash.get("renda_anual_est", 0) or 0
        if yield_12m is not None:
            renda_mes = renda_anual / 12
            fmt.card_kpi(
                "Yield Projetado 12m",
                fmt.pct(yield_12m, casas=2),
                delta=f"Gerida: {fmt.pct(yield_12m_gerida, casas=2)} · ~{fmt.moeda(renda_mes)}/mês",
                cor_delta="#2ecc71",
            )
        else:
            fmt.card_kpi("Yield Projetado 12m", "—")

    st.divider()

    # ─── Vencimentos RF ───────────────────────────────────────────
    venc_rf = dash.get("vencimentos_rf", [])
    proventos_30d = dash.get("proventos_30d", 0) or 0
    if venc_rf or proventos_30d > 0:
        st.subheader("Renda Fixa & Proventos")
        vc1, vc2 = st.columns(2)

        with vc1:
            if venc_rf:
                linhas = []
                for v in venc_rf:
                    anos = v["dias_restantes"] // 365
                    dias_r = v["dias_restantes"] % 365
                    periodo_str = f"{anos}a {dias_r}d" if anos > 0 else f"{v['dias_restantes']}d"
                    dt_fmt = pd.to_datetime(v["data_vencimento"]).strftime("%d/%m/%Y")
                    val_str = fmt.moeda(v["valor_atual"]) if v.get("valor_atual") else "—"
                    cor_al = "#e74c3c" if v["alerta"] == "CRITICO" else (
                        "#f39c12" if v["alerta"] == "ATENCAO" else "#2ecc71"
                    )
                    linhas.append(
                        f"<tr><td><b>{v['ticker']}</b></td>"
                        f"<td style='color:{cor_al}'>{periodo_str}</td>"
                        f"<td>{dt_fmt}</td>"
                        f"<td>{val_str}</td></tr>"
                    )
                st.markdown(
                    "<div style='background:#1e2130;padding:14px 18px;border-radius:10px;"
                    "border-left:4px solid #4a9eff;'>"
                    "<div style='color:#aaa;font-size:0.78rem;text-transform:uppercase;"
                    "letter-spacing:0.05em;margin-bottom:8px'>PRÓXIMOS VENCIMENTOS RF</div>"
                    "<table style='width:100%;font-size:0.9rem;border-collapse:collapse'>"
                    "<tr style='color:#888;font-size:0.75rem'>"
                    "<th align='left'>Ativo</th><th align='left'>Prazo</th>"
                    "<th align='left'>Vencimento</th><th align='left'>Valor Bruto</th></tr>"
                    + "".join(linhas) + "</table></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.info("Nenhum ativo RF com vencimento cadastrado.")

        with vc2:
            fmt.card_kpi(
                "Renda estimada (30 dias)",
                fmt.moeda(proventos_30d),
                delta="Projeção histórica — sem garantia",
                cor_delta="#aaa",
            )

        st.divider()

    # ─── Diário: decisões aguardando revisão ─────────────────────
    pendentes_dec = api.get("decisoes/pendentes") or []
    if pendentes_dec:
        n = len(pendentes_dec)
        st.info(
            f"📓 **{n} decisão/ões aguardam revisão no Diário** — "
            f"mais antiga: {pendentes_dec[0].get('ativo', '')} "
            f"({pendentes_dec[0].get('acao', '')}) prevista para "
            f"{pendentes_dec[0].get('revisao_em', '?')}"
        )

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
