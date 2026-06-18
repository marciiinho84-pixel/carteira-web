"""
Página: Macro e Eventos Corporativos — contexto macroeconômico persistido (Fatia 3).
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from carteira_clean_web.frontend.utils import api

_INDICADORES = {
    "SELIC_META":   ("Selic Meta (% a.a.)", "BCB SGS 432"),
    "IPCA":         ("IPCA (% a.m.)", "BCB SGS 433"),
    "USD_BRL":      ("USD/BRL PTAX", "BCB SGS 1"),
    "SELIC_DIARIA": ("CDI diário (% a.d.)", "BCB SGS 12"),
    "IPCA_FOCUS":   ("IPCA Esperado — Focus (% a.a.)", "BCB Olinda"),
}
_CORES = {
    "SELIC_META":   "#4a9eff",
    "IPCA":         "#ff6b6b",
    "USD_BRL":      "#ffd93d",
    "SELIC_DIARIA": "#6bcb77",
    "IPCA_FOCUS":   "#c77dff",
}


def _grafico_serie(pontos: list[dict], titulo: str, cor: str, fmt_y: str = ".2f") -> go.Figure:
    datas = [p["data"] for p in reversed(pontos)]
    valores = [p["valor"] for p in reversed(pontos)]
    fig = go.Figure(go.Scatter(
        x=datas, y=valores,
        mode="lines+markers",
        line=dict(color=cor, width=2),
        marker=dict(size=4),
        hovertemplate=f"<b>%{{x}}</b><br>%{{y:{fmt_y}}}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=13)),
        height=220,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,22,36,0.8)",
        font_color="white",
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", showgrid=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", tickformat=fmt_y),
        margin=dict(t=35, b=30, l=50, r=10),
    )
    return fig


def render():
    st.title("🌍 Macro e Eventos Corporativos")
    st.caption(
        "Indicadores macroeconômicos persistidos (BCB SGS + Focus) "
        "e agenda de eventos corporativos (yfinance)."
    )

    abas = st.tabs(["📊 Indicadores Macro", "📅 Eventos Corporativos", "⚙️ Coletar"])

    # ─── Aba 1: Indicadores Macro ─────────────────────────────────────────────
    with abas[0]:
        dados_macro = api.get("macro/indicadores", params={"ultimos_n": 24}) or {}

        if not any(dados_macro.values()):
            st.info(
                "Nenhum dado macro disponível. "
                "Vá à aba **⚙️ Coletar** para buscar os dados pela primeira vez."
            )
        else:
            # KPIs com os valores mais recentes
            cols = st.columns(len(_INDICADORES))
            for i, (ind, (label, fonte)) in enumerate(_INDICADORES.items()):
                pontos = dados_macro.get(ind, [])
                with cols[i]:
                    if pontos:
                        ultimo = pontos[0]
                        val = ultimo["valor"]
                        data_val = ultimo["data"]
                        # Formatar conforme tipo
                        if ind == "USD_BRL":
                            val_fmt = f"R$ {val:.4f}"
                        elif ind == "SELIC_DIARIA":
                            val_fmt = f"{val:.6f}%"
                        else:
                            val_fmt = f"{val:.2f}%"
                        st.metric(label.split(" (")[0], val_fmt, help=f"Ref: {data_val} · {fonte}")
                    else:
                        st.metric(label.split(" (")[0], "—")

            st.divider()

            # Gráficos por indicador
            ind_selecionados = st.multiselect(
                "Indicadores a exibir",
                options=list(_INDICADORES.keys()),
                default=["SELIC_META", "IPCA", "USD_BRL"],
                format_func=lambda x: _INDICADORES[x][0],
                key="macro_ind_sel",
            )

            for ind in ind_selecionados:
                pontos = dados_macro.get(ind, [])
                if not pontos:
                    st.caption(f"{_INDICADORES[ind][0]}: sem dados")
                    continue
                label, _ = _INDICADORES[ind]
                fmt_y = ".4f" if ind == "SELIC_DIARIA" else ".2f"
                fig = _grafico_serie(pontos, label, _CORES.get(ind, "#4a9eff"), fmt_y)
                st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

            # Tabela detalhada
            with st.expander("Ver tabela completa"):
                rows = []
                for ind, (label, fonte) in _INDICADORES.items():
                    pontos = dados_macro.get(ind, [])
                    for p in pontos[:12]:
                        rows.append({
                            "Indicador": label,
                            "Data": p["data"],
                            "Valor": p["valor"],
                            "Fonte": fonte,
                        })
                if rows:
                    st.dataframe(
                        pd.DataFrame(rows).sort_values(["Indicador", "Data"], ascending=[True, False]),
                        use_container_width=True,
                        hide_index=True,
                    )

    # ─── Aba 2: Eventos Corporativos ─────────────────────────────────────────
    with abas[1]:
        st.caption(
            "Análise completa via 🤖 Assistente: **'próximos eventos corporativos da carteira'**"
        )

        col_filtro1, col_filtro2 = st.columns([2, 1])
        with col_filtro1:
            ticker_f = st.text_input("Filtrar por ativo", placeholder="Ex: WEGE3", key="ev_ticker_f")
        with col_filtro2:
            janela = st.selectbox("Horizonte", [30, 60, 90, 180], index=1, key="ev_janela")

        params = {"janela_dias": janela}
        if ticker_f.strip():
            params["ticker"] = ticker_f.strip().upper()

        eventos = api.get("macro/eventos-corporativos", params=params) or []

        if not eventos:
            st.info(
                "Nenhum evento encontrado no horizonte selecionado. "
                "Vá à aba **⚙️ Coletar** para buscar eventos atualizados."
            )
        else:
            hoje = date.today()
            rows_ev = []
            for ev in eventos:
                dt = date.fromisoformat(ev["data_evento"]) if ev.get("data_evento") else None
                dias_restantes = (dt - hoje).days if dt else None
                urgencia = (
                    "🔴" if dias_restantes is not None and dias_restantes <= 7
                    else "🟡" if dias_restantes is not None and dias_restantes <= 21
                    else "🟢"
                )
                rows_ev.append({
                    "": urgencia,
                    "Ativo": ev.get("ticker", "—"),
                    "Tipo": ev.get("tipo", "—"),
                    "Data": ev.get("data_evento", "—"),
                    "Dias": dias_restantes if dias_restantes is not None else "—",
                    "Descrição": (ev.get("descricao") or "—")[:60],
                })

            st.dataframe(
                pd.DataFrame(rows_ev).sort_values("Data"),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"{len(eventos)} evento(s) nos próximos {janela} dias")

    # ─── Aba 3: Coletar ───────────────────────────────────────────────────────
    with abas[2]:
        st.markdown("#### ⚙️ Coletar dados macro e eventos")
        st.info(
            "A coleta usa as APIs gratuitas do Banco Central (BCB SGS + Focus/Olinda) "
            "e yfinance. Pode levar 30-60 segundos."
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Indicadores Macro**")
            st.caption("Selic, IPCA, USD/BRL, Focus — BCB SGS + Olinda")
            if st.button("📥 Coletar Macro", key="btn_coletar_macro"):
                with st.spinner("Coletando indicadores macro (BCB)..."):
                    res = api.post("macro/coletar")
                if res is not None:
                    st.success("✅ Coleta macro iniciada em background!")
                else:
                    st.error("Erro ao iniciar coleta. Verifique logs do backend.")

        with c2:
            st.markdown("**Eventos Corporativos**")
            st.caption("Earnings dates, ex-dividend dates — yfinance")
            if st.button("📅 Coletar Eventos", key="btn_coletar_eventos"):
                with st.spinner("Coletando eventos corporativos (yfinance)..."):
                    res = api.post("macro/coletar-eventos")
                if res is not None:
                    st.success("✅ Coleta de eventos iniciada em background!")
                else:
                    st.error("Erro ao iniciar coleta. Verifique logs do backend.")

        st.divider()
        st.caption(
            "Após a coleta (30-60s), recarregue a página para ver os dados atualizados."
        )
