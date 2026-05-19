"""
Página: Carteira RV — Estação operacional de Renda Variável.

4 seções:
  1. Caixa operacional (KPIs + alerta)
  2. Calendário D+2 (tabela de liquidações próximas)
  3. Distribuição setorial (treemap Plotly)
  4. Performance RV vs IBOV / S&P500 BRL
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("📊 Carteira RV — Estação Operacional")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira. Verifique se a API está rodando.")
        return

    rv = api.get("carteira-rv")
    if rv is None:
        return

    # ─── Seção 1: Caixa Operacional ──────────────────────────────
    st.subheader("1. Caixa Operacional")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        fmt.card_kpi("Caixa Hoje (FIC FUNC)", fmt.moeda(rv["caixa_atual"]))
    with c2:
        fmt.card_kpi(
            "Entrando (5 d.u.)",
            fmt.moeda(rv["entrando_5d"]),
            delta="+caixa",
            cor_delta="#2ecc71",
        )
    with c3:
        fmt.card_kpi(
            "Saindo (5 d.u.)",
            fmt.moeda(rv["saindo_5d"]),
            delta="-caixa",
            cor_delta="#e74c3c",
        )
    with c4:
        saldo_proj = rv["saldo_projetado"]
        cor = "#2ecc71" if saldo_proj >= 0 else "#e74c3c"
        fmt.card_kpi(
            "Saldo Projetado Pós-D+2",
            fmt.moeda(saldo_proj),
            cor_delta=cor,
        )

    if saldo_proj < 0:
        st.error(
            f"⚠️ **ATENÇÃO:** caixa projetado fica em {fmt.moeda(saldo_proj)} após D+2. "
            f"Precisa resgatar pelo menos {fmt.moeda(abs(saldo_proj))} do FIC FUNC."
        )
    elif saldo_proj < rv["caixa_atual"] * 0.3:
        st.warning(
            f"ℹ️ Caixa baixo após liquidações: {fmt.moeda(saldo_proj)}. "
            "Avaliar resgate preventivo."
        )
    else:
        st.success(
            f"✓ Caixa suficiente para honrar liquidações da semana "
            f"({fmt.moeda(saldo_proj)} disponível)."
        )

    st.divider()

    # ─── Seção 2: Calendário D+2 / D+1 ──────────────────────────
    st.subheader("2. Calendário de Liquidações D+2 / D+1")
    pendentes = rv.get("pendentes", [])
    if pendentes:
        rows = []
        for p in pendentes:
            impacto = p["impacto"]
            cor_imp = "🟢" if impacto > 0 else "🔴"
            prazo = p.get("prazo", "D+2")
            rows.append({
                "Liquidação": p["liquidacao"],
                "Trade": p["trade"],
                "Op": p["tipo"],
                "Ativo": p["ativo"],
                "Qtd": p.get("qtd", "—"),
                "Valor": fmt.moeda(p["valor"]),
                "Impacto": f"{cor_imp} {fmt.moeda(abs(impacto))}  [{prazo}]",
                "Saldo Proj.": fmt.moeda(p["saldo_projetado"]),
            })
        df_pend = pd.DataFrame(rows)
        st.dataframe(df_pend, use_container_width=True, hide_index=True)
    else:
        st.info("✓ Nenhuma operação pendente nos próximos 5 dias úteis.")

    st.divider()

    # ─── Seção 3: Distribuição Setorial ──────────────────────────
    st.subheader("3. Distribuição Setorial — Carteira RV")
    setores = rv.get("setores", [])
    if setores:
        df_set = pd.DataFrame(setores)
        col_tree, col_tab = st.columns([3, 2])
        with col_tree:
            fig = px.treemap(
                df_set,
                path=["setor"],
                values="valor",
                custom_data=["pct_rv", "n_ativos", "ativos"],
                color="valor",
                color_continuous_scale=px.colors.sequential.Blues,
                title="Treemap Setorial (valor de mercado)",
            )
            fig.update_traces(
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Valor: R$ %{value:,.0f}<br>"
                    "% RV: %{customdata[0]:.1%}<br>"
                    "Ativos: %{customdata[1]}<br>"
                    "%{customdata[2]}"
                    "<extra></extra>"
                ),
                texttemplate="<b>%{label}</b><br>%{customdata[0]:.1%}",
            )
            fig.update_layout(
                margin=dict(t=40, l=0, r=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="white",
                coloraxis_showscale=False,
                height=max(300, 420),
            )
            st.plotly_chart(fig, use_container_width=True, config={'responsive': True})

        with col_tab:
            df_tab = df_set[["setor", "valor", "pct_rv", "n_ativos"]].copy()
            df_tab["valor"] = df_tab["valor"].apply(fmt.moeda)
            df_tab["pct_rv"] = df_tab["pct_rv"].apply(lambda v: fmt.pct(v, casas=1))
            df_tab.columns = ["Setor", "Valor", "% RV", "# Ativos"]
            st.dataframe(df_tab, use_container_width=True, hide_index=True, height=420)

    st.divider()

    # ─── Seção 4: Performance RV ──────────────────────────────────
    st.subheader("4. Performance da RV vs Benchmarks")
    twr_rv = rv.get("twr_rv", 0)
    ibov = rv.get("ibov_ytd", 0)
    sp500_brl = rv.get("sp500_brl_ytd", 0)

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        cor = "#2ecc71" if twr_rv >= 0 else "#e74c3c"
        fmt.card_kpi("TWR Carteira RV (YTD)", fmt.pct(twr_rv), cor_delta=cor)
    with mc2:
        cor = "#2ecc71" if ibov >= 0 else "#e74c3c"
        fmt.card_kpi("IBOV (YTD)", fmt.pct(ibov), delta="Benchmark Brasil", cor_delta=cor)
    with mc3:
        cor = "#2ecc71" if sp500_brl >= 0 else "#e74c3c"
        fmt.card_kpi("S&P 500 BRL (YTD)", fmt.pct(sp500_brl), delta="Benchmark Internacional", cor_delta=cor)

    # Barra de comparação
    fig_bar = go.Figure(go.Bar(
        x=["TWR RV", "IBOV", "S&P500 BRL"],
        y=[twr_rv * 100, ibov * 100, sp500_brl * 100],
        marker_color=[
            "#2ecc71" if twr_rv >= 0 else "#e74c3c",
            "#3498db",
            "#9b59b6",
        ],
        text=[fmt.pct(twr_rv), fmt.pct(ibov), fmt.pct(sp500_brl)],
        textposition="outside",
    ))
    fig_bar.update_layout(
        title="Retorno Acumulado YTD (%)",
        yaxis_ticksuffix="%",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="white",
        height=280,
        margin=dict(t=40, b=10),
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={'responsive': True})
