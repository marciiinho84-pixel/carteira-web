"""
Carteira Clean — aplicação Streamlit principal.
"""

import streamlit as st

from carteira_clean_web.frontend.utils import api
from carteira_clean_web.backend.scripts.backup import backup_se_necessario
from carteira_clean_web.frontend.telas import (
    carteira_rv,
    novo_evento,
    dashboard,
    posicoes,
    vendas,
    meta,
    evolucao,
    proventos,
    configuracoes,
)

# Backup automático: uma vez por dia, não bloqueia se falhar
if "backup_hoje_feito" not in st.session_state:
    try:
        backup_se_necessario()
    except Exception:
        pass
    st.session_state["backup_hoje_feito"] = True

st.set_page_config(
    page_title="Carteira Clean",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS mobile-first: colunas empilham em telas < 640px, botões com área de toque adequada
st.markdown("""
<style>
@media (max-width: 640px) {
    /* Empilha colunas em telas estreitas */
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    /* Área de toque mínima para botões (padrão Apple 44px) */
    .stButton > button,
    .stDownloadButton > button {
        min-height: 44px !important;
        font-size: 1rem !important;
    }
    /* Treemap / gráficos: altura mínima */
    div[data-testid="stPlotlyChart"] iframe,
    div[data-testid="stPlotlyChart"] > div {
        min-height: 300px !important;
    }
    /* Tabelas: garante scroll horizontal */
    div[data-testid="stDataFrame"] > div {
        overflow-x: auto !important;
    }
    /* Reduz padding lateral em mobile */
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    /* Card KPI: permite quebra de linha */
    div[data-testid="metric-container"] {
        min-width: 0 !important;
    }
}
</style>
""", unsafe_allow_html=True)

PAGINAS = {
    "📊 Carteira RV": carteira_rv,
    "➕ Novo Evento": novo_evento,
    "🏠 Dashboard": dashboard,
    "📋 Posições": posicoes,
    "💰 Vendas": vendas,
    "🎯 Meta": meta,
    "📈 Evolução": evolucao,
    "📅 Proventos": proventos,
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
