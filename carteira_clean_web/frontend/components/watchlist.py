"""Componente de Watchlist — tabela nativa Streamlit (botões funcionam)."""

import streamlit as st

_CARD   = "#1C2333"
_BORDER = "#252D3D"
_TXT    = "#D1D4DC"
_TXT2   = "#787B86"
_OK     = "#26A69A"
_ALERTA = "#F59E0B"
_NEG    = "#EF5350"
_MUTED  = "#6B7280"
_FONT   = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"

_BADGE = {
    "NA_ZONA":  ("NA ZONA",  "#26A69A", "rgba(38,166,154,0.20)"),
    "PROXIMO":  ("PRÓXIMO",  "#F59E0B", "rgba(245,158,11,0.20)"),
    "ACIMA":    ("ACIMA",    "#6B7280", "rgba(107,114,128,0.15)"),
    "SEM_DADOS":("SEM DADOS","#4B5563", "rgba(107,114,128,0.10)"),
}

_WIDTHS  = [1.8, 1.2, 1.3, 1.3, 1.1, 2.8, 0.5]
_HEADERS = ["Ticker", "Alvo", "Cotação", "Distância", "Stop", "Tese", ""]

_RS = "border-bottom:1px solid {b};padding:8px 2px;font-family:{f};font-size:13px;line-height:1.35"


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def render_watchlist(items: list) -> None:
    """Renderiza a tabela de watchlist com botões de remoção nativos."""
    if not items:
        st.markdown(
            f'<div style="color:#4B5563;font-size:13px;font-family:{_FONT};'
            f'text-align:center;padding:28px 0">'
            f'Nenhum ativo na watchlist — adicione abaixo</div>',
            unsafe_allow_html=True,
        )
        return

    # Cabeçalho
    cols = st.columns(_WIDTHS)
    for col, h in zip(cols, _HEADERS):
        with col:
            st.markdown(
                f'<div style="color:{_TXT2};font-size:0.62rem;text-transform:uppercase;'
                f'letter-spacing:0.09em;padding:4px 2px 6px;'
                f'border-bottom:1px solid {_BORDER};font-family:{_FONT}">{h}</div>',
                unsafe_allow_html=True,
            )

    row_s = _RS.format(b=_BORDER, f=_FONT)

    for item in items:
        cotacao = item.get("cotacao_atual")
        alvo    = item["preco_alvo"]
        stop    = item.get("stop_loss")
        sinal   = item.get("sinal", "SEM_DADOS")
        dist    = item.get("distancia_alvo_pct")
        motivo  = item.get("motivo") or "—"

        badge_label, badge_color, badge_bg = _BADGE.get(sinal, _BADGE["SEM_DADOS"])

        # Cor da cotação
        if cotacao is None:
            cor_cot = _TXT2
        elif cotacao <= alvo:
            cor_cot = _OK
        elif cotacao <= alvo * 1.05:
            cor_cot = _ALERTA
        else:
            cor_cot = _MUTED

        # Distância texto
        if dist is not None:
            if dist >= 0:
                dist_txt = f"+{dist:.1f}% upside".replace(".", ",")
                dist_cor = _OK
            else:
                dist_txt = f"{abs(dist):.1f}% acima".replace(".", ",")
                dist_cor = _NEG
        else:
            dist_txt, dist_cor = "—", _TXT2

        tese_trunc = (motivo[:55] + "…") if len(motivo) > 55 else motivo

        cols = st.columns(_WIDTHS)

        with cols[0]:
            st.markdown(
                f'<div style="{row_s}">'
                f'<span style="color:{_TXT};font-weight:600">{item["ticker"]}</span>'
                f'&nbsp;<span style="background:{badge_bg};color:{badge_color};'
                f'font-size:0.58rem;font-weight:600;padding:2px 5px;border-radius:3px;'
                f'letter-spacing:0.04em">{badge_label}</span></div>',
                unsafe_allow_html=True,
            )

        with cols[1]:
            st.markdown(
                f'<div style="{row_s};color:{_TXT}">{_fmt_brl(alvo)}</div>',
                unsafe_allow_html=True,
            )

        with cols[2]:
            cot_html = (
                f'<span style="color:{cor_cot}">{_fmt_brl(cotacao)}</span>'
                if cotacao else f'<span style="color:{_TXT2}">—</span>'
            )
            st.markdown(f'<div style="{row_s}">{cot_html}</div>', unsafe_allow_html=True)

        with cols[3]:
            st.markdown(
                f'<div style="{row_s};color:{dist_cor};font-weight:500">{dist_txt}</div>',
                unsafe_allow_html=True,
            )

        with cols[4]:
            stop_html = (
                f'<span style="color:{_NEG}">{_fmt_brl(stop)}</span>'
                if stop else f'<span style="color:{_TXT2}">—</span>'
            )
            st.markdown(f'<div style="{row_s}">{stop_html}</div>', unsafe_allow_html=True)

        with cols[5]:
            st.markdown(
                f'<div style="{row_s};color:{_TXT2};overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap" '
                f'title="{motivo}">{tese_trunc}</div>',
                unsafe_allow_html=True,
            )

        with cols[6]:
            st.markdown(f'<div style="padding-top:4px">', unsafe_allow_html=True)
            if st.button("×", key=f"wl_rm_{item['id']}", help=f"Remover {item['ticker']}"):
                from carteira_clean_web.frontend.utils import api
                api.delete(f"watchlist/{item['id']}")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
