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

    # ─── Painel IR Mensal ─────────────────────────────────────────
    ir_data = api.get("ir-mensal") or []
    if ir_data:
        st.subheader("📊 Imposto de Renda — Estimativa Mensal")
        mes_atual = pd.Timestamp.today().strftime("%Y-%m")
        ir_mes_atual = next((r for r in ir_data if r["mes"] == mes_atual), None) or ir_data[-1]

        mes_fmt = f"{ir_mes_atual['mes'][5:7]}/{ir_mes_atual['mes'][:4]}"
        status_ir = ir_mes_atual["status"]
        cor_box = "#2ecc71" if status_ir == "ISENTO" else "#e74c3c" if ir_mes_atual["gera_darf"] else "#f39c12"
        icone = "✓" if status_ir == "ISENTO" else "⚠"

        st.markdown(
            f"<div style='border:1px solid {cor_box};border-left:5px solid {cor_box};"
            f"padding:16px;border-radius:8px;margin-bottom:16px;'>"
            f"<b style='font-size:1.1em;'>IMPOSTO DE RENDA — {mes_fmt.upper()}</b><br><br>"
            f"Volume vendas:&nbsp;&nbsp;&nbsp;&nbsp;<b>{fmt.moeda(ir_mes_atual['volume_vendas'])}</b><br>"
            f"Status:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b style='color:{cor_box};'>{status_ir} {icone}</b><br>"
            f"IR a pagar:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{fmt.moeda(ir_mes_atual['ir_devido'])}</b><br>"
            f"Prejuízo acum.:&nbsp;&nbsp;<b>{fmt.moeda(ir_mes_atual['prejudizo_acumulado'])}</b>"
            + (f"<br>DARF Cód. 6015 — vence <b>{ir_mes_atual['darf_vencimento'][8:10]}/{ir_mes_atual['darf_vencimento'][5:7]}</b>" if ir_mes_atual["gera_darf"] else "")
            + "</div>",
            unsafe_allow_html=True,
        )

        st.subheader("Histórico Mensal de IR")
        rows_ir = []
        for r in ir_data:
            rows_ir.append({
                "Mês": f"{r['mes'][5:7]}/{r['mes'][:4]}",
                "Ativos": ", ".join(r.get("tickers_vendidos", [])),
                "Volume Vendas": fmt.moeda(r["volume_vendas"]),
                "Lucro Bruto": fmt.moeda(r["lucro_bruto"]),
                "Compensado": fmt.moeda(r["prejudizo_compensado"]),
                "IR Estimado": fmt.moeda(r["ir_devido"]),
                "Status": r["status"],
                "DARF Vence": (
                    f"{r['darf_vencimento'][8:10]}/{r['darf_vencimento'][5:7]}"
                    if r.get("darf_vencimento") else "—"
                ),
            })
        df_ir = pd.DataFrame(rows_ir)
        st.dataframe(df_ir, hide_index=True, use_container_width=True)
        st.divider()


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
    st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

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
    st.dataframe(df_tab, use_container_width=True, hide_index=True)

    # Totalizador
    st.markdown(
        f"**Total P&L: {fmt.moeda(total_pnl, sinal=True)}** — "
        f"{n_operacoes} operações — "
        f"Recebido: {fmt.moeda(total_recebido)}"
    )

    # ─── Exportação ───────────────────────────────────────────────
    st.caption("Exportar tabela de vendas:")
    df_export_v = df[["data","ticker","qtd_vendida","preco_venda",
                       "custo_medio","valor_recebido","pnl","pnl_pct"]].copy()
    df_export_v["data"] = df_export_v["data"].dt.strftime("%d/%m/%Y")
    df_export_v.columns = ["Data","Ticker","Qtd Vendida","Preço Venda",
                            "Custo Médio","Valor Recebido","P&L R$","P&L %"]
    fmt.botoes_exportar(df_export_v, "vendas", key="vnd")
