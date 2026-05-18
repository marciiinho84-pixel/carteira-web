"""
Página: Meta Patrimônio — projeção interativa com slider de TWR.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("🎯 Meta Patrimônio — R$ 3.000.000")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    meta_data = api.get("meta")
    if meta_data is None:
        return

    pat_atual = meta_data["patrimonio_atual"]
    twr_calc = meta_data["twr_anualizado"]

    # Permite que Configurações sobrescreva as premissas padrão da API
    _prem = st.session_state.get("premissas_meta", {})
    META = _prem.get("meta_valor") or meta_data["meta"]
    aporte_funcef_m = _prem.get("aporte_funcef_mensal", 6_392.0)
    aporte_marco = _prem.get("aporte_gerida_marco", 10_000.0)
    aporte_outubro = _prem.get("aporte_gerida_outubro", 10_000.0)
    aporte_anual = aporte_funcef_m * 12 + aporte_marco + aporte_outubro

    # ─── Slider de ajuste de TWR ──────────────────────────────────
    st.subheader("Parâmetros da Projeção")
    c_slider, c_info = st.columns([3, 1])
    with c_slider:
        twr_ajustado = st.slider(
            "TWR Anualizado estimado (%)",
            min_value=5.0,
            max_value=20.0,
            value=min(max(round(twr_calc * 100, 1), 5.0), 20.0),
            step=0.5,
            format="%.1f%%",
            help="Ajuste o retorno esperado para ver diferentes cenários.",
        )
        twr_slider = twr_ajustado / 100

    with c_info:
        fmt.card_kpi(
            "TWR calculado (atual)",
            fmt.pct(twr_calc),
            delta="baseado no histórico YTD",
            cor_delta="#4a9eff",
        )

    # ─── Recalcular projeção localmente com o slider ──────────────
    # (sem chamar a API — projeção é cálculo simples)
    pat = pat_atual
    projecao_custom = [{"ano": 2026, "patrimonio": pat, "pct_meta": pat / META}]
    for offset in range(1, 31):
        pat = pat * (1 + twr_slider) + aporte_anual
        projecao_custom.append({
            "ano": 2026 + offset,
            "patrimonio": pat,
            "pct_meta": pat / META,
        })
        if pat >= META * 1.1:
            break

    df_proj = pd.DataFrame(projecao_custom)
    ano_meta = next((r["ano"] for r in projecao_custom if r["patrimonio"] >= META), None)
    anos_restantes = (ano_meta - 2026) if ano_meta else "não atingida em 30 anos"

    st.divider()

    # ─── KPIs ─────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        fmt.card_kpi("Patrimônio Atual", fmt.moeda(pat_atual))
    with k2:
        fmt.card_kpi("Meta", fmt.moeda(META))
    with k3:
        falta = META - pat_atual
        fmt.card_kpi("Falta", fmt.moeda(falta))
    with k4:
        if ano_meta:
            fmt.card_kpi(
                "Ano estimado de atingimento",
                str(ano_meta),
                delta=f"{anos_restantes} anos",
                cor_delta="#2ecc71",
            )
        else:
            fmt.card_kpi("Ano estimado", "— (> 30 anos)", cor_delta="#e74c3c")

    st.divider()

    # ─── Gráfico de projeção ──────────────────────────────────────
    st.subheader("Projeção Patrimonial")

    fig = go.Figure()

    # Linha de projeção
    fig.add_trace(go.Scatter(
        x=df_proj["ano"],
        y=df_proj["patrimonio"],
        name="Patrimônio Projetado",
        line=dict(color="#4a9eff", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(74,158,255,0.1)",
        hovertemplate="<b>%{x}</b><br>R$ %{y:,.0f}<br>%{customdata:.0%} da meta<extra></extra>",
        customdata=df_proj["pct_meta"],
    ))

    # Linha da meta
    fig.add_hline(
        y=META,
        line_dash="dash",
        line_color="#2ecc71",
        line_width=2,
        annotation_text=f"Meta: R$ {META:,.0f}",
        annotation_position="right",
        annotation_font_color="#2ecc71",
    )

    # Ponto de atingimento
    if ano_meta:
        pat_no_ano = next(r["patrimonio"] for r in projecao_custom if r["ano"] == ano_meta)
        fig.add_trace(go.Scatter(
            x=[ano_meta],
            y=[pat_no_ano],
            mode="markers+text",
            marker=dict(color="#2ecc71", size=14, symbol="star"),
            text=[f"  {ano_meta}"],
            textposition="middle right",
            textfont=dict(color="#2ecc71", size=13),
            name="Meta atingida",
            hovertemplate=f"<b>Meta atingida!</b><br>{ano_meta}<br>R$ {pat_no_ano:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,22,36,0.8)",
        font_color="white",
        xaxis=dict(gridcolor="rgba(255,255,255,0.08)", title="Ano", dtick=1),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.08)",
            title="Patrimônio (R$)",
            tickformat=",.0f",
        ),
        hovermode="x",
        legend=dict(orientation="h", y=1.05),
        margin=dict(t=10, b=40, l=80, r=120),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ─── Tabela de projeção ───────────────────────────────────────
    st.subheader("Tabela de Projeção Ano a Ano")
    rows_tab = []
    for r in projecao_custom:
        atingiu = "⭐ META" if r["patrimonio"] >= META and r["ano"] == ano_meta else (
            "✓ acima" if r["patrimonio"] >= META else ""
        )
        rows_tab.append({
            "Ano": r["ano"],
            "Patrimônio": fmt.moeda(r["patrimonio"]),
            "% da Meta": fmt.pct(r["pct_meta"], casas=0),
            "": atingiu,
        })
    df_tab = pd.DataFrame(rows_tab)

    def _destacar_meta(row):
        if row[""] == "⭐ META":
            return ["background-color: rgba(255, 215, 0, 0.25); font-weight: bold"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_tab.style.apply(_destacar_meta, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"Premissas: TWR = {twr_ajustado:.1f}% a.a. | "
        f"Meta = {fmt.moeda(META)} | "
        f"Aporte anual = {fmt.moeda(aporte_anual)} "
        f"(FUNCEF {fmt.moeda(aporte_funcef_m)}/mês + "
        f"março {fmt.moeda(aporte_marco)} + outubro {fmt.moeda(aporte_outubro)})"
    )
