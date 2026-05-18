"""
Carteira Clean — aplicação Streamlit principal.
"""

import streamlit as st

from carteira_clean_web.frontend.utils import api
from carteira_clean_web.frontend.telas import (
    carteira_rv,
    novo_evento,
    dashboard,
    posicoes,
    vendas,
    meta,
    evolucao,
    configuracoes,
)

st.set_page_config(
    page_title="Carteira Clean",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGINAS = {
    "📊 Carteira RV": carteira_rv,
    "➕ Novo Evento": novo_evento,
    "🏠 Dashboard": dashboard,
    "📋 Posições": posicoes,
    "💰 Vendas": vendas,
    "🎯 Meta": meta,
    "📈 Evolução": evolucao,
    "⚙️ Configurações": configuracoes,
}

with st.sidebar:
    st.title("💼 Carteira Clean")
    st.divider()

    pagina_sel = st.radio(
        "Navegação",
        list(PAGINAS.keys()),
        label_visibility="collapsed",
    )

    st.divider()

    # Indicador de última atualização
    ultima = api.tempo_desde_calculo()
    if ultima:
        st.caption(f"🕒 Última atualização: {ultima}")
    else:
        st.caption("⚠️ Engine não calculado")

    if st.button("🔄 Recalcular", use_container_width=True):
        with st.spinner("Calculando..."):
            res = api.post("calcular", params={"no_api": "true"})
        if res and res.get("ok"):
            st.success("✅ Atualizado!")
            st.rerun()

PAGINAS[pagina_sel].render()
