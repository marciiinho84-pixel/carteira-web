"""
Página: Dashboard — KPIs executivos + gráfico TWR vs benchmarks.
"""

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt
from carteira_clean_web.frontend.components.kpi_card import kpi_card_html
from carteira_clean_web.frontend.components.tv_chart import tv_dual_chart_html
from carteira_clean_web.frontend.components.donut_chart import donut_alocacao_html

# ─── Design System (TradingView-inspired) ──────────────────────
_CSS = """<style>
.main .block-container { padding-top: 1rem; max-width: 1200px; }
[data-testid="stHorizontalBlock"] { gap: 8px !important; }
[data-testid="column"] { padding: 0 2px !important; }
[data-testid="metric-container"] {
    background: #1C2333; border: 1px solid #252D3D;
    border-radius: 8px; padding: 12px;
}
[data-testid="metric-container"] label {
    color: #787B86 !important; font-size: 0.7rem !important;
    text-transform: uppercase; letter-spacing: 0.08em;
}
[data-testid="metric-container"] [data-testid="metric-value"] {
    color: #D1D4DC !important; font-size: 2rem !important;
    font-weight: 700 !important;
}
</style>"""

_POS   = "#26A69A"
_NEG   = "#EF5350"
_NEUT  = "#6366F1"
_ALERT = "#F59E0B"
_INFO  = "#3B82F6"
_BG2   = "#1C2333"
_BG3   = "#252D3D"
_TXT   = "#D1D4DC"
_TXT2  = "#787B86"


def _plotly_base(**kwargs) -> dict:
    base = dict(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        font=dict(family="Inter,system-ui,sans-serif", color=_TXT, size=12),
        margin=dict(l=40, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(28,35,51,0.8)", bordercolor=_BG3, borderwidth=1),
        xaxis=dict(gridcolor=_BG2, linecolor=_BG3, tickfont=dict(color=_TXT2)),
        yaxis=dict(gridcolor=_BG2, linecolor=_BG3, tickfont=dict(color=_TXT2)),
        hoverlabel=dict(bgcolor=_BG2, bordercolor=_BG3, font_color=_TXT),
    )
    base.update(kwargs)
    return base


def _kpi(titulo: str, valor: str, delta: str = "",
         cor: str = _NEUT, delta_cor: str = _TXT2, min_h: str = "96px") -> None:
    d = (f'<div style="color:{delta_cor};font-size:0.9rem;margin-top:4px">{delta}</div>'
         if delta else "")
    st.markdown(
        f'<div style="background:{_BG2};padding:12px;border-radius:8px;border-left:3px solid {cor};'
        f'margin-bottom:8px;min-height:{min_h};box-sizing:border-box">'
        f'<div style="color:{_TXT2};font-size:0.7rem;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-bottom:5px">{titulo}</div>'
        f'<div style="color:{_TXT};font-size:2rem;font-weight:700;line-height:1.1">{valor}</div>'
        f'{d}</div>',
        unsafe_allow_html=True,
    )


def render():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("🏠 Dashboard")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    dash      = api.get("dashboard")
    evo_data  = api.get("evolucao")
    ir_data   = api.get("ir-mensal") or []
    pos_data  = api.get("posicoes") or []
    prov_data = api.get("proventos-projetados") or {}
    pendentes = api.get("decisoes/pendentes") or []

    if dash is None:
        return

    # ─── Alerta DARF ────────────────────────────────────────────
    if ir_data:
        mes_atual = pd.Timestamp.today().strftime("%Y-%m")
        ir_mes = next((r for r in ir_data if r["mes"] == mes_atual and r["gera_darf"]), None)
        if ir_mes:
            venc = ir_mes.get("darf_vencimento", "?")
            venc_fmt = f"{venc[8:10]}/{venc[5:7]}" if venc and len(venc) >= 10 else venc
            st.error(
                f"🔴 **DARF Código 6015** — "
                f"IR sobre RV: **{fmt.moeda(ir_mes['ir_devido'])}** — "
                f"Vence em **{venc_fmt}** (último dia útil do mês seguinte)"
            )

    # ─── Banner — 3 métricas em linha ───────────────────────────
    var_mercado = dash.get("var_mercado_dia")
    fluxo_dia   = dash.get("fluxo_dia")
    pat_total   = dash.get("patrimonio_total", 0)

    def _banner_seg(label: str, valor_html: str, cor_borda: str, flex: int = 1) -> str:
        return (
            f"<div style='flex:{flex};padding:10px 18px;border-left:3px solid {cor_borda};"
            f"border-radius:6px;background:{_BG2}'>"
            f"<div style='color:{_TXT2};font-size:0.65rem;text-transform:uppercase;"
            f"letter-spacing:0.08em;margin-bottom:4px'>{label}</div>"
            f"<div style='font-size:1.2rem;font-weight:700;line-height:1'>{valor_html}</div>"
            f"</div>"
        )

    # segmento 1 — variação de mercado
    if var_mercado is not None:
        seta_m   = "▲" if var_mercado >= 0 else "▼"
        cor_m    = _POS if var_mercado >= 0 else _NEG
        pct_m = abs(var_mercado / pat_total) if pat_total else 0
        val_m_html = (
            f"<span style='color:{cor_m}'>{seta_m} {fmt.moeda(abs(var_mercado))}</span>"
            f"<span style='color:{_TXT2};font-size:0.82rem;margin-left:6px'>"
            f"({fmt.pct(pct_m, casas=2)})</span>"
        )
        seg1 = _banner_seg("Variação mercado (D-1→D)", val_m_html, cor_m, flex=2)
    else:
        seg1 = _banner_seg("Variação mercado (D-1→D)",
                           f"<span style='color:{_TXT2}'>—</span>", _TXT2, flex=2)

    # segmento 2 — fluxo do dia
    if fluxo_dia is not None and fluxo_dia != 0:
        seta_f    = "+" if fluxo_dia >= 0 else "−"
        cor_f     = _INFO if fluxo_dia >= 0 else _ALERT
        label_f   = "Aporte" if fluxo_dia >= 0 else "Resgate"
        val_f_html = (
            f"<span style='color:{cor_f}'>{seta_f} {fmt.moeda(abs(fluxo_dia))}</span>"
            f"<span style='color:{_TXT2};font-size:0.75rem;margin-left:6px'>{label_f}</span>"
        )
        seg2 = _banner_seg("Fluxo externo do dia", val_f_html, cor_f, flex=2)
    else:
        seg2 = _banner_seg("Fluxo externo do dia",
                           f"<span style='color:{_TXT2}'>—</span>", _BG3, flex=2)

    # segmento 3 — patrimônio total
    val_pat_html = f"<span style='color:{_TXT}'>{fmt.moeda(pat_total)}</span>"
    seg3 = _banner_seg("Patrimônio total", val_pat_html, _NEUT, flex=3)

    st.markdown(
        f"<div style='display:flex;gap:8px;margin-bottom:14px'>{seg1}{seg2}{seg3}</div>",
        unsafe_allow_html=True,
    )

    # ─── LINHA 1 — KPI Cards (Investidor10 style) ───────────────
    twr   = dash["twr_gerida_ytd"]
    exc   = dash["excesso_cdi"]
    pnl   = dash["pnl_vendas_rv"]
    shp   = dash["sharpe"]

    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        components.html(kpi_card_html(
            "PATRIMÔNIO TOTAL",
            fmt.moeda(dash["patrimonio_total"]),
            badge_text=fmt.pct(twr),
            badge_positive=twr >= 0,
            subtitle=f"vs CDI {fmt.pct(dash['cdi_ytd'])}",
        ), height=108)
    with c2:
        components.html(kpi_card_html(
            "TWR GERIDA YTD",
            fmt.pct(twr),
            badge_text=f"exc. {fmt.pct(exc, sinal=True)}",
            badge_positive=exc >= 0,
            subtitle="sobre o CDI",
        ), height=108)
    with c3:
        interp = "Defensivo" if shp < 0.5 else ("Bom" if shp < 1.5 else "Excelente")
        components.html(kpi_card_html(
            "SHARPE YTD",
            f"{shp:.2f}",
            badge_text=interp,
            badge_neutral=True,
            subtitle="risco/retorno ajustado",
        ), height=108)
    with c4:
        components.html(kpi_card_html(
            "P&L VENDAS RV",
            fmt.moeda(pnl, sinal=True),
            badge_text="Lucro" if pnl >= 0 else "Prejuízo",
            badge_positive=pnl >= 0,
            subtitle="ganhos realizados YTD",
        ), height=108)

    st.divider()

    # ─── LINHA 2 — TV Chart (70%) + Donut ECharts (30%) ────────
    col_chart, col_donut = st.columns([7, 3])

    with col_chart:
        if evo_data:
            patrimonio_series = [
                {"time": r["data"], "value": float(r["patrimonio_total"])}
                for r in evo_data if (r.get("patrimonio_total") or 0) > 0
            ]
            twr_series = [
                {"time": r["data"], "value": round(float(r["twr_gerida"]) * 100, 4)}
                for r in evo_data
            ]
            cdi_series = [
                {"time": r["data"], "value": round(float(r["cdi_acum"]) * 100, 4)}
                for r in evo_data
            ]
            ibov_series = [
                {"time": r["data"], "value": round(float(r["ibov_acum"]) * 100, 4)}
                for r in evo_data
            ]
            components.html(
                tv_dual_chart_html(patrimonio_series, twr_series, cdi_series, ibov_series),
                height=510,
            )
        else:
            st.info("Dados de evolução indisponíveis.")

    with col_donut:
        st.markdown(
            f'<div style="color:#787B86;font-size:0.65rem;text-transform:uppercase;'
            f'letter-spacing:0.12em;font-weight:500;margin-bottom:4px">Alocação Gerida</div>',
            unsafe_allow_html=True,
        )
        gerida_classe: dict = {}
        for p in pos_data:
            if p.get("composite") == "Gerida":
                classe = p.get("classe", "Outros")
                gerida_classe[classe] = (
                    gerida_classe.get(classe, 0) + (p.get("valor_atual") or 0)
                )
        if gerida_classe:
            total_gerida = sum(gerida_classe.values())
            components.html(
                donut_alocacao_html(gerida_classe, total_gerida),
                height=490,
            )
        else:
            st.info("Sem posições na carteira gerida.")

    st.divider()

    # ─── Benchmarks YTD (linha compacta) ────────────────────────
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        _kpi("CDI YTD", fmt.pct(dash["cdi_ytd"]), cor=_TXT2)
    with b2:
        v = dash["ibov_ytd"]
        _kpi("IBOV YTD", fmt.pct(v), cor=_POS if v >= 0 else _NEG)
    with b3:
        v = dash["sp500_brl_ytd"]
        _kpi("S&P500 BRL YTD", fmt.pct(v), cor=_POS if v >= 0 else _NEG)
    with b4:
        v = dash.get("twr_rv_ytd", 0)
        _kpi("TWR RV YTD", fmt.pct(v), cor=_POS if v >= 0 else _NEG)

    st.divider()

    # ─── LINHA 3 — Risco & Rendimento + Próximos Proventos ───────
    st.subheader("Risco & Rendimento")
    r1, r2, r3, r4 = st.columns(4)

    with r1:
        dd      = dash.get("drawdown_max")
        dd_data = dash.get("drawdown_max_data")
        if dd is not None:
            dt_str = pd.to_datetime(dd_data).strftime("%d/%m/%Y") if dd_data else ""
            _kpi("Drawdown Máx. YTD", fmt.pct(dd, casas=2),
                 delta=dt_str, cor=_NEG, delta_cor=_TXT2)
        else:
            _kpi("Drawdown Máx. YTD", "—", cor=_TXT2)

    with r2:
        vol = dash.get("vol_anualizada")
        _kpi("Volatilidade a.a.",
             fmt.pct(vol, casas=1) if vol is not None else "—",
             delta="Ref. IBOV ~25%", cor=_NEUT, delta_cor=_TXT2)

    with r3:
        beta = dash.get("beta_ibov")
        if beta is not None:
            interp = (
                "Defensiva" if beta < 0.5 else
                "Moderada"  if beta < 0.8 else
                "Alinhada"  if beta < 1.2 else "Agressiva"
            )
            _kpi("Beta vs IBOV", f"{beta:.2f}",
                 delta=interp, cor=_NEUT, delta_cor=_TXT2)
        else:
            _kpi("Beta vs IBOV", "—", delta="< 20 obs.", cor=_TXT2)

    with r4:
        hoje     = pd.Timestamp.today().normalize()
        limite   = hoje + pd.Timedelta(days=30)
        projecao = prov_data.get("projecao", [])
        proximos = [
            p for p in projecao
            if hoje <= pd.Timestamp(p["data"]) <= limite
        ]
        if proximos:
            total_30d = sum(p["valor"] for p in proximos)
            n = len(proximos)
            _kpi("Próximos Proventos",
                 fmt.moeda(total_30d),
                 delta=f"{n} evento{'s' if n > 1 else ''} nos próximos 30 dias",
                 cor=_POS, delta_cor=_TXT2)
        else:
            historico = prov_data.get("historico", [])
            recentes  = historico[:5]
            if recentes:
                total_rec = sum(p["valor"] for p in recentes)
                _kpi("Últimos Proventos",
                     fmt.moeda(total_rec),
                     delta="histórico — sem previsão disponível",
                     cor=_TXT2, delta_cor=_ALERT)
            else:
                _kpi("Próximos Proventos", "—", cor=_TXT2)

    st.divider()

    # ─── LINHA 4 — Alertas (esq.) + Decisões (dir.) ─────────────
    col_alertas, col_decisoes = st.columns(2)

    with col_alertas:
        alertas = dash.get("alertas", [])
        st.subheader(f"🔔 Alertas ({len(alertas)})")
        if alertas:
            for a in alertas:
                nivel = a["nivel"]
                msg   = f"**{a['ativo']}**: {a['mensagem']}"
                if nivel == "ERRO":
                    st.error(f"🔴 {msg}")
                elif nivel == "AVISO":
                    st.warning(f"🟡 {msg}")
                else:
                    st.info(f"🔵 {msg}")
        else:
            st.markdown(
                f"<div style='color:{_TXT2};font-size:0.9rem;padding:8px 0'>"
                f"Nenhum alerta ativo.</div>",
                unsafe_allow_html=True,
            )

    with col_decisoes:
        st.subheader(f"📓 Decisões ({len(pendentes)})")
        if pendentes:
            for d in pendentes:
                ativo = d.get("ativo", "")
                acao  = d.get("acao", "")
                rev   = d.get("revisao_em", "?")
                st.info(f"**{ativo}** — {acao} · revisão em {rev}")
        else:
            st.markdown(
                f"<div style='color:{_TXT2};font-size:0.9rem;padding:8px 0'>"
                f"Nenhuma decisão pendente.</div>",
                unsafe_allow_html=True,
            )

    # ─── LINHA 5 — Vencimentos RF ────────────────────────────────
    venc_rf = dash.get("vencimentos_rf", [])
    if venc_rf:
        st.divider()
        st.subheader("Vencimentos Renda Fixa")
        linhas = []
        for v in venc_rf:
            anos   = v["dias_restantes"] // 365
            dias_r = v["dias_restantes"] % 365
            prazo  = f"{anos}a {dias_r}d" if anos > 0 else f"{v['dias_restantes']}d"
            dt_fmt = pd.to_datetime(v["data_vencimento"]).strftime("%d/%m/%Y")
            val_str = fmt.moeda(v["valor_atual"]) if v.get("valor_atual") else "—"
            cor_al = (
                _NEG   if v["alerta"] == "CRITICO" else
                _ALERT if v["alerta"] == "ATENCAO" else _POS
            )
            linhas.append(
                f"<tr>"
                f"<td style='padding:6px 10px'><b style='color:{_TXT}'>{v['ticker']}</b></td>"
                f"<td style='padding:6px 10px;color:{cor_al}'>{prazo}</td>"
                f"<td style='padding:6px 10px;color:{_TXT2}'>{dt_fmt}</td>"
                f"<td style='padding:6px 10px;color:{_TXT}'>{val_str}</td>"
                f"</tr>"
            )
        st.markdown(
            f"<div style='background:{_BG2};padding:14px 18px;border-radius:10px;"
            f"border-left:3px solid {_INFO}'>"
            f"<table style='width:100%;font-size:0.88rem;border-collapse:collapse'>"
            f"<tr style='color:{_TXT2};font-size:0.72rem;text-transform:uppercase;"
            f"letter-spacing:0.05em;border-bottom:1px solid {_BG3}'>"
            f"<th style='padding:4px 10px;text-align:left'>Ativo</th>"
            f"<th style='padding:4px 10px;text-align:left'>Prazo</th>"
            f"<th style='padding:4px 10px;text-align:left'>Vencimento</th>"
            f"<th style='padding:4px 10px;text-align:left'>Valor Bruto</th>"
            f"</tr>"
            + "".join(linhas)
            + "</table></div>",
            unsafe_allow_html=True,
        )

    # ─── Proventos ───────────────────────────────────────────────
    st.divider()
    st.subheader("💰 Proventos")

    total_hist = prov_data.get("total_historico", 0)
    total_proj = prov_data.get("total_projetado_12m", 0)
    historico  = prov_data.get("historico", [])
    aviso      = prov_data.get("aviso", "")

    p1, p2, p3 = st.columns(3)
    with p1:
        _kpi("Total recebido", fmt.moeda(total_hist), cor=_POS)
    with p2:
        _kpi("Projeção 12 meses", fmt.moeda(total_proj), cor=_NEUT)
    with p3:
        media_mensal = total_proj / 12 if total_proj else 0
        _kpi("Média mensal projetada", fmt.moeda(media_mensal), cor=_TXT2)

    if aviso:
        st.caption(f"⚠️ {aviso}")

    if historico:
        with st.expander("Ver histórico mensal de proventos"):
            df_prov = pd.DataFrame(historico[-12:])
            if "mes" in df_prov.columns and "total" in df_prov.columns:
                df_prov = df_prov.rename(columns={"mes": "Mês", "total": "Total"})
                df_prov["Total"] = df_prov["Total"].apply(fmt.moeda)
                st.dataframe(df_prov, use_container_width=True, hide_index=True)
