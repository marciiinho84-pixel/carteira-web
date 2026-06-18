"""
Página: Risco ex-ante — exposição por bloco/classe, liquidez e orientação ao Assistente (Fatia 6).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("⚠️ Risco ex-ante")
    st.caption(
        "Análise completa disponível via 🤖 Assistente. "
        "Pergunte: **'análise de risco da carteira'**"
    )

    st.info(
        "Esta tela exibe indicadores básicos de exposição calculados localmente. "
        "Para análise completa de drawdown, stress e liquidez, use o Assistente."
    )

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    posicoes = api.get("posicoes") or []

    if not posicoes:
        st.info(
            "Nenhuma posição disponível. Após importar eventos e calcular, "
            "os dados de exposição aparecerão aqui."
        )
        return

    df = pd.DataFrame(posicoes)

    # ─── KPIs rápidos ────────────────────────────────────────────────
    total = df["valor_atual"].sum()
    n_ativos = len(df)

    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Patrimônio monitorado", fmt.moeda(total))
    with k2:
        st.metric("Ativos em carteira", n_ativos)
    with k3:
        if "pnl" in df.columns and total > 0:
            pnl_total = df["pnl"].sum()
            st.metric(
                "P&L Total",
                fmt.moeda(pnl_total, sinal=True),
                delta=fmt.pct(pnl_total / (total - pnl_total) if (total - pnl_total) > 0 else 0),
                delta_color="normal" if pnl_total >= 0 else "inverse",
            )
        else:
            st.metric("Ativos", n_ativos)

    st.divider()

    # ─── Exposição por classe de ativo ───────────────────────────────
    if "classe" in df.columns:
        st.subheader("Exposição por Classe de Ativo")
        df_classe = (
            df.groupby("classe", dropna=False)["valor_atual"]
            .sum()
            .reset_index()
            .sort_values("valor_atual", ascending=False)
        )
        df_classe["pct"] = df_classe["valor_atual"] / total if total > 0 else 0

        fig_classe = go.Figure(go.Pie(
            labels=df_classe["classe"].fillna("Outros"),
            values=df_classe["valor_atual"],
            hole=0.4,
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
        ))
        fig_classe.update_layout(
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="white",
            showlegend=True,
            legend=dict(orientation="v", x=1.0, y=0.5),
            margin=dict(t=10, b=10, l=10, r=140),
        )
        st.plotly_chart(fig_classe, use_container_width=True, config={"responsive": True})

        rows_classe = []
        for _, r in df_classe.iterrows():
            rows_classe.append({
                "Classe": r["classe"] or "Outros",
                "Valor": fmt.moeda(r["valor_atual"]),
                "% Carteira": fmt.pct(r["pct"]),
            })
        st.dataframe(pd.DataFrame(rows_classe), use_container_width=True, hide_index=True)

    st.divider()

    # ─── Exposição por bloco IPS ─────────────────────────────────────
    if "bloco_ips" in df.columns:
        st.subheader("Exposição por Bloco IPS")
        df_bloco = (
            df.groupby("bloco_ips", dropna=False)["valor_atual"]
            .sum()
            .reset_index()
            .sort_values("valor_atual", ascending=False)
        )
        df_bloco["pct"] = df_bloco["valor_atual"] / total if total > 0 else 0

        fig_bloco = go.Figure(go.Bar(
            x=df_bloco["bloco_ips"].fillna("—"),
            y=df_bloco["pct"],
            text=[fmt.pct(v) for v in df_bloco["pct"]],
            textposition="outside",
            marker_color="#4a9eff",
            hovertemplate="<b>%{x}</b><br>%{customdata}<br>%{y:.1%}<extra></extra>",
            customdata=[fmt.moeda(v) for v in df_bloco["valor_atual"]],
        ))
        fig_bloco.update_layout(
            height=300,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(20,22,36,0.8)",
            font_color="white",
            xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
            yaxis=dict(
                gridcolor="rgba(255,255,255,0.08)",
                tickformat=".0%",
                title="% Carteira",
            ),
            margin=dict(t=30, b=40, l=60, r=20),
        )
        st.plotly_chart(fig_bloco, use_container_width=True, config={"responsive": True})

        rows_bloco = []
        for _, r in df_bloco.iterrows():
            rows_bloco.append({
                "Bloco IPS": r["bloco_ips"] or "—",
                "Valor": fmt.moeda(r["valor_atual"]),
                "% Carteira": fmt.pct(r["pct"]),
            })
        st.dataframe(pd.DataFrame(rows_bloco), use_container_width=True, hide_index=True)

    elif "classe" not in df.columns:
        st.info(
            "Os dados de posições não contêm informações de classe ou bloco IPS. "
            "Use o Assistente para análise de risco detalhada."
        )

    st.divider()

    # ─── Concentração — top 5 ─────────────────────────────────────────
    st.subheader("Concentração — Top 5 Ativos")
    df_sorted = df.sort_values("valor_atual", ascending=False).head(5)
    rows_conc = []
    for _, r in df_sorted.iterrows():
        pct = r["valor_atual"] / total if total > 0 else 0
        rows_conc.append({
            "Ticker": r.get("ticker", "—"),
            "Valor": fmt.moeda(r["valor_atual"]),
            "% Carteira": fmt.pct(pct),
        })
    st.dataframe(pd.DataFrame(rows_conc), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown(
        "> Para análise completa de **drawdown**, **stress test** e **liquidez**, "
        "acesse o **Assistente** e pergunte: _'análise de risco da carteira'_."
    )
