"""Componente de Sinais Técnicos — tabela HTML com sub-linha de fundamentalistas."""

_BG      = "rgba(15,17,23,0.6)"
_BORDER  = "#1C2333"
_TXT     = "#D1D4DC"
_TXT2    = "#6B7280"
_VERDE   = "#26A69A"
_VERMELHO = "#EF5350"
_AMBAR   = "#F59E0B"
_CINZA   = "#4B5563"
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


# ── Cores por faixa de fundamentalistas ──────────────────────────

def _cor_pl(v) -> str:
    if v is None: return _TXT2
    if v < 0: return _VERMELHO
    if v < 10: return _VERDE
    if v <= 25: return _TXT
    return _AMBAR


def _cor_pvp(v) -> str:
    if v is None: return _TXT2
    if v < 1: return _VERDE
    if v <= 3: return _TXT
    return _AMBAR


def _cor_ev_ebitda(v) -> str:
    if v is None: return _TXT2
    if v < 8: return _VERDE
    if v <= 15: return _TXT
    return _AMBAR


def _cor_roe(v) -> str:
    if v is None: return _TXT2
    if v < 0: return _VERMELHO
    if v < 10: return _AMBAR
    if v <= 20: return _TXT
    return _VERDE


def _cor_margem(v) -> str:
    if v is None: return _TXT2
    if v < 0: return _VERMELHO
    if v < 5: return _AMBAR
    if v < 10: return "#9CA3AF"
    if v <= 20: return _TXT
    return _VERDE


def _cor_div_ebitda(v) -> str:
    if v is None: return _TXT2
    if v < 1.5: return _VERDE
    if v <= 3: return _TXT
    if v <= 5: return _AMBAR
    return _VERMELHO


def _fmt_metrica(label: str, val, cor: str, sufixo: str = "", ndigits: int = 1) -> str:
    if val is None:
        return f'<span style="color:{_TXT2};font-size:10.5px">{label}</span> <span style="color:{_CINZA}">—</span>'
    v = f"{val:.{ndigits}f}"
    return (
        f'<span style="color:{_TXT2};font-size:10.5px">{label}</span> '
        f'<span style="color:{cor};font-weight:500">{v}{sufixo}</span>'
    )


def _fund_subrow(fund: dict) -> str:
    """Gera o conteúdo HTML da sub-linha fundamentalista."""
    if not fund:
        return f'<span style="color:{_CINZA};font-size:10px;font-style:italic">—</span>'

    pl = fund.get("pl")
    pvp = fund.get("pvp")
    ev = fund.get("ev_ebitda")
    roe = fund.get("roe")
    mg = fund.get("margem_liq")
    dv = fund.get("div_ebitda")
    erro = fund.get("erro")

    tem_dados = any(x is not None for x in [pl, pvp, ev, roe, mg, dv])
    if not tem_dados:
        msg = erro or "Sem dados fundamentais"
        return f'<span style="color:{_CINZA};font-size:10px;font-style:italic">{msg}</span>'

    partes = [
        f'<span style="color:{_TXT2};font-size:10px;font-weight:600;letter-spacing:0.04em">Fund:</span>',
        _fmt_metrica("P/L", pl, _cor_pl(pl)),
        _fmt_metrica("P/VP", pvp, _cor_pvp(pvp), ndigits=2),
        _fmt_metrica("EV/EBITDA", ev, _cor_ev_ebitda(ev)),
        _fmt_metrica("ROE", roe, _cor_roe(roe), sufixo="%"),
        _fmt_metrica("Marg", mg, _cor_margem(mg), sufixo="%"),
        _fmt_metrica("Dív", dv, _cor_div_ebitda(dv), sufixo="x"),
    ]
    return " &nbsp;<span style='color:#374151'>·</span>&nbsp; ".join(partes)


# ── Tabela principal ──────────────────────────────────────────────

def sinais_html(sinais: list, titulo: str = "") -> str:
    """Tabela HTML de sinais técnicos + sub-linha fundamentalista.
    Só exibe linhas com tem_sinal_ativo == True."""
    ativos = [s for s in (sinais or []) if s.get("tem_sinal_ativo")]

    container_ini = (
        f'<div style="background:{_BG};border:1px solid {_BORDER};'
        f'border-radius:10px;padding:12px;font-family:{_FONT}">'
    )
    if not ativos:
        return container_ini + _vazio() + "</div>"

    css = (
        "<style>"
        ".sg-tbl{width:100%;border-collapse:collapse}"
        ".sg-th{color:#6B7280;font-size:10px;text-transform:uppercase;"
        "letter-spacing:0.06em;text-align:left;padding:4px 8px 8px;"
        f"border-bottom:1px solid {_BORDER}}}"
        ".sg-td{padding:10px 8px 4px;font-size:11.5px;vertical-align:middle}"
        f".sg-fund td{{padding:2px 8px 10px;border-bottom:1px solid {_BORDER}}}"
        ".sg-grupo:hover td{background:rgba(28,35,51,0.5)}"
        "</style>"
    )

    ths = "".join(f'<th class="sg-th">{h}</th>' for h in _HEADERS)
    grupos = []
    for s in ativos:
        # Fonte badge
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

        # Sinal combinado badge
        comb = s.get("combinado", {})
        comb_cor = comb.get("cor", _TXT2)
        comb_html = (
            f'<span style="background:{_hex_to_rgba(comb_cor, 0.20)};color:{comb_cor};'
            f'font-weight:700;font-size:11px;padding:3px 9px;border-radius:5px;'
            f'white-space:nowrap">{comb.get("label", "—")}</span>'
        )

        # Linha técnica
        linha_tec = (
            f'<tr>'
            f'<td class="sg-td" style="color:{_TXT};font-weight:600;font-size:13px">{s.get("ticker", "")}</td>'
            f'<td class="sg-td">{fonte_html}</td>'
            f'<td class="sg-td" style="color:{s.get("rsi_cor", _TXT2)}">{s.get("rsi_label", "—")}</td>'
            f'<td class="sg-td" style="color:{s.get("macd_cor", _TXT2)}">{s.get("macd_label", "—")}</td>'
            f'<td class="sg-td" style="color:{s.get("mm_cor", _TXT2)}">{s.get("mm_label", "—")}</td>'
            f'<td class="sg-td">{comb_html}</td>'
            f'</tr>'
        )

        # Sub-linha fundamentalista
        fund_content = _fund_subrow(s.get("fund", {}))
        linha_fund = (
            f'<tr class="sg-fund-row">'
            f'<td colspan="6" style="padding:2px 8px 10px;'
            f'border-bottom:1px solid {_BORDER};font-size:11px">'
            f'{fund_content}</td>'
            f'</tr>'
        )

        grupos.append(f'<tbody class="sg-grupo">{linha_tec}{linha_fund}</tbody>')

    tabela = (
        f'<table class="sg-tbl"><thead><tr>{ths}</tr></thead>'
        f'{"".join(grupos)}</table>'
    )
    return css + container_ini + tabela + "</div>"
