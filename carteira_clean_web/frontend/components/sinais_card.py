"""Componente de Sinais Técnicos — tabela HTML (RSI · MACD · MM · Sinal)."""

_BG      = "rgba(15,17,23,0.6)"
_BORDER  = "#1C2333"
_TXT     = "#D1D4DC"
_TXT2    = "#6B7280"
_FONT    = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"

_FONTE_BADGE = {
    "posicao":   ("POSIÇÃO",   "#6366F1", "rgba(99,102,241,0.15)"),
    "watchlist": ("WATCHLIST", "#F59E0B", "rgba(245,158,11,0.15)"),
    "ambos":     ("AMBOS",     "#26A69A", "rgba(38,166,154,0.15)"),
}

_HEADERS = ["Ticker", "Fonte", "RSI", "MACD", "Médias móveis", "Sinal"]


def _hex_to_rgba(hex_cor: str, alpha: float) -> str:
    h = hex_cor.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _vazio() -> str:
    return (
        f'<div style="text-align:center;padding:24px;color:#4B5563;'
        f'font-size:12px;font-family:{_FONT}">'
        f'Nenhum sinal ativo no momento<br/>'
        f'<span style="font-size:11px;opacity:0.7">'
        f'RSI, MACD e médias móveis em zona neutra para todos os ativos</span></div>'
    )


def sinais_html(sinais: list, titulo: str = "") -> str:
    """Tabela HTML de sinais técnicos. Só exibe linhas com tem_sinal_ativo."""
    ativos = [s for s in (sinais or []) if s.get("tem_sinal_ativo")]

    container_ini = (
        f'<div style="background:{_BG};border:1px solid {_BORDER};'
        f'border-radius:10px;padding:12px;font-family:{_FONT}">'
    )
    if not ativos:
        return container_ini + _vazio() + "</div>"

    css = (
        "<style>"
        ".sg-row:hover{background:rgba(28,35,51,0.5)}"
        ".sg-tbl{width:100%;border-collapse:collapse}"
        ".sg-th{color:#6B7280;font-size:10px;text-transform:uppercase;"
        "letter-spacing:0.06em;text-align:left;padding:4px 8px 8px;"
        f"border-bottom:1px solid {_BORDER}}}"
        ".sg-td{padding:10px 8px;border-bottom:1px solid " + _BORDER +
        ";font-size:11.5px;vertical-align:middle}"
        "</style>"
    )

    ths = "".join(f'<th class="sg-th">{h}</th>' for h in _HEADERS)
    linhas = []
    for s in ativos:
        fonte = s.get("fonte")
        if fonte in _FONTE_BADGE:
            fl, fc, fbg = _FONTE_BADGE[fonte]
            fonte_html = (
                f'<span style="background:{fbg};color:{fc};font-size:9.5px;'
                f'font-weight:600;padding:2px 6px;border-radius:4px;'
                f'letter-spacing:0.03em">{fl}</span>'
            )
        else:
            fonte_html = f'<span style="color:{_TXT2}">—</span>'

        comb = s.get("combinado", {})
        comb_cor = comb.get("cor", _TXT2)
        comb_html = (
            f'<span style="background:{_hex_to_rgba(comb_cor, 0.20)};color:{comb_cor};'
            f'font-weight:700;font-size:11px;padding:3px 9px;border-radius:5px;'
            f'white-space:nowrap">{comb.get("label", "—")}</span>'
        )

        linhas.append(
            f'<tr class="sg-row">'
            f'<td class="sg-td" style="color:{_TXT};font-weight:600;font-size:13px">{s.get("ticker", "")}</td>'
            f'<td class="sg-td">{fonte_html}</td>'
            f'<td class="sg-td" style="color:{s.get("rsi_cor", _TXT2)}">{s.get("rsi_label", "—")}</td>'
            f'<td class="sg-td" style="color:{s.get("macd_cor", _TXT2)}">{s.get("macd_label", "—")}</td>'
            f'<td class="sg-td" style="color:{s.get("mm_cor", _TXT2)}">{s.get("mm_label", "—")}</td>'
            f'<td class="sg-td">{comb_html}</td>'
            f'</tr>'
        )

    tabela = (
        f'<table class="sg-tbl"><thead><tr>{ths}</tr></thead>'
        f'<tbody>{"".join(linhas)}</tbody></table>'
    )
    return css + container_ini + tabela + "</div>"
