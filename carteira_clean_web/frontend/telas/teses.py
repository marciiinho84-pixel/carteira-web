"""
Página: Teses de Investimento — gerenciamento de teses com critérios de invalidação.
"""

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

BLOCOS_IPS = ["", "SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS"]
NIVEIS = ["VERDE", "AMARELO", "VERMELHO"]
NIVEL_ICONE = {"VERDE": "🟢", "AMARELO": "🟡", "VERMELHO": "🔴"}


def render():
    st.title("🎯 Teses de Investimento")
    st.caption("Registre e monitore suas teses com critérios claros de invalidação.")

    ativos_lista = api.get("ativos") or []
    tickers = sorted(a["ticker"] for a in ativos_lista if a.get("ticker"))

    abas = st.tabs(["✏️ Nova Tese", "📋 Teses Ativas"])

    # ─── Aba 1: Nova Tese ─────────────────────────────────────────
    with abas[0]:
        st.markdown("#### ✏️ Nova Tese")

        c1, c2 = st.columns(2)
        with c1:
            ticker = st.selectbox("Ativo *", options=tickers, key="ts_ticker")
            bloco = st.selectbox(
                "Bloco IPS",
                options=BLOCOS_IPS,
                format_func=lambda x: "— (sem bloco)" if x == "" else x,
                key="ts_bloco",
            )
        with c2:
            nivel = st.selectbox(
                "Nível inicial",
                options=NIVEIS,
                format_func=lambda x: f"{NIVEL_ICONE[x]} {x}",
                key="ts_nivel",
            )

        racional = st.text_area(
            "Racional *",
            height=120,
            placeholder="Por que este ativo? Qual a tese central?",
            key="ts_racional",
        )
        cenario = st.text_area(
            "Cenário esperado",
            height=80,
            placeholder="O que precisa acontecer para a tese se confirmar?",
            key="ts_cenario",
        )
        criterio = st.text_area(
            "Critério de invalidação",
            height=80,
            placeholder="O que invalidaria esta tese?",
            key="ts_criterio",
        )

        pode_salvar = bool(ticker and racional.strip())
        if st.button("💾 Salvar Tese", type="primary", disabled=not pode_salvar, key="ts_btn_salvar"):
            payload = {
                "ticker": ticker,
                "bloco_ips": bloco or None,
                "racional": racional.strip(),
                "cenario_esperado": cenario.strip() or None,
                "criterio_invalidacao": criterio.strip() or None,
                "nivel_invalidacao": nivel,
            }
            res = api.post("teses", data=payload)
            if res is not None:
                st.success(f"✅ Tese para **{ticker}** registrada!")
                for k in ["ts_ticker", "ts_bloco", "ts_nivel", "ts_racional", "ts_cenario", "ts_criterio"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ─── Aba 2: Teses Ativas ──────────────────────────────────────
    with abas[1]:
        teses = api.get("teses") or []
        ativas = [t for t in teses if t.get("status") == "ATIVA"]

        if not ativas:
            st.info("Nenhuma tese ativa registrada.")
        else:
            rows = []
            for t in ativas:
                nivel = t.get("nivel_invalidacao", "VERDE")
                rows.append({
                    "Nível": f"{NIVEL_ICONE.get(nivel, '')} {nivel}",
                    "Ativo": t["ticker"],
                    "Bloco IPS": t.get("bloco_ips") or "—",
                    "Racional": (t.get("racional") or "")[:60] + "…"
                    if len(t.get("racional") or "") > 60
                    else t.get("racional") or "",
                    "Dias": t.get("dias_desde_criacao", "—"),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.divider()

            for t in ativas:
                nivel_atual = t.get("nivel_invalidacao", "VERDE")
                icone = NIVEL_ICONE.get(nivel_atual, "")
                with st.expander(f"{icone} **{t['ticker']}** — {nivel_atual} · {t.get('dias_desde_criacao', '?')} dias"):
                    st.markdown(f"**Racional:** {t.get('racional', '—')}")
                    if t.get("cenario_esperado"):
                        st.markdown(f"**Cenário esperado:** {t['cenario_esperado']}")
                    if t.get("criterio_invalidacao"):
                        st.markdown(f"**Critério de invalidação:** {t['criterio_invalidacao']}")
                    if t.get("bloco_ips"):
                        st.caption(f"Bloco IPS: {t['bloco_ips']} · Criado em: {t.get('data_criacao', '?')}")

                    st.markdown("---")

                    # Alterar nível
                    col_n, col_btn = st.columns([3, 1])
                    with col_n:
                        novo_nivel = st.selectbox(
                            "Alterar nível",
                            options=NIVEIS,
                            index=NIVEIS.index(nivel_atual),
                            format_func=lambda x: f"{NIVEL_ICONE[x]} {x}",
                            key=f"ts_nivel_{t['id']}",
                        )
                    with col_btn:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("Atualizar Nível", key=f"ts_upd_nivel_{t['id']}"):
                            res = api.patch(f"teses/{t['id']}", data={"nivel_invalidacao": novo_nivel})
                            if res is not None:
                                st.success("Nível atualizado!")
                                st.rerun()

                    # Encerrar tese
                    st.markdown("**Encerrar tese**")
                    obs_enc = st.text_area(
                        "Motivo do encerramento",
                        placeholder="Por que está encerrando esta tese?",
                        key=f"ts_obs_enc_{t['id']}",
                    )
                    if st.button("🔒 Encerrar Tese", key=f"ts_enc_{t['id']}"):
                        st.session_state[f"confirm_enc_{t['id']}"] = True

                    if st.session_state.get(f"confirm_enc_{t['id']}"):
                        st.warning("Confirma o encerramento desta tese?")
                        ca, cb = st.columns(2)
                        with ca:
                            if st.button("✅ Confirmar", type="primary", key=f"ts_enc_ok_{t['id']}"):
                                res = api.patch(
                                    f"teses/{t['id']}",
                                    data={
                                        "status": "ENCERRADA",
                                        "observacao_encerramento": obs_enc.strip() or None,
                                    },
                                )
                                if res is not None:
                                    st.success("Tese encerrada.")
                                    st.session_state.pop(f"confirm_enc_{t['id']}", None)
                                    st.rerun()
                        with cb:
                            if st.button("❌ Cancelar", key=f"ts_enc_cancel_{t['id']}"):
                                st.session_state.pop(f"confirm_enc_{t['id']}", None)
                                st.rerun()
