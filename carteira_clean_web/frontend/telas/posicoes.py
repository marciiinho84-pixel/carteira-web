"""
Página: Posições — tabela filtrável com status D+2 e P&L colorido.
"""

import streamlit as st
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("📋 Posições")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    pos_data = api.get("posicoes")
    if pos_data is None:
        return

    df = pd.DataFrame(pos_data)
    if df.empty:
        st.info("Nenhuma posição ativa.")
        return

    # ─── Filtros ──────────────────────────────────────────────────
    st.subheader("Filtros")
    fc1, fc2, fc3 = st.columns(3)

    with fc1:
        familias = sorted(df["familia"].dropna().unique())
        familia_sel = st.multiselect("Família", options=familias, default=[])

    with fc2:
        composites = sorted(df["composite"].dropna().unique())
        composite_sel = st.multiselect("Composite", options=composites, default=[])

    with fc3:
        busca = st.text_input("Buscar ticker", placeholder="Ex: PETR4")

    # Aplicar filtros
    df_filtrado = df.copy()
    if familia_sel:
        df_filtrado = df_filtrado[df_filtrado["familia"].isin(familia_sel)]
    if composite_sel:
        df_filtrado = df_filtrado[df_filtrado["composite"].isin(composite_sel)]
    if busca:
        df_filtrado = df_filtrado[
            df_filtrado["ticker"].str.upper().str.contains(busca.upper())
        ]

    st.divider()

    # ─── KPIs de resumo ───────────────────────────────────────────
    total_custo = df_filtrado["custo_total"].sum()
    total_valor = df_filtrado["valor_atual"].sum()
    total_pnl = df_filtrado["pnl"].sum()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Ativos exibidos", len(df_filtrado))
    with k2:
        st.metric("Custo Total", fmt.moeda(total_custo))
    with k3:
        st.metric("Valor Atual", fmt.moeda(total_valor))
    with k4:
        cor = "normal" if total_pnl >= 0 else "inverse"
        st.metric(
            "P&L Total",
            fmt.moeda(total_pnl, sinal=True),
            delta=fmt.pct(total_pnl / total_custo if total_custo > 0 else 0),
            delta_color=cor,
        )

    st.divider()

    # ─── Tabela principal ─────────────────────────────────────────
    st.subheader(f"Posições ({len(df_filtrado)} ativos)")

    rows = []
    pnl_vals = []
    for _, r in df_filtrado.sort_values("valor_atual", ascending=False).iterrows():
        pnl = r["pnl"]
        pnl_vals.append(pnl)
        status = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "🟡")

        rows.append({
            "": status,
            "Ticker": r["ticker"],
            "Família": r.get("familia", "—"),
            "Composite": r.get("composite", "—"),
            "Qtd": f"{r['qtd']:,.4f}" if r["qtd"] else "—",
            "Custo Médio": fmt.moeda(r["custo_medio"]),
            "Custo Total": fmt.moeda(r["custo_total"]),
            "Preço Atual": fmt.moeda(r["preco_atual"]) if r["preco_atual"] else "—",
            "Valor Atual": fmt.moeda(r["valor_atual"]),
            "P&L R$": fmt.moeda(pnl, sinal=True),
            "P&L %": fmt.pct(r["pnl_pct"]),
        })

    df_exib = pd.DataFrame(rows)

    def _cor_linha(row):
        pnl = pnl_vals[row.name]
        if pnl > 0:
            bg = "background-color: rgba(46, 204, 113, 0.10)"
        elif pnl < 0:
            bg = "background-color: rgba(231, 76, 60, 0.10)"
        else:
            bg = ""
        return [bg] * len(row)

    st.dataframe(
        df_exib.style.apply(_cor_linha, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # ─── Detalhamento por composite ───────────────────────────────
    st.divider()
    st.subheader("Resumo por Composite")
    for comp in sorted(df_filtrado["composite"].unique()):
        df_comp = df_filtrado[df_filtrado["composite"] == comp]
        custo_c = df_comp["custo_total"].sum()
        valor_c = df_comp["valor_atual"].sum()
        pnl_c = df_comp["pnl"].sum()
        emoji = "🏛️" if comp == "FUNCEF" else "💼"
        pnl_delta = f"{'+' if pnl_c >= 0 else ''}{pnl_c:,.2f}"
        st.metric(
            f"{emoji} {comp}",
            fmt.moeda(valor_c),
            delta=f"P&L: R$ {pnl_delta}",
            delta_color="normal" if pnl_c >= 0 else "inverse",
        )
