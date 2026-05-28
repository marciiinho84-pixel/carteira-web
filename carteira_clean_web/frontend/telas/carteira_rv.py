"""
Carteira RV — Central de Decisões de Renda Variável.

Responde 3 perguntas na ordem do investidor:
  1. O QUE ACONTECEU? → Bloco A (Pulso) + Bloco B (Heatmap 3 modos)
  2. ONDE ESTOU?      → Bloco C (Concentração) + Bloco D (Agenda)
  3. O QUE FAZER?     → Bloco E (Alertas + Ranking P&L)
  + Blocos F/G/H     → Performance + Caixa + Análise Setorial
"""

from datetime import date, timedelta

import streamlit as st
import streamlit.components.v1 as components

from carteira_clean_web.frontend.utils import api, fmt
from carteira_clean_web.frontend.components.kpi_card import kpi_card_html
from carteira_clean_web.frontend.components.heatmap_posicoes import heatmap_posicoes_html
from carteira_clean_web.frontend.components.ranking_pnl import ranking_pnl_html
from carteira_clean_web.frontend.components.treemap_setorial import treemap_setorial_html
from carteira_clean_web.frontend.components.tv_chart import tv_chart_rv_html

_BG = "rgba(20,25,35,0.7)"
_BORDER = "rgba(37,45,61,0.5)"
_TXT = "#D1D4DC"
_TXT2 = "#6B7280"
_FONT = "-apple-system, BlinkMacSystemFont, 'Inter', sans-serif"
_ALERTA = "#F59E0B"
_CRITICO = "#EF5350"
_OK = "#26A69A"

_TIPOS_AGENDA = ["EX_DIV", "BALANCO", "DIVIDENDO", "PROVENTOS", "OUTRO"]
_LABEL_TIPO = {
    "EX_DIV": "Ex-Dividendo",
    "BALANCO": "Balanço",
    "DIVIDENDO": "Dividendo",
    "PROVENTOS": "Proventos",
    "OUTRO": "Outro",
}


# ─── Helpers HTML ─────────────────────────────────────────────────

def _card_alerta(ticker: str, pnl_pct: float, pnl_rs: float, critico: bool) -> str:
    cor = _CRITICO if critico else _ALERTA
    label = "⚠️ CRÍTICO" if critico else "⚠️ ATENÇÃO"
    return (
        f'<div style="background:rgba(20,25,35,0.6);border-left:3px solid {cor};'
        f'border-radius:6px;padding:8px 12px;margin-bottom:6px;font-family:{_FONT}">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="color:{_TXT};font-weight:600;font-size:14px">{ticker}</span>'
        f'<span style="background:rgba({_hex_to_rgb(cor)},0.18);color:{cor};font-size:11px;'
        f'padding:2px 7px;border-radius:4px">{label}</span></div>'
        f'<div style="color:{_CRITICO};font-size:13px;margin-top:2px">'
        f'{fmt.pct(pnl_pct)} &nbsp;·&nbsp; {fmt.moeda(pnl_rs, sinal=True)}</div>'
        f'</div>'
    )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _concentracao_html(setores: list, top_ativos: list, valor_total: float) -> str:
    cores = [
        '#6366F1', '#26A69A', '#F59E0B', '#EC4899',
        '#3B82F6', '#8B5CF6', '#10B981', '#EF4444',
    ]
    linhas = ""
    for i, s in enumerate(setores[:8]):
        pct = round(s["pct_rv"] * 100, 1)
        cor = cores[i % len(cores)]
        bar_w = max(2, min(100, pct * 5))
        linhas += (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">'
            f'<div style="width:90px;font-size:11px;color:{_TXT2};white-space:nowrap;overflow:hidden;'
            f'text-overflow:ellipsis">{s["nome"]}</div>'
            f'<div style="flex:1;background:#1C2333;border-radius:3px;height:8px">'
            f'<div style="width:{bar_w}%;background:{cor};height:100%;border-radius:3px"></div></div>'
            f'<div style="width:38px;text-align:right;font-size:11px;color:{_TXT};font-weight:600">'
            f'{pct}%</div></div>'
        )

    top_html = ""
    for p in top_ativos[:5]:
        pct = round(p["pct_rv"] * 100, 1)
        cor = _ALERTA if pct > 15 else _TXT
        top_html += (
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:3px 0;border-bottom:1px solid #1C2333;font-size:12px">'
            f'<span style="color:{_TXT}">{p["ticker"]}</span>'
            f'<span style="color:{cor};font-weight:600">{pct}%</span></div>'
        )

    return (
        f'<div style="background:{_BG};border:1px solid {_BORDER};border-radius:10px;'
        f'padding:14px 16px;font-family:{_FONT}">'
        f'<div style="color:{_TXT2};font-size:0.6rem;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin-bottom:12px">Por Setor</div>'
        f'{linhas}'
        f'<div style="color:{_TXT2};font-size:0.6rem;text-transform:uppercase;'
        f'letter-spacing:0.12em;margin:12px 0 8px">Top 5 Posições Individuais</div>'
        f'{top_html}</div>'
    )


def _agenda_html(eventos: list) -> str:
    if not eventos:
        return (
            f'<div style="color:{_TXT2};font-size:13px;font-family:{_FONT};'
            f'padding:20px;text-align:center">Nenhum evento cadastrado nos próximos 30 dias.'
            f'<br/><small>Use o formulário abaixo para adicionar.</small></div>'
        )

    hoje = date.today()
    em_7d = hoje + timedelta(days=7)
    linhas = ""
    for ev in eventos:
        ev_date = date.fromisoformat(ev["data"]) if isinstance(ev["data"], str) else ev["data"]
        urgente = ev_date <= em_7d
        dias_r = (ev_date - hoje).days
        dias_label = "hoje" if dias_r == 0 else f"em {dias_r}d"
        cor_data = _ALERTA if urgente else _TXT2
        tipo_label = _LABEL_TIPO.get(ev["tipo"], ev["tipo"])
        desc_html = (f'<br/><span style="color:{_TXT2};font-size:11px">{ev["descricao"]}</span>'
                     if ev.get("descricao") else "")
        urgente_html = (f'<span style="background:rgba(245,158,11,0.18);color:{_ALERTA};'
                        f'font-size:10px;padding:1px 6px;border-radius:4px">7d</span>'
                        if urgente else "")
        linhas += (
            f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;'
            f'border-bottom:1px solid #1C2333;font-family:{_FONT}">'
            f'<div style="min-width:72px">'
            f'<div style="color:{cor_data};font-size:12px;font-weight:600">'
            f'{ev_date.strftime("%d/%m")}</div>'
            f'<div style="color:{_TXT2};font-size:10px">{dias_label}</div></div>'
            f'<div style="flex:1">'
            f'<span style="color:{_TXT};font-size:13px;font-weight:600">{ev["ativo"]}</span>'
            f' <span style="color:{_TXT2};font-size:11px">· {tipo_label}</span>'
            f'{desc_html}</div>'
            f'{urgente_html}'
            f'</div>'
        )

    return (
        f'<div style="background:{_BG};border:1px solid {_BORDER};border-radius:10px;'
        f'padding:14px 16px">{linhas}</div>'
    )


def _caixa_html(caixa: dict) -> str:
    saldo = caixa["projetado"]
    cor_saldo = _OK if saldo >= 0 else _CRITICO
    poder_compra = fmt.moeda(abs(saldo)) + (" disponível" if saldo >= 0 else " déficit")

    def _row(label, valor, cor=_TXT, bold=False):
        fw = "700" if bold else "400"
        return (
            f'<tr><td style="color:{_TXT2};padding:4px 0;font-size:13px">{label}</td>'
            f'<td style="text-align:right;color:{cor};padding:4px 0;font-size:13px;'
            f'font-weight:{fw}">{valor}</td></tr>'
        )

    return (
        f'<div style="background:{_BG};border:1px solid {_BORDER};border-radius:10px;'
        f'padding:14px 18px;font-family:{_FONT}">'
        f'<table style="width:100%;border-collapse:collapse">'
        + _row("Caixa FIC FUNC", fmt.moeda(caixa["atual"]))
        + _row("Entrando D+2", "+" + fmt.moeda(caixa["entrando_d2"]), _OK)
        + _row("Saindo D+2", "−" + fmt.moeda(caixa["saindo_d2"]), _CRITICO)
        + f'<tr style="border-top:1px solid #1C2333"><td style="padding-top:8px;color:{_TXT};'
        f'font-size:13px;font-weight:700">Saldo projetado</td>'
        f'<td style="text-align:right;padding-top:8px;color:{cor_saldo};font-size:13px;'
        f'font-weight:700">{fmt.moeda(abs(saldo))}</td></tr>'
        + '</table>'
        + f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid #1C2333;'
        f'color:{_TXT2};font-size:11px">Poder de compra: '
        f'<span style="color:{cor_saldo};font-weight:600">{poder_compra}</span></div>'
        + '</div>'
    )


def _diario_card_html(e: dict) -> str:
    ativo = e.get("ativo", "")
    acao = e.get("acao", "")
    tese = e.get("tese", "")
    data_d = e.get("data_decisao", "")
    return (
        f'<div style="background:rgba(20,25,35,0.6);border:1px solid {_BORDER};'
        f'border-radius:8px;padding:10px 14px;margin-bottom:6px;font-family:{_FONT};'
        f'color:{_TXT};font-size:13px">'
        f'<span style="color:{_TXT2};font-size:11px">{data_d}</span>'
        f' · <b>{ativo}</b> · {acao}'
        f'<div style="margin-top:4px;font-size:12px;color:#9CA3AF">'
        f'{tese[:140]}{"…" if len(tese) > 140 else ""}</div></div>'
    )


# ─── Render principal ─────────────────────────────────────────────

def render():
    st.title("📈 Carteira RV")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira. Verifique se a API está rodando.")
        return

    dados = api.get_carteira_rv_dados()
    if dados is None:
        return

    posicoes = dados["posicoes"]
    valor_rv = dados["valor_atual"]

    # ─── BLOCO A — PULSO DO DIA ──────────────────────────────────
    var_pct = dados["variacao_dia_pct"]
    var_rs = dados["variacao_dia_valor"]

    # Banner de atenção se var > 3%
    movers_extremos = [p for p in posicoes if abs(p.get("variacao_dia_pct", 0)) > 0.05]
    if movers_extremos:
        nomes = ", ".join(p["ticker"] for p in movers_extremos[:3])
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

    # ─── BLOCO B — HEATMAP (3 abas) ──────────────────────────────
    st.markdown(
        "##### Mapa de Posições"
        "<br><small style='color:#6B7280'>Selecione a dimensão de análise</small>",
        unsafe_allow_html=True,
    )
    tab_dia, tab_pnl, tab_peso = st.tabs(["📅 Variação Hoje", "💰 P&L Total", "📊 Concentração"])

    with tab_dia:
        components.html(heatmap_posicoes_html(posicoes, mode="dia"), height=320)
    with tab_pnl:
        components.html(heatmap_posicoes_html(posicoes, mode="pnl"), height=320)
    with tab_peso:
        components.html(heatmap_posicoes_html(posicoes, mode="tamanho"), height=320)

    # ─── BLOCOS C + D — CONCENTRAÇÃO | AGENDA ────────────────────
    col_conc, col_agenda = st.columns([2, 3])

    with col_conc:
        st.markdown("##### Concentração")
        st.markdown(
            _concentracao_html(dados["setores"], dados["top_concentracao"], valor_rv),
            unsafe_allow_html=True,
        )

    with col_agenda:
        st.markdown("##### Agenda — próximos 30 dias")
        eventos_agenda = api.get_agenda_eventos(dias=30)
        st.markdown(_agenda_html(eventos_agenda), unsafe_allow_html=True)

        with st.expander("➕ Adicionar evento"):
            rv_tickers = sorted({p["ticker"] for p in posicoes})
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                ag_ativo = st.selectbox("Ativo", rv_tickers, key="ag_ativo")
                ag_tipo = st.selectbox("Tipo", _TIPOS_AGENDA, key="ag_tipo",
                                       format_func=lambda x: _LABEL_TIPO.get(x, x))
            with c2:
                ag_data = st.date_input("Data", value=date.today() + timedelta(days=7),
                                        format="DD/MM/YYYY", key="ag_data")
                ag_desc = st.text_input("Descrição (opcional)", key="ag_desc")
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Salvar", key="ag_btn", use_container_width=True):
                    res = api.criar_agenda_evento(str(ag_data), ag_ativo, ag_tipo, ag_desc)
                    if res:
                        st.success("Evento salvo!")
                        st.rerun()

        # Botão remover (se houver eventos)
        if eventos_agenda:
            with st.expander("🗑️ Remover evento"):
                ops = {f"{e['data']} · {e['ativo']} · {_LABEL_TIPO.get(e['tipo'],e['tipo'])}": e["id"]
                       for e in eventos_agenda}
                sel = st.selectbox("Selecione", list(ops.keys()), key="ag_rm_sel")
                if st.button("Remover", key="ag_rm_btn"):
                    api.deletar_agenda_evento(ops[sel])
                    st.success("Removido!")
                    st.rerun()

    # ─── BLOCO E — PAINEL DE AÇÃO ────────────────────────────────
    st.markdown("##### Painel de Ação")
    col_alertas, col_ranking = st.columns([2, 3])

    THRESH_ATENCAO = -0.15
    THRESH_CRITICO = -0.25

    with col_alertas:
        alertas = [p for p in posicoes if p.get("pl_total_pct", 0) < THRESH_ATENCAO]
        alertas_sorted = sorted(alertas, key=lambda p: p["pl_total_pct"])

        if alertas_sorted:
            st.markdown(
                f"<div style='color:{_TXT2};font-size:11px;margin-bottom:8px'>"
                f"Posições com P&L abaixo de {fmt.pct(THRESH_ATENCAO)} do custo</div>",
                unsafe_allow_html=True,
            )
            for p in alertas_sorted:
                critico = p["pl_total_pct"] < THRESH_CRITICO
                st.markdown(
                    _card_alerta(p["ticker"], p["pl_total_pct"], p["pl_total_rs"], critico),
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f'<div style="background:rgba(38,166,154,0.1);border:1px solid rgba(38,166,154,0.3);'
                f'border-radius:8px;padding:16px;text-align:center;color:{_OK};font-family:{_FONT};'
                f'font-size:13px">✓ Nenhuma posição abaixo de {fmt.pct(THRESH_ATENCAO)}</div>',
                unsafe_allow_html=True,
            )

    with col_ranking:
        st.markdown(
            f"<div style='color:{_TXT2};font-size:11px;margin-bottom:4px'>"
            "Top 5 winners · Top 5 losers (P&L acumulado)</div>",
            unsafe_allow_html=True,
        )
        n_pos = len(posicoes)
        top_n = min(5, n_pos // 2) if n_pos >= 4 else 2
        ht_ranking = (top_n * 2 + 1) * 28 + 40
        components.html(ranking_pnl_html(posicoes, top_n=top_n), height=ht_ranking)

    # ─── BLOCOS F + G — PERFORMANCE | CAIXA ─────────────────────
    col_perf, col_caixa = st.columns([3, 2])

    with col_perf:
        st.markdown("##### Performance RV vs benchmarks")
        components.html(
            tv_chart_rv_html(dados["performance_serie"], markers=dados.get("markers", [])),
            height=245,
        )

    with col_caixa:
        st.markdown("##### Caixa operacional")
        st.markdown(_caixa_html(dados["caixa"]), unsafe_allow_html=True)

    # ─── BLOCO H — ANÁLISE SETORIAL ──────────────────────────────
    st.markdown(
        "##### Análise setorial"
        "<br><small style='color:#6B7280'>setor → ativos · clique para ampliar</small>",
        unsafe_allow_html=True,
    )
    components.html(treemap_setorial_html(dados["setores"]), height=400)

    # ─── PLACEHOLDERS FASE B / C ─────────────────────────────────
    col_sinais, col_watch = st.columns(2)

    with col_sinais:
        st.markdown("##### 📡 Sinais técnicos")
        st.markdown(
            f'<div style="background:rgba(20,25,35,0.4);border:1px dashed rgba(99,102,241,0.3);'
            f'border-radius:10px;padding:32px;text-align:center;color:{_TXT2};font-size:12px;'
            f'font-family:{_FONT}">RSI · MACD · médias móveis<br/>'
            f'<span style="font-size:11px;opacity:0.8">Próxima fase (C)</span></div>',
            unsafe_allow_html=True,
        )

    with col_watch:
        st.markdown("##### 👁️ Watchlist")
        st.markdown(
            f'<div style="background:rgba(20,25,35,0.4);border:1px dashed rgba(99,102,241,0.3);'
            f'border-radius:10px;padding:32px;text-align:center;color:{_TXT2};font-size:12px;'
            f'font-family:{_FONT}">Ativos monitorados · alvo · distância<br/>'
            f'<span style="font-size:11px;opacity:0.8">Próxima fase (B)</span></div>',
            unsafe_allow_html=True,
        )

    # ─── DIÁRIO ──────────────────────────────────────────────────
    st.markdown("##### Contexto do diário")
    entradas = api.get_diario_recentes(limit=3)
    if entradas:
        for e in entradas:
            st.markdown(_diario_card_html(e), unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div style="color:{_TXT2};font-size:13px;font-family:{_FONT}">'
            "Nenhuma decisão registrada ainda.</div>",
            unsafe_allow_html=True,
        )
