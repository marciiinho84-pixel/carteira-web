"""
Página: Vendas Realizadas — relatório com P&L por operação.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("💰 Vendas Realizadas")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    vendas = api.get("vendas")
    if vendas is None:
        return

    if not vendas:
        st.info("Nenhuma venda de RV registrada.")
        return

    df = pd.DataFrame(vendas)
    df["data"] = pd.to_datetime(df["data"])

    # ─── KPIs ─────────────────────────────────────────────────────
    total_pnl = df["pnl"].sum()
    total_recebido = df["valor_recebido"].sum()
    n_operacoes = len(df)
    pnl_medio = df["pnl_pct"].mean()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        cor = "normal" if total_pnl >= 0 else "inverse"
        st.metric("P&L Total Realizado", fmt.moeda(total_pnl, sinal=True), delta_color=cor)
    with k2:
        st.metric("Total Recebido", fmt.moeda(total_recebido))
    with k3:
        st.metric("Operações", n_operacoes)
    with k4:
        st.metric("P&L Médio (%)", f"{'+' if pnl_medio >= 0 else ''}{pnl_medio:.2f}%")

    st.divider()

    # ─── Gráfico de barras P&L por venda ──────────────────────────
    st.subheader("P&L por Operação")
    fig = go.Figure(go.Bar(
        x=[f"{row['ticker']}<br>{pd.Timestamp(row['data']).strftime('%d/%m')}"
           for _, row in df.iterrows()],
        y=df["pnl"],
        marker_color=["#2ecc71" if v >= 0 else "#e74c3c" for v in df["pnl"]],
        text=[fmt.moeda(v, sinal=True) for v in df["pnl"]],
        textposition="outside",
        hovertemplate=(
            "<b>%{x}</b><br>"
            "P&L: R$ %{y:+,.2f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,22,36,0.8)",
        font_color="white",
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="P&L (R$)"),
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        showlegend=False,
        margin=dict(t=20, b=40),
    )
    fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_width=1)
    st.plotly_chart(fig, width='stretch')

    st.divider()

    # ─── Tabela detalhada ─────────────────────────────────────────
    st.subheader("Detalhe das Vendas")

    rows_tab = []
    for _, r in df.sort_values("data").iterrows():
        rows_tab.append({
            "Data": r["data"].strftime("%d/%m/%Y"),
            "Ticker": r["ticker"],
            "Qtd Vendida": f"{r['qtd_vendida']:,.4f}",
            "Preço Venda": fmt.moeda(r["preco_venda"]) if r["preco_venda"] else "—",
            "Custo Médio": fmt.moeda(r["custo_medio"]),
            "Valor Recebido": fmt.moeda(r["valor_recebido"]),
            "P&L R$": fmt.moeda(r["pnl"], sinal=True),
            "P&L %": fmt.pct(r["pnl_pct"] / 100),
        })

    df_tab = pd.DataFrame(rows_tab)
    st.dataframe(df_tab, width='stretch', hide_index=True)

    # Totalizador
    st.markdown(
        f"**Total P&L: {fmt.moeda(total_pnl, sinal=True)}** — "
        f"{n_operacoes} operações — "
        f"Recebido: {fmt.moeda(total_recebido)}"
    )
