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
    diario,
    correlacao,
    whatif,
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

# ─── Tema ────────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True

_DARK = st.session_state["dark_mode"]

# CSS: responsividade mobile + tema dinâmico
_LIGHT_OVERRIDES = """
    [data-testid="stAppViewContainer"] > div:first-child {
        background-color: #f4f6fb !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        background-color: #e8ecf4 !important;
    }
    [data-testid="stSidebar"] * { color: #1a1a2e !important; }
    .block-container { background-color: #f4f6fb !important; }
    h1, h2, h3, h4, p, span, label { color: #1a1a2e !important; }
    [data-testid="stDataFrame"] { background: #fff; }
    [data-testid="metric-container"] { background: #e8ecf4 !important; border-radius: 8px; }
""" if not _DARK else ""

st.markdown(f"""
<style>
{_LIGHT_OVERRIDES}
@media (max-width: 640px) {{
    div[data-testid="column"] {{
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }}
    .stButton > button,
    .stDownloadButton > button {{
        min-height: 44px !important;
        font-size: 1rem !important;
    }}
    div[data-testid="stPlotlyChart"] iframe,
    div[data-testid="stPlotlyChart"] > div {{
        min-height: 300px !important;
    }}
    div[data-testid="stDataFrame"] > div {{
        overflow-x: auto !important;
    }}
    .block-container {{
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }}
    div[data-testid="metric-container"] {{
        min-width: 0 !important;
    }}
}}
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
    "📓 Diário": diario,
    "🔗 Correlação": correlacao,
    "🔮 What-If": whatif,
    "⚙️ Configurações": configuracoes,
}

with st.sidebar:
    st.title("💼 Carteira Clean")

    # ─── Toggle dark/light mode ───────────────────────────────
    _label = "☀️ Modo Claro" if _DARK else "🌙 Modo Escuro"
    if st.button(_label, use_container_width=True, key="btn_tema"):
        st.session_state["dark_mode"] = not _DARK
        st.rerun()

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
