"""
Página: Evolução — gráfico de patrimônio + tabela diária.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("📈 Evolução Patrimonial")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    evo_data = api.get("evolucao")
    if not evo_data:
        st.info("Sem dados de evolução.")
        return

    df = pd.DataFrame(evo_data)
    df["data"] = pd.to_datetime(df["data"])

    # ─── Filtro de período ────────────────────────────────────────
    fc1, fc2 = st.columns(2)
    with fc1:
        data_ini = st.date_input("De", value=df["data"].min().date(), format="DD/MM/YYYY")
    with fc2:
        data_fim = st.date_input("Até", value=df["data"].max().date(), format="DD/MM/YYYY")

    df_f = df[(df["data"].dt.date >= data_ini) & (df["data"].dt.date <= data_fim)]

    if df_f.empty:
        st.warning("Nenhum dado no período selecionado.")
        return

    st.divider()

    # ─── KPIs do período ─────────────────────────────────────────
    primeiro = df_f.iloc[0]
    ultimo = df_f.iloc[-1]
    variacao_pat = ultimo["patrimonio_total"] - primeiro["patrimonio_total"]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        fmt.card_kpi("Patrimônio Final", fmt.moeda(ultimo["patrimonio_total"]))
    with k2:
        cor = "#2ecc71" if variacao_pat >= 0 else "#e74c3c"
        fmt.card_kpi("Variação no Período", fmt.moeda(variacao_pat, sinal=True), cor_delta=cor)
    with k3:
        fmt.card_kpi("TWR Gerida (período)", fmt.pct(ultimo["twr_gerida"]))
    with k4:
        st.metric("Dias úteis", len(df_f))

    st.divider()

    # ─── Gráfico duplo: Patrimônio + TWR ─────────────────────────
    st.subheader("Patrimônio e TWR")
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        row_heights=[0.6, 0.4],
        subplot_titles=("Patrimônio (R$)", "TWR vs Benchmarks (%)"),
        vertical_spacing=0.08,
    )

    # Total + FUNCEF — eixo Y esquerdo
    fig.add_trace(go.Scatter(
        x=df_f["data"], y=df_f["patrimonio_total"],
        name="Total", line=dict(color="#4a9eff", width=2),
        hovertemplate="Total: R$ %{y:,.0f}<extra></extra>",
    ), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df_f["data"], y=df_f["patrimonio_funcef"],
        name="FUNCEF", line=dict(color="#f39c12", width=1.5, dash="dash"),
        hovertemplate="FUNCEF: R$ %{y:,.0f}<extra></extra>",
    ), row=1, col=1, secondary_y=False)

    # Gerida — eixo Y direito (escala própria)
    fig.add_trace(go.Scatter(
        x=df_f["data"], y=df_f["patrimonio_gerida"],
        name="Gerida ▶", line=dict(color="#2ecc71", width=1.5, dash="dot"),
        hovertemplate="Gerida: R$ %{y:,.0f}<extra></extra>",
    ), row=1, col=1, secondary_y=True)

    # Caixa (derivado) — eixo Y direito, junto com a Gerida
    if "caixa" in df_f.columns:
        fig.add_trace(go.Scatter(
            x=df_f["data"], y=df_f["caixa"],
            name="Caixa ▶", line=dict(color="#95a5a6", width=1.5, dash="dot"),
            hovertemplate="Caixa: R$ %{y:,.0f}<extra></extra>",
        ), row=1, col=1, secondary_y=True)

    # TWR
    for col, nome, cor, dash_ in [
        ("twr_gerida", "TWR Gerida", "#4a9eff", "solid"),
        ("cdi_acum", "CDI", "#2ecc71", "dash"),
        ("ibov_acum", "IBOV", "#f39c12", "dashdot"),
    ]:
        fig.add_trace(go.Scatter(
            x=df_f["data"], y=df_f[col] * 100,
            name=nome, line=dict(color=cor, dash=dash_, width=1.5),
            showlegend=True,
            hovertemplate=f"{nome}: %{{y:+.2f}}%<extra></extra>",
        ), row=2, col=1)

    _pt = fmt.plotly_theme()
    _gc = "rgba(255,255,255,0.08)" if fmt._dark() else "rgba(0,0,0,0.10)"
    fig.update_layout(
        height=580,
        **_pt,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.05),
        margin=dict(t=40, b=20, l=80, r=80),
    )
    for i in range(1, 3):
        fig.update_xaxes(gridcolor=_gc, row=i, col=1)
        fig.update_yaxes(gridcolor=_gc, row=i, col=1)
    fig.update_yaxes(tickformat=",.0f", title_text="Total / FUNCEF (R$)",
                     row=1, col=1, secondary_y=False)
    fig.update_yaxes(tickformat=",.0f", title_text="Gerida (R$)",
                     row=1, col=1, secondary_y=True, gridcolor=_gc)
    fig.update_yaxes(ticksuffix="%", row=2, col=1)

    st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

    st.divider()

    # ─── Gráfico Underwater (drawdown) ───────────────────────────
    if "drawdown" in df_f.columns and df_f["drawdown"].notna().any():
        st.subheader("Drawdown (Underwater)")
        dd_min = df_f["drawdown"].min()
        fig_dd = go.Figure(go.Scatter(
            x=df_f["data"],
            y=df_f["drawdown"] * 100,
            fill="tozeroy",
            fillcolor="rgba(231, 76, 60, 0.20)",
            line=dict(color="#e74c3c", width=1.5),
            hovertemplate="Drawdown: %{y:+.2f}%<extra></extra>",
            name="Drawdown",
        ))
        fig_dd.add_hline(y=0, line_color="rgba(150,150,150,0.4)", line_width=1)
        fig_dd.update_layout(
            height=220,
            **fmt.plotly_theme(),
            hovermode="x unified",
            showlegend=False,
            margin=dict(t=10, b=30, l=60, r=20),
            xaxis=dict(gridcolor=_gc),
            yaxis=dict(gridcolor=_gc, ticksuffix="%", title="Drawdown (%)"),
        )
        st.plotly_chart(fig_dd, use_container_width=True, config={'responsive': True})
        if dd_min < 0:
            idx_dd = df_f["drawdown"].idxmin()
            st.caption(
                f"Drawdown máximo do período: **{dd_min * 100:+.2f}%** "
                f"(em {df_f.loc[idx_dd, 'data'].strftime('%d/%m/%Y')})"
            )
        st.divider()

    # ─── Tabela diária (expansível) ───────────────────────────────
    with st.expander("📊 Tabela Diária Completa", expanded=False):
        rows_tab = []
        for _, r in df_f.iterrows():
            rows_tab.append({
                "Data": r["data"].strftime("%d/%m/%Y"),
                "Patrim. Total": fmt.moeda(r["patrimonio_total"]),
                "Gerida": fmt.moeda(r["patrimonio_gerida"]),
                "FUNCEF": fmt.moeda(r["patrimonio_funcef"]),
                "RV": fmt.moeda(r["patrimonio_rv"]),
                "Caixa": fmt.moeda(r.get("caixa", 0.0)),
                "TWR Gerida": fmt.pct(r["twr_gerida"]),
                "TWR Total": fmt.pct(r["twr_total"]),
                "CDI": fmt.pct(r["cdi_acum"]),
                "IBOV": fmt.pct(r["ibov_acum"]),
            })
        df_evo_tab = pd.DataFrame(rows_tab)
        st.dataframe(df_evo_tab, use_container_width=True, hide_index=True, height=400)

        st.caption("Exportar série histórica:")
        # Export com valores numéricos (não formatados)
        if "caixa" not in df_f.columns:
            df_f["caixa"] = 0.0
        df_evo_export = df_f[["data","patrimonio_total","patrimonio_gerida",
                               "patrimonio_funcef","patrimonio_rv","caixa",
                               "twr_gerida","twr_total","cdi_acum","ibov_acum"]].copy()
        df_evo_export["data"] = df_evo_export["data"].dt.strftime("%d/%m/%Y")
        df_evo_export.columns = ["Data","Patrim. Total","Gerida","FUNCEF","RV","Caixa",
                                  "TWR Gerida","TWR Total","CDI","IBOV"]
        fmt.botoes_exportar(df_evo_export, "evolucao", key="evo")
