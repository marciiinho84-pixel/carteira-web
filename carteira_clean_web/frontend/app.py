"""
Carteira Clean — aplicação Streamlit principal.
"""

import importlib
import streamlit as st
from streamlit_option_menu import option_menu

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
    importar,
    assistente,
)

# Força reload dos módulos de tela para que edições em desenvolvimento
# sejam sempre refletidas sem reiniciar o processo Streamlit.
for _mod in [carteira_rv, novo_evento, dashboard, posicoes, vendas, meta,
             evolucao, proventos, diario, correlacao, whatif, configuracoes, importar, assistente]:
    importlib.reload(_mod)

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
    initial_sidebar_state="collapsed",
)

# ─── Tema ────────────────────────────────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True

_DARK = st.session_state["dark_mode"]

_LIGHT_OVERRIDES = """
    [data-testid="stAppViewContainer"] > div:first-child {
        background-color: #f4f6fb !important;
    }
    .block-container { background-color: #f4f6fb !important; }
    h1, h2, h3, h4, p, span, label { color: #1a1a2e !important; }
    [data-testid="stDataFrame"] { background: #fff; }
    [data-testid="metric-container"] { background: #e8ecf4 !important; border-radius: 8px; }
""" if not _DARK else ""

# ─── CSS Global ──────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
/* Esconder sidebar e botão de colapso */
[data-testid="stSidebar"] {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}

/* Conteúdo principal — sem padding excessivo */
.main .block-container {{
    padding-top: 0.5rem !important;
    max-width: 1400px !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
}}

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
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }}
    div[data-testid="metric-container"] {{
        min-width: 0 !important;
    }}
}}
</style>
""", unsafe_allow_html=True)

# ─── Mapeamento de páginas (ordem da navbar) ─────────────────────────────────
PAGINAS = {
    "🏠 Dashboard":        dashboard,
    "🤖 Assistente":       assistente,
    "📊 Carteira RV":      carteira_rv,
    "📋 Posições":         posicoes,
    "💰 Proventos":        proventos,
    "📈 Evolução":         evolucao,
    "🎯 Meta":             meta,
    "🔗 Correlação":       correlacao,
    "🔮 What-If":          whatif,
    "➕ Novo Evento":       novo_evento,
    "📥 Importar Extrato": importar,
    "📓 Diário":           diario,
    "⚙️ Configurações":    configuracoes,
}

# ─── Navbar horizontal ───────────────────────────────────────────────────────
pagina_sel = option_menu(
    menu_title=None,
    options=list(PAGINAS.keys()),
    icons=[""] * len(PAGINAS),
    menu_icon=None,
    default_index=0,
    orientation="horizontal",
    styles={
        "container": {
            "padding": "0",
            "background-color": "#0F1117",
            "border-bottom": "1px solid #252D3D",
            "margin-bottom": "0",
        },
        "nav": {
            "background-color": "#0F1117",
            "flex-wrap": "nowrap",
            "overflow-x": "auto",
        },
        "icon": {
            "display": "none",
            "font-size": "0",
        },
        "nav-link": {
            "font-size": "0.76rem",
            "color": "#787B86",
            "padding": "10px 8px",
            "border-radius": "0",
            "white-space": "nowrap",
            "--hover-color": "#252D3D",
        },
        "nav-link-selected": {
            "background-color": "transparent",
            "color": "#6366F1",
            "border-bottom": "2px solid #6366F1",
            "font-weight": "600",
        },
    },
)

# ─── Barra de status compacta ────────────────────────────────────────────────
col_status, col_btn1, col_btn2, col_tema = st.columns([6, 1.2, 1.8, 0.7])

with col_status:
    ultima = api.tempo_desde_calculo()
    label_st = f"🕒 Última atualização: {ultima}" if ultima else "⚠️ Engine não calculado"
    st.markdown(
        f'<div style="padding:5px 0 2px 0;font-size:0.78rem;color:#787B86">{label_st}</div>',
        unsafe_allow_html=True,
    )

with col_btn1:
    if st.button("🔄 Recalcular", use_container_width=True,
                 help="Recalcula sem buscar cotações (rápido)"):
        with st.spinner("Calculando..."):
            res = api.post("calcular", params={"no_api": "true"})
        if res and res.get("ok"):
            st.success("✅ Atualizado!")
            st.rerun()

with col_btn2:
    if st.button("📡 Atualizar cotações", use_container_width=True,
                 help="Baixa preços do dia via internet (~30s)"):
        with st.spinner("Baixando cotações... (~30s)"):
            res = api.post("calcular", params={"no_api": "false"})
        if res and res.get("ok"):
            st.success("✅ Cotações atualizadas!")
            st.rerun()

with col_tema:
    _icone = "☀️" if _DARK else "🌙"
    if st.button(_icone, use_container_width=True,
                 help="Alternar modo claro/escuro"):
        st.session_state["dark_mode"] = not _DARK
        st.rerun()

st.divider()

# ─── Renderizar página selecionada ───────────────────────────────────────────
PAGINAS[pagina_sel].render()
