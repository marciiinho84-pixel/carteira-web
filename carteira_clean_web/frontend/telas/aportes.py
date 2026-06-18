"""
Página: Disciplina de Aporte — gerenciamento da regra de aporte e histórico.
"""

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

TIPOS = ["PROGRAMADO", "OPORTUNISTICO", "MISTO"]


def render():
    st.title("💰 Disciplina de Aporte")
    st.caption("Defina sua regra de aporte mensal e acompanhe o histórico.")

    abas = st.tabs(["⚙️ Regra de Aporte", "📜 Histórico de Regras"])

    # ─── Aba 1: Regra Ativa ───────────────────────────────────────
    with abas[0]:
        regra_ativa = api.get("regra-aportes/ativa")

        if regra_ativa:
            st.info(
                f"Regra ativa desde **{regra_ativa.get('data_criacao', '?')}** — "
                f"alvo: **{fmt.moeda(regra_ativa.get('valor_mensal_alvo', 0))}** · "
                f"tipo: **{regra_ativa.get('tipo', '—')}**"
            )

        st.markdown("#### ⚙️ Configurar Regra")

        valor_atual = float(regra_ativa.get("valor_mensal_alvo", 0.0)) if regra_ativa else 0.0
        tipo_atual = regra_ativa.get("tipo", "PROGRAMADO") if regra_ativa else "PROGRAMADO"
        criterio_atual = regra_ativa.get("criterio_oportunismo", "") if regra_ativa else ""

        valor = st.number_input(
            "Valor mensal alvo (R$) *",
            min_value=0.0,
            value=valor_atual,
            step=100.0,
            format="%.2f",
            key="ap_valor",
        )
        tipo = st.selectbox(
            "Tipo *",
            options=TIPOS,
            index=TIPOS.index(tipo_atual) if tipo_atual in TIPOS else 0,
            key="ap_tipo",
        )

        criterio = ""
        if tipo in ("MISTO", "OPORTUNISTICO"):
            criterio = st.text_area(
                "Critério de oportunismo",
                value=criterio_atual,
                placeholder="Ex: aportar extra quando queda > 5% em ativo da carteira",
                key="ap_criterio",
            )

        pode_salvar = valor > 0
        if st.button("💾 Salvar Regra", type="primary", disabled=not pode_salvar, key="ap_btn_salvar"):
            payload = {
                "valor_mensal_alvo": valor,
                "tipo": tipo,
                "criterio_oportunismo": criterio.strip() or None,
            }
            if regra_ativa:
                res = api.patch(f"regra-aportes/{regra_ativa['id']}", data=payload)
            else:
                res = api.post("regra-aportes", data=payload)

            if res is not None:
                st.success("✅ Regra de aporte salva!")
                st.rerun()

        if regra_ativa is None:
            st.caption("Nenhuma regra ativa. Preencha acima para criar a primeira.")

    # ─── Aba 2: Histórico ─────────────────────────────────────────
    with abas[1]:
        todas = api.get("regra-aportes") or []

        if not todas:
            st.info("Nenhuma regra registrada ainda.")
        else:
            rows = []
            for r in todas:
                rows.append({
                    "Criada em": r.get("data_criacao", "—"),
                    "Valor alvo": fmt.moeda(r.get("valor_mensal_alvo", 0)),
                    "Tipo": r.get("tipo", "—"),
                    "Ativa": "✅" if r.get("ativo") else "—",
                    "Critério": (r.get("criterio_oportunismo") or "—")[:60],
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
