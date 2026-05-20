"""
Página: Proventos — histórico realizado + projeção dos próximos 12 meses.
"""

import streamlit as st
import pandas as pd

from carteira_clean_web.frontend.utils import api, fmt


def render():
    st.title("📅 Proventos")

    if not api.garantir_calculado():
        st.warning("Não foi possível calcular a carteira.")
        return

    data = api.get("proventos-projetados")
    if data is None:
        return

    total_hist = data.get("total_historico", 0)
    total_proj = data.get("total_projetado_12m", 0)
    meses_base = data.get("meses_base", 1)
    aviso = data.get("aviso", "")
    historico = data.get("historico", [])
    projecao = data.get("projecao", [])

    # ─── Resumo ───────────────────────────────────────────────────
    st.subheader("Resumo")
    k1, k2, k3 = st.columns(3)
    with k1:
        fmt.card_kpi("Total Recebido (histórico)", fmt.moeda(total_hist))
    with k2:
        fmt.card_kpi(
            "Projeção 12 meses",
            fmt.moeda(total_proj),
            delta=f"~{fmt.moeda(total_proj / 12)}/mês",
            cor_delta="#2ecc71",
        )
    with k3:
        fmt.card_kpi(
            "Base histórica",
            f"{meses_base:.1f} meses",
            delta="usada para calcular média mensal",
            cor_delta="#aaa",
        )

    if aviso:
        st.info(f"ℹ️ {aviso}")

    st.divider()

    # ─── Histórico realizado ───────────────────────────────────────
    st.subheader("Histórico Realizado")
    if historico:
        df_hist = pd.DataFrame(historico)
        df_hist["data"] = pd.to_datetime(df_hist["data"]).dt.strftime("%d/%m/%Y")
        df_hist["valor"] = df_hist["valor"].apply(lambda v: fmt.moeda(v))
        df_hist = df_hist.rename(columns={
            "data": "Data", "ativo": "Ativo", "familia": "Família",
            "tipo": "Tipo", "valor": "Valor", "status": "Status",
        })
        st.dataframe(
            df_hist[["Data", "Ativo", "Família", "Tipo", "Valor", "Status"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nenhum provento registrado no histórico.")

    st.divider()

    # ─── Projeção 12 meses ────────────────────────────────────────
    st.subheader("Projeção — Próximos 12 Meses")
    if projecao:
        df_proj = pd.DataFrame(projecao)
        df_proj["data"] = pd.to_datetime(df_proj["data"]).dt.strftime("%m/%Y")
        df_proj["valor"] = df_proj["valor"].apply(lambda v: fmt.moeda(v))
        df_proj = df_proj.rename(columns={
            "data": "Mês/Ano", "ativo": "Ativo", "familia": "Família",
            "tipo": "Tipo", "valor": "Valor Estimado", "status": "Status",
        })
        st.dataframe(
            df_proj[["Mês/Ano", "Ativo", "Família", "Tipo", "Valor Estimado", "Status"]],
            use_container_width=True,
            hide_index=True,
        )

        # Resumo mensal agregado
        st.divider()
        st.subheader("Total Projetado por Mês")
        df_raw = pd.DataFrame(projecao)
        df_raw["mes"] = pd.to_datetime(df_raw["data"]).dt.strftime("%m/%Y")
        df_mensal = (
            df_raw.groupby("mes", sort=False)["valor"]
            .sum()
            .reset_index()
            .rename(columns={"mes": "Mês/Ano", "valor": "Total Estimado"})
        )
        df_mensal["Total Estimado"] = df_mensal["Total Estimado"].apply(fmt.moeda)
        st.dataframe(df_mensal, use_container_width=True, hide_index=True)
    else:
        st.info("Sem histórico de proventos suficiente para projeção.")
