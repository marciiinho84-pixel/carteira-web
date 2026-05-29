"""
Carteira RV — Central de Decisões de Renda Variável.

Layout v3:
  A  — Pulso do dia (4 KPIs)
  B  — Heatmap treemap (3 modos)
  C  — Concentração  |  Ranking P&L
  E+G — Alertas      |  Caixa operacional
  F  — Performance RV vs benchmarks (largura total)
  H  — Análise setorial treemap
  Placeholders: Sinais técnicos / Watchlist
  Diário
"""

from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from carteira_clean_web.frontend.utils import api, fmt
from carteira_clean_web.frontend.components.kpi_card import kpi_card_html
from carteira_clean_web.frontend.components.heatmap_posicoes import heatmap_posicoes_html
from carteira_clean_web.frontend.components.ranking_pnl import ranking_pnl_html
from carteira_clean_web.frontend.components.treemap_setorial import treemap_setorial_html
from carteira_clean_web.frontend.components.tv_chart import tv_chart_rv_html
from carteira_clean_web.frontend.components.watchlist import render_watchlist
from carteira_clean_web.frontend.components.sinais_card import sinais_html

# ── Design tokens ──────────────────────────────────────────────────
_BG      = "#161B27"
_CARD    = "#1C2333"
_BORDER  = "#252D3D"
_TXT     = "#D1D4DC"
_TXT2    = "#787B86"
_FONT    = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
_OK      = "#26A69A"
_CRITICO = "#EF5350"
_ALERTA  = "#F59E0B"
_INDIGO  = "#6366F1"

_SECTION_LABEL = (
    "font-size:0.62rem;font-weight:600;letter-spacing:0.14em;"
    f"text-transform:uppercase;color:{_TXT2};margin-bottom:10px"
)

_DIVIDER = (
    '<hr style="border:none;border-top:1px solid #1C2333;margin:20px 0 16px">'
)

_CORES_SETOR = [
    "#6366F1", "#26A69A", "#F59E0B", "#EC4899",
    "#3B82F6", "#8B5CF6", "#10B981", "#F97316",
]


def _hex_rgb(h: str) -> str:
    h = h.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"


# ── HTML helpers ───────────────────────────────────────────────────

def _card_alerta(ticker: str, pnl_pct: float, pnl_rs: float, critico: bool) -> str:
    cor   = _CRITICO if critico else _ALERTA
    badge = "CRÍTICO" if critico else "ATENÇÃO"
    sinal_label = fmt.pct(pnl_pct)
    rs_label    = fmt.moeda(abs(pnl_rs))
    return (
        f'<div style="background:rgba({_hex_rgb(cor)},0.08);border-left:3px solid {cor};'
        f'border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:8px;'
        f'font-family:{_FONT}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:4px">'
        f'<span style="color:{_TXT};font-weight:700;font-size:14px;'
        f'letter-spacing:0.02em">{ticker}</span>'
        f'<span style="background:rgba({_hex_rgb(cor)},0.20);color:{cor};font-size:10px;'
        f'font-weight:600;padding:2px 8px;border-radius:4px;letter-spacing:0.05em">'
        f'{badge}</span></div>'
        f'<span style="color:{cor};font-size:13px;font-weight:600">{sinal_label}</span>'
        f'<span style="color:{_TXT2};font-size:12px"> · -{rs_label}</span>'
        f'</div>'
    )


def _concentracao_html(setores: list, top_ativos: list) -> str:
    barras = ""
    for i, s in enumerate(setores[:8]):
        pct = round(s["pct_rv"] * 100, 1)
        cor = _CORES_SETOR[i % len(_CORES_SETOR)]
        bar_w = max(2, min(100, pct * 5))
        barras += (
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">'
            f'<div style="width:96px;font-size:11px;color:{_TXT2};white-space:nowrap;'
            f'overflow:hidden;text-overflow:ellipsis;flex-shrink:0">{s["nome"]}</div>'
            f'<div style="flex:1;background:#1C2333;border-radius:3px;height:6px">'
            f'<div style="width:{bar_w}%;background:{cor};height:100%;border-radius:3px;'
            f'transition:width 0.3s ease"></div></div>'
            f'<div style="width:34px;text-align:right;font-size:11px;color:{_TXT};'
            f'font-weight:600;flex-shrink:0">{pct}%</div></div>'
        )

    top_rows = ""
    for p in top_ativos[:5]:
        pct = round(p["pct_rv"] * 100, 1)
        cor = _ALERTA if pct > 15 else _TXT
        badge = (
            f'<span style="font-size:9px;background:rgba({_hex_rgb(_ALERTA)},0.18);'
            f'color:{_ALERTA};padding:1px 5px;border-radius:3px;margin-left:4px">▲</span>'
            if pct > 15 else ""
        )
        top_rows += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:5px 0;border-bottom:1px solid #1C2333">'
            f'<span style="color:{_TXT};font-size:12px;font-weight:500">'
            f'{p["ticker"]}{badge}</span>'
            f'<span style="color:{cor};font-size:12px;font-weight:700">{pct}%</span>'
            f'</div>'
        )

    return (
        f'<div style="font-family:{_FONT}">'
        f'<div style="{_SECTION_LABEL}">Por Setor</div>'
        f'{barras}'
        f'<div style="{_SECTION_LABEL};margin-top:14px">Top 5 Individuais</div>'
        f'{top_rows}</div>'
    )


def _caixa_html(caixa: dict) -> str:
    saldo   = caixa["projetado"]
    cor_sal = _OK if saldo >= 0 else _CRITICO
    label_pc = ("disponível" if saldo >= 0 else "déficit")

    def _row(label, valor, cor=_TXT, bold=False):
        fw = "700" if bold else "400"
        return (
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:7px 0;border-bottom:1px solid #1C2333">'
            f'<span style="color:{_TXT2};font-size:13px">{label}</span>'
            f'<span style="color:{cor};font-size:13px;font-weight:{fw}">{valor}</span>'
            f'</div>'
        )

    return (
        f'<div style="font-family:{_FONT}">'
        + _row("Caixa FIC FUNC",  fmt.moeda(caixa["atual"]))
        + _row("Entrando D+2", "+" + fmt.moeda(caixa["entrando_d2"]), _OK)
        + _row("Saindo D+2",   "−" + fmt.moeda(caixa["saindo_d2"]),  _CRITICO)
        + f'<div style="display:flex;justify-content:space-between;align-items:center;'
          f'padding:10px 0 4px">'
          f'<span style="color:{_TXT};font-size:13px;font-weight:700">Saldo projetado</span>'
          f'<span style="color:{cor_sal};font-size:14px;font-weight:700">'
          f'{fmt.moeda(abs(saldo))}</span></div>'
        + f'<div style="margin-top:8px;padding:8px 10px;border-radius:6px;'
          f'background:rgba({_hex_rgb(cor_sal)},0.10);'
          f'color:{cor_sal};font-size:12px;font-weight:500">'
          f'Poder de compra: <strong>{fmt.moeda(abs(saldo))}</strong> {label_pc}</div>'
        + '</div>'
    )


def _diario_card_html(e: dict) -> str:
    ativo = e.get("ativo", "")
    acao  = e.get("acao", "")
    tese  = e.get("tese", "")
    data_d = e.get("data_decisao", "")
    cor_acao = _OK if "COMPRA" in acao.upper() else (_CRITICO if "VENDA" in acao.upper() else _TXT2)
    return (
        f'<div style="background:rgba(28,35,51,0.5);border:1px solid {_BORDER};'
        f'border-radius:8px;padding:12px 16px;margin-bottom:8px;font-family:{_FONT}">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">'
        f'<span style="color:{_TXT2};font-size:11px">{data_d}</span>'
        f'<span style="color:{_TXT};font-weight:700;font-size:13px">{ativo}</span>'
        f'<span style="color:{cor_acao};font-size:11px;font-weight:600;'
        f'background:rgba({_hex_rgb(cor_acao)},0.15);padding:1px 7px;border-radius:4px">'
        f'{acao}</span></div>'
        f'<div style="color:#9CA3AF;font-size:12px;line-height:1.5">'
        f'{tese[:160]}{"…" if len(tese) > 160 else ""}</div>'
        f'</div>'
    )


def _placeholder_html(linha1: str, linha2: str) -> str:
    return (
        f'<div style="background:rgba(20,25,35,0.4);'
        f'border:1px dashed rgba(99,102,241,0.25);border-radius:10px;'
        f'padding:36px 24px;text-align:center;font-family:{_FONT}">'
        f'<div style="color:{_TXT2};font-size:12px;margin-bottom:4px">{linha1}</div>'
        f'<div style="color:{_INDIGO};font-size:11px;opacity:0.7">{linha2}</div>'
        f'</div>'
    )


# ── CSS global ─────────────────────────────────────────────────────
_CSS = """
<style>
.main .block-container { padding-top: 0.5rem; }
[data-testid="stTabs"] [data-baseweb="tab"] {
    font-size: 0.82rem; font-weight: 500; color: #787B86;
    padding: 6px 16px;
}
[data-testid="stTabs"] [aria-selected="true"] { color: #6366F1; }
[data-testid="stExpander"] { border: 1px solid #252D3D; border-radius: 8px; }
</style>
"""


# ── Render principal ───────────────────────────────────────────────

def render():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("📈 Carteira RV")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira. Verifique se a API está rodando.")
        return

    dados = api.get_carteira_rv_dados()
    if dados is None:
        return

    posicoes = dados["posicoes"]
    valor_rv = dados["valor_atual"]
    var_pct  = dados["variacao_dia_pct"]
    var_rs   = dados["variacao_dia_valor"]

    # ── A — PULSO DO DIA ─────────────────────────────────────────
    movers_ext = [p for p in posicoes if abs(p.get("variacao_dia_pct", 0)) > 0.05]
    if movers_ext:
        nomes = ", ".join(p["ticker"] for p in movers_ext[:3])
        st.warning(f"⚡ Movimento expressivo hoje (>5%): **{nomes}**")

    cols = st.columns(4)
    with cols[0]:
        components.html(kpi_card_html(
            label="CARTEIRA RV", value=fmt.moeda(valor_rv),
            badge_text=fmt.pct(var_pct), badge_positive=var_pct >= 0,
            subtitle=fmt.moeda(var_rs, sinal=True) + " hoje",
        ), height=110)
    with cols[1]:
        m = dados["movers"]["maior_alta"]
        components.html(kpi_card_html(
            label="MAIOR ALTA", value=m["ticker"],
            badge_text=fmt.pct(m["pct"]), badge_positive=True,
            subtitle=fmt.moeda(m["contrib_rs"], sinal=True) + " contrib",
        ), height=110)
    with cols[2]:
        m = dados["movers"]["maior_queda"]
        components.html(kpi_card_html(
            label="MAIOR QUEDA", value=m["ticker"],
            badge_text=fmt.pct(m["pct"]), badge_positive=False,
            subtitle=fmt.moeda(m["contrib_rs"], sinal=True) + " contrib",
        ), height=110)
    with cols[3]:
        m = dados["movers"]["maior_impacto"]
        components.html(kpi_card_html(
            label="MAIOR IMPACTO P&L", value=m["ticker"],
            badge_text=fmt.moeda(m["contrib_rs"], sinal=True),
            badge_positive=m["contrib_rs"] >= 0,
            subtitle=fmt.pct(m["pct"]) + " no dia",
        ), height=110)

    # ── B — HEATMAP (3 abas) ─────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:2px">'
        f'Mapa de Posições</div>'
        f'<div style="font-size:0.78rem;color:{_TXT2};margin-bottom:10px">'
        f'Selecione a dimensão de análise</div>',
        unsafe_allow_html=True,
    )
    tab_dia, tab_pnl, tab_peso = st.tabs(["📅 Variação Hoje", "💰 P&L Total", "📊 Concentração"])
    with tab_dia:
        components.html(heatmap_posicoes_html(posicoes, mode="dia"), height=340)
    with tab_pnl:
        components.html(heatmap_posicoes_html(posicoes, mode="pnl"), height=340)
    with tab_peso:
        components.html(heatmap_posicoes_html(posicoes, mode="tamanho"), height=340)

    # ── C — CONCENTRAÇÃO | RANKING P&L ───────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    col_conc, col_rank = st.columns([2, 3])

    with col_conc:
        st.markdown(
            f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:12px">'
            f'Concentração</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            _concentracao_html(dados["setores"], dados["top_concentracao"]),
            unsafe_allow_html=True,
        )

    with col_rank:
        n_pos = len(posicoes)
        top_n = min(5, n_pos // 2) if n_pos >= 4 else 2
        ht_rank = (top_n * 2 + 1) * 30 + 50
        st.markdown(
            f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:4px">'
            f'Ranking P&L</div>'
            f'<div style="font-size:0.78rem;color:{_TXT2};margin-bottom:8px">'
            f'Top {top_n} winners · top {top_n} losers — acumulado</div>',
            unsafe_allow_html=True,
        )
        components.html(ranking_pnl_html(posicoes, top_n=top_n), height=ht_rank)

    # ── E+G — ALERTAS | CAIXA ────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    col_alert, col_caixa = st.columns([3, 2])

    THRESH_ATENCAO = -0.15
    THRESH_CRITICO = -0.25

    with col_alert:
        st.markdown(
            f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:4px">'
            f'Painel de Risco</div>'
            f'<div style="font-size:0.78rem;color:{_TXT2};margin-bottom:10px">'
            f'Posições com P&L abaixo de {fmt.pct(THRESH_ATENCAO)}</div>',
            unsafe_allow_html=True,
        )
        alertas = sorted(
            [p for p in posicoes if p.get("pl_total_pct", 0) < THRESH_ATENCAO],
            key=lambda p: p["pl_total_pct"],
        )
        if alertas:
            for p in alertas:
                st.markdown(
                    _card_alerta(p["ticker"], p["pl_total_pct"], p["pl_total_rs"],
                                 p["pl_total_pct"] < THRESH_CRITICO),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div style="background:rgba(38,166,154,0.08);'
                f'border:1px solid rgba(38,166,154,0.25);border-radius:8px;'
                f'padding:18px;text-align:center;color:{_OK};font-family:{_FONT};'
                f'font-size:13px">✓ Nenhuma posição abaixo de {fmt.pct(THRESH_ATENCAO)}</div>',
                unsafe_allow_html=True,
            )

    with col_caixa:
        st.markdown(
            f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:12px">'
            f'Caixa Operacional</div>',
            unsafe_allow_html=True,
        )
        st.markdown(_caixa_html(dados["caixa"]), unsafe_allow_html=True)

    # ── F — PERFORMANCE (largura total) ──────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:2px">'
        f'Performance RV vs Benchmarks</div>'
        f'<div style="font-size:0.78rem;color:{_TXT2};margin-bottom:10px">'
        f'TWR carteira · IBOV · CDI — marcadores de operações</div>',
        unsafe_allow_html=True,
    )
    components.html(
        tv_chart_rv_html(dados["performance_serie"], markers=dados.get("markers", [])),
        height=300,
    )

    # ── H — ANÁLISE SETORIAL ─────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:2px">'
        f'Análise Setorial</div>'
        f'<div style="font-size:0.78rem;color:{_TXT2};margin-bottom:10px">'
        f'setor → ativos · tamanho = valor alocado</div>',
        unsafe_allow_html=True,
    )
    components.html(treemap_setorial_html(dados["setores"]), height=420)

    # ── SINAIS TÉCNICOS ───────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    with st.expander("📡 Sinais Técnicos e Fundamentos", expanded=False):
        with st.spinner("Calculando RSI, MACD e médias móveis..."):
            sinais = api.get_sinais_carteira_rv(apenas_ativos=True)

        n_ativos = sum(1 for s in sinais if s.get("tem_sinal_ativo"))
        if n_ativos > 0:
            st.caption(f"{n_ativos} sinal(is) ativo(s) — posições e watchlist combinadas")
        altura = max(180, 78 * n_ativos + 96)
        components.html(sinais_html(sinais), height=altura)

    # ── WATCHLIST ─────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:10px">'
        f'👁️ Watchlist</div>',
        unsafe_allow_html=True,
    )

    with st.expander("➕ Adicionar à Watchlist", expanded=False):
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            ticker_input = st.text_input(
                "Ticker", placeholder="ex: SAPR11", key="wl_ticker",
            ).upper().strip()
        with col2:
            alvo_input = st.number_input(
                "Preço-alvo (R$)", min_value=0.01, step=0.01, key="wl_alvo",
            )
        with col3:
            stop_raw = st.number_input(
                "Stop-loss (R$) — opcional", min_value=0.0, step=0.01, key="wl_stop",
            )
            stop_input = stop_raw if stop_raw > 0 else None

        motivo_input = st.text_area(
            "Motivo / tese", height=68,
            placeholder="ex: Dividend yield > 8%, setor defensivo...",
            key="wl_motivo",
        )

        if st.button("Adicionar", key="wl_add"):
            if not ticker_input:
                st.error("Ticker obrigatório.")
            elif alvo_input <= 0:
                st.error("Preço-alvo deve ser maior que zero.")
            elif stop_input and stop_input >= alvo_input:
                st.error("Stop-loss deve ser menor que o preço-alvo.")
            else:
                resp = api.post_watchlist({
                    "ticker": ticker_input,
                    "preco_alvo": alvo_input,
                    "stop_loss": stop_input,
                    "motivo": motivo_input or None,
                })
                if resp and resp.get("id"):
                    st.success(f"{ticker_input} adicionado à watchlist.")
                    st.rerun()
                else:
                    st.error("Erro ao adicionar. Verifique os dados.")

    wl_items = api.get_watchlist()
    render_watchlist(wl_items)

    # ── DIÁRIO ────────────────────────────────────────────────────
    st.markdown(_DIVIDER, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:1rem;font-weight:700;color:{_TXT};margin-bottom:10px">'
        f'Contexto do Diário</div>',
        unsafe_allow_html=True,
    )
    entradas = api.get_diario_recentes(limit=3)
    if entradas:
        for e in entradas:
            st.markdown(_diario_card_html(e), unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="color:{_TXT2};font-size:13px;font-family:{_FONT}">'
            f'Nenhuma decisão registrada ainda.</div>',
            unsafe_allow_html=True,
        )
