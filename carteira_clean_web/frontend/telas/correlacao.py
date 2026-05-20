"""
Página: Correlação — heatmap de correlações entre ativos da Carteira RV.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, timedelta

from carteira_clean_web.frontend.utils import api, fmt

JANELAS = {"3 meses": 63, "6 meses": 126, "YTD": None}


def _carregar_retornos_yfinance(tickers: list, dias: int | None) -> pd.DataFrame | None:
    """Tenta baixar preços via yfinance. Retorna DataFrame de retornos ou None."""
    try:
        import yfinance as yf
        fim = date.today()
        ini = date(fim.year, 1, 1) if dias is None else (fim - timedelta(days=int(dias * 1.4)))
        # Adiciona .SA para ações BR
        mapa = {}
        symbols = []
        for t in tickers:
            sym = t + ".SA" if not t.endswith((".SA", "34", "39", "11")) else t
            if t.endswith(("34", "39")):
                sym = t + ".SA"
            mapa[sym] = t
            symbols.append(sym)

        raw = yf.download(symbols, start=str(ini), end=str(fim),
                          progress=False, auto_adjust=True)["Close"]
        if raw.empty:
            return None
        raw = raw.rename(columns=mapa)
        rets = raw.pct_change().dropna(how="all")
        # Manter apenas colunas com pelo menos 20 obs não-NaN
        rets = rets.loc[:, rets.count() >= 20]
        return rets if not rets.empty else None
    except Exception:
        return None


def render():
    st.title("🔗 Correlação entre Ativos")
    st.caption("Matriz de correlação de Pearson sobre retornos diários dos ativos da Carteira RV.")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    posicoes = api.get("posicoes") or []
    rv_pos = [p for p in posicoes if p.get("familia") in
              {"Ação BR", "BDR", "BDR de ETF", "ETF BR"}]

    if len(rv_pos) < 2:
        st.info("Menos de 2 ativos de Renda Variável com posição ativa — sem correlação a calcular.")
        return

    tickers_rv = [p["ticker"] for p in rv_pos]

    # ─── Filtros ──────────────────────────────────────────────────
    fc1, fc2 = st.columns(2)
    with fc1:
        janela_label = st.selectbox("Janela temporal", list(JANELAS.keys()), key="corr_janela")
    with fc2:
        tickers_sel = st.multiselect("Ativos", tickers_rv, default=tickers_rv, key="corr_ativos")

    if len(tickers_sel) < 2:
        st.warning("Selecione pelo menos 2 ativos.")
        return

    # ─── Carregar retornos ────────────────────────────────────────
    with st.spinner("Carregando dados de mercado…"):
        dias_janela = JANELAS[janela_label]
        rets = _carregar_retornos_yfinance(tickers_sel, dias_janela)

    if rets is None or rets.empty:
        st.warning(
            "⚠️ Não foi possível obter dados de mercado (modo offline ou conexão indisponível). "
            "Inicie com preços de mercado para habilitar a análise de correlação."
        )
        st.info(
            "💡 Para ativar: clique em **'🌐 Recalcular (com preços de mercado)'** "
            "em ⚙️ Configurações → Sistema."
        )
        return

    # Filtrar apenas tickers com dados
    cols_disp = [t for t in tickers_sel if t in rets.columns]
    if len(cols_disp) < 2:
        st.warning("Dados insuficientes para os ativos selecionados.")
        return

    rets_f = rets[cols_disp].dropna(how="all")
    n_obs = len(rets_f)

    if n_obs < 10:
        st.warning(f"Apenas {n_obs} observações — dados insuficientes para correlação.")
        return

    if n_obs < 30:
        st.warning(f"⚠️ Apenas {n_obs} observações — correlações podem ser instáveis (mínimo recomendado: 30).")

    # ─── Matriz de correlação ─────────────────────────────────────
    corr = rets_f.corr(method="pearson").round(3)

    # ─── Heatmap ─────────────────────────────────────────────────
    st.subheader(f"Heatmap — {janela_label} ({n_obs} obs.)")

    labels = list(corr.columns)
    z = corr.values

    # Texto de anotação nas células
    text = [[f"{v:.2f}" for v in row] for row in z]

    _pt = fmt.plotly_theme()
    fig = go.Figure(go.Heatmap(
        z=z,
        x=labels,
        y=labels,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 11},
        colorscale=[
            [0.0, "#e74c3c"],    # -1: vermelho intenso
            [0.5, "#95a5a6"],    # 0:  cinza
            [1.0, "#2ecc71"],    # +1: verde intenso
        ],
        zmin=-1, zmax=1,
        colorbar=dict(title="Correlação", tickvals=[-1, -0.5, 0, 0.5, 1]),
        hovertemplate="<b>%{y} × %{x}</b><br>Correlação: %{z:.3f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(350, 60 * len(labels)),
        **_pt,
        margin=dict(t=20, b=20, l=80, r=80),
        xaxis=dict(side="bottom"),
    )
    st.plotly_chart(fig, use_container_width=True, config={"responsive": True})

    # ─── Insights automáticos ─────────────────────────────────────
    st.subheader("Insights")
    pares = []
    n = len(labels)
    for i in range(n):
        for j in range(i + 1, n):
            pares.append((labels[i], labels[j], corr.iloc[i, j]))

    pares_sort = sorted(pares, key=lambda x: x[2], reverse=True)
    altos = [p for p in pares_sort if p[2] > 0.6]
    baixos = [p for p in pares_sort if p[2] < 0.2]

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**⚠️ Pares mais correlacionados (risco de concentração):**")
        if altos:
            for a, b, c in altos[:3]:
                st.markdown(f"- {a} × {b}: **{c:+.2f}**")
        else:
            st.markdown("_Nenhum par com correlação > 0,60_")

    with col_b:
        st.markdown("**✅ Pares mais diversificadores:**")
        baixos_ord = sorted(baixos, key=lambda x: x[2])
        if baixos_ord:
            for a, b, c in baixos_ord[:3]:
                st.markdown(f"- {a} × {b}: **{c:+.2f}**")
        else:
            st.markdown("_Nenhum par com correlação < 0,20_")

    # ─── Tabela completa ─────────────────────────────────────────
    with st.expander("📋 Tabela de correlações (todos os pares)"):
        rows_tab = [{"Par": f"{a} × {b}", "Correlação": f"{c:+.3f}",
                     "Nível": "Alta" if c > 0.6 else ("Baixa/Neg." if c < 0.2 else "Média")}
                    for a, b, c in pares_sort]
        st.dataframe(pd.DataFrame(rows_tab), use_container_width=True, hide_index=True)
