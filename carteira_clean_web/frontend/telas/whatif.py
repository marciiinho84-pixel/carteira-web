"""
Página: Simulação de Cenários What-If — impacto de choques de mercado no patrimônio.
"""

import streamlit as st
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt

# Cenários pré-definidos: (título, emoji, ibov_pct, usd_pct, selic_delta_pp)
CENARIOS_PRE = [
    ("Crash do IBOV",       "📉", -20,   0,    0),
    ("Alta forte do IBOV",  "📈", +20,   0,    0),
    ("Dólar +15%",          "💵",   0, +15,    0),
    ("Dólar -15%",          "💵",   0, -15,    0),
    ("Selic sobe → 16%",    "🏦",   0,   0,   +3),
    ("Selic cai → 8%",      "🏦",   0,   0,   -5),
]


def _calc_impacto(
    pat_total: float,
    pat_rv: float,
    pat_gerida: float,
    pat_funcef: float,
    posicoes: list,
    beta_ibov: float,
    ibov_pct: float,
    usd_pct: float,
    selic_delta: float,
) -> dict:
    """
    Calcula o impacto aproximado de um choque no patrimônio.

    - IBOV: afeta RV via beta. Sem beta real → usa 0.3 (estimativa conservadora).
    - USD: afeta BDRs diretamente (exposição cambial).
    - Selic: afeta RF (valor de face constante para LCI/FIC → rendimento futuro muda,
      não mark-to-market imediato). Usa sensibilidade simplificada de 0.5 × delta_selic
      sobre o patrimônio RF como penalidade/benefício de oportunidade.
    """
    beta = beta_ibov if beta_ibov is not None else 0.3
    beta_aviso = beta_ibov is None

    # Patrimônio por categoria
    pat_rf = pat_gerida - pat_rv  # Renda Fixa dentro da Gerida
    pat_bdr = sum(
        p["valor_atual"] for p in posicoes
        if p.get("familia") in {"BDR", "BDR de ETF"}
    )

    # Impacto IBOV sobre RV (via beta)
    # impacto_rv = beta × ibov_pct × peso_RV_no_total
    peso_rv = pat_rv / pat_total if pat_total > 0 else 0
    impacto_ibov_abs = pat_total * peso_rv * beta * (ibov_pct / 100)

    # Impacto cambial sobre BDRs
    impacto_usd_abs = pat_bdr * (usd_pct / 100)

    # Impacto Selic sobre RF (simplificado: oportunidade +/-)
    # Subida de selic beneficia RF pós-fixada mas penaliza renda variável via valuations
    impacto_selic_rf = pat_rf * 0.5 * (selic_delta / 100)  # pequena sensibilidade pós-fixada
    impacto_selic_rv = -pat_rv * 0.3 * (selic_delta / 100)  # ações sofrem com selic alta

    impacto_total = impacto_ibov_abs + impacto_usd_abs + impacto_selic_rf + impacto_selic_rv

    return {
        "pat_antes": pat_total,
        "pat_depois": pat_total + impacto_total,
        "impacto_total": impacto_total,
        "impacto_pct": impacto_total / pat_total if pat_total > 0 else 0,
        "impacto_ibov": impacto_ibov_abs,
        "impacto_usd": impacto_usd_abs,
        "impacto_selic": impacto_selic_rf + impacto_selic_rv,
        "beta_usado": beta,
        "beta_aviso": beta_aviso,
    }


def _card_cenario(titulo: str, emoji: str, resultado: dict) -> None:
    imp = resultado["impacto_total"]
    pct = resultado["impacto_pct"]
    cor = "#2ecc71" if imp >= 0 else "#e74c3c"
    seta = "↑" if imp >= 0 else "↓"
    dark = fmt._dark()
    bg = "#1e2130" if dark else "#f0f2f8"
    txt = "#fff" if dark else "#1a1a2e"
    aviso = " ⚠️" if resultado["beta_aviso"] else ""
    st.markdown(
        f"""<div style='background:{bg};border-left:4px solid {cor};
        border-radius:10px;padding:14px 18px;margin-bottom:10px'>
        <div style='color:{cor};font-size:1.1em;font-weight:700'>{emoji} {titulo}{aviso}</div>
        <div style='color:{txt};font-size:0.95em;margin-top:6px'>
          Antes: <b>{fmt.moeda(resultado['pat_antes'])}</b><br>
          Depois: <b style='color:{cor}'>{fmt.moeda(resultado['pat_depois'])}</b><br>
          Impacto: <b style='color:{cor}'>{seta} {fmt.moeda(abs(imp))} ({fmt.pct(abs(pct), casas=2)})</b>
        </div></div>""",
        unsafe_allow_html=True,
    )


def render():
    st.title("🔮 Simulação de Cenários")
    st.caption(
        "Estimativa do impacto de choques de mercado no patrimônio. "
        "Valores aproximados — não consideram correlações entre fatores nem efeitos de segunda ordem."
    )

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    dash = api.get("dashboard")
    posicoes = api.get("posicoes") or []
    if not dash:
        return

    pat_total = dash["patrimonio_total"]
    pat_rv = dash["patrimonio_rv"]
    pat_gerida = dash["patrimonio_gerida"]
    pat_funcef = dash["patrimonio_funcef"]
    beta_ibov = dash.get("beta_ibov")

    # ─── Aviso sobre beta ────────────────────────────────────────
    if beta_ibov is None:
        st.warning(
            "⚠️ Beta indisponível (dados de mercado insuficientes — modo sem API). "
            "Usando estimativa conservadora de **0,30** para a Carteira Gerida."
        )
    else:
        st.info(f"ℹ️ Beta vs IBOV da Carteira Gerida: **{beta_ibov:.2f}** (calculado sobre retornos YTD)")

    # ─── Resumo da carteira ───────────────────────────────────────
    st.subheader("Composição Atual")
    cc1, cc2, cc3, cc4 = st.columns(4)
    pat_rf = pat_gerida - pat_rv
    pat_bdr = sum(p["valor_atual"] for p in posicoes
                  if p.get("familia") in {"BDR", "BDR de ETF"})
    with cc1:
        fmt.card_kpi("Total", fmt.moeda(pat_total))
    with cc2:
        fmt.card_kpi("RV (Ações/ETF)", fmt.moeda(pat_rv),
                     delta=f"{pat_rv/pat_total*100:.1f}%" if pat_total > 0 else "—")
    with cc3:
        fmt.card_kpi("BDRs (exposição USD)", fmt.moeda(pat_bdr),
                     delta=f"{pat_bdr/pat_total*100:.1f}%" if pat_total > 0 else "—")
    with cc4:
        fmt.card_kpi("RF + FUNCEF", fmt.moeda(pat_rf + pat_funcef),
                     delta=f"{(pat_rf+pat_funcef)/pat_total*100:.1f}%" if pat_total > 0 else "—")

    st.divider()

    # ─── Cenários pré-definidos ───────────────────────────────────
    st.subheader("Cenários Pré-Definidos")
    cols1 = st.columns(3)
    cols2 = st.columns(3)
    for idx, (titulo, emoji, ibov, usd, selic) in enumerate(CENARIOS_PRE):
        resultado = _calc_impacto(
            pat_total, pat_rv, pat_gerida, pat_funcef, posicoes,
            beta_ibov, ibov, usd, selic,
        )
        col = (cols1 if idx < 3 else cols2)[idx % 3]
        with col:
            _card_cenario(titulo, emoji, resultado)

    if beta_ibov is None:
        st.caption("⚠️ Beta estimado em 0,30 — ative preços de mercado para cálculo real.")

    st.divider()

    # ─── Cenário customizado ──────────────────────────────────────
    st.subheader("Cenário Customizado")
    cs1, cs2, cs3 = st.columns(3)
    with cs1:
        ibov_custom = st.slider("IBOV (%)", -40, +40, 0, step=1, key="wf_ibov")
    with cs2:
        usd_custom = st.slider("Dólar (%)", -30, +30, 0, step=1, key="wf_usd")
    with cs3:
        selic_custom = st.slider("Selic (Δ p.p.)", -8, +8, 0, step=1, key="wf_selic")

    res_custom = _calc_impacto(
        pat_total, pat_rv, pat_gerida, pat_funcef, posicoes,
        beta_ibov, ibov_custom, usd_custom, selic_custom,
    )

    imp = res_custom["impacto_total"]
    cor = "#2ecc71" if imp >= 0 else "#e74c3c"
    seta = "↑" if imp >= 0 else "↓"

    st.markdown("**Resultado do cenário customizado:**")
    r1, r2, r3 = st.columns(3)
    with r1:
        fmt.card_kpi("Patrimônio Antes", fmt.moeda(res_custom["pat_antes"]))
    with r2:
        fmt.card_kpi("Patrimônio Depois", fmt.moeda(res_custom["pat_depois"]),
                     cor_delta=cor)
    with r3:
        fmt.card_kpi(
            "Impacto Total",
            f"{seta} {fmt.moeda(abs(imp))}",
            delta=f"{fmt.pct(abs(res_custom['impacto_pct']), casas=2)}",
            cor_delta=cor,
        )

    # Decomposição
    st.markdown("**Decomposição do impacto:**")
    d1, d2, d3 = st.columns(3)
    with d1:
        v = res_custom["impacto_ibov"]
        fmt.card_kpi("Via IBOV (beta)", fmt.moeda(v, sinal=True),
                     delta=f"β={res_custom['beta_usado']:.2f}",
                     cor_delta="#2ecc71" if v >= 0 else "#e74c3c")
    with d2:
        v = res_custom["impacto_usd"]
        fmt.card_kpi("Via Dólar (BDRs)", fmt.moeda(v, sinal=True),
                     cor_delta="#2ecc71" if v >= 0 else "#e74c3c")
    with d3:
        v = res_custom["impacto_selic"]
        fmt.card_kpi("Via Selic (RF/RV)", fmt.moeda(v, sinal=True),
                     cor_delta="#2ecc71" if v >= 0 else "#e74c3c")

    st.caption(
        "Metodologia: impacto IBOV = peso RV × β × ΔIBOV; "
        "impacto USD = valor BDRs × ΔUSD; "
        "impacto Selic = sensibilidade simplificada de RF (0,5×Δ) e RV (−0,3×Δ). "
        "Não considera rebalanceamento, correlações cruzadas ou efeitos de segunda ordem."
    )
