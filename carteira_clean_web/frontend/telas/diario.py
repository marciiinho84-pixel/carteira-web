"""
Página: Diário de Decisões — registro e revisão de teses de investimento.
"""

from datetime import date

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

ACOES = ["COMPRA", "VENDA", "MANTER", "OBSERVAR"]
HORIZONTES = ["curto", "medio", "longo"]


def _form_nova_decisao(tickers: list, ev_id: int | None = None,
                       ativo_pre: str = "", acao_pre: str = "COMPRA") -> bool:
    """Renderiza o form de nova decisão. Retorna True se salvo com sucesso."""
    st.markdown("#### ✏️ Nova Decisão")

    c1, c2 = st.columns(2)
    with c1:
        ativo_idx = tickers.index(ativo_pre) if ativo_pre in tickers else 0
        ativo = st.selectbox("Ativo *", options=tickers, index=ativo_idx, key="dj_ativo")
        acao = st.selectbox("Ação *", options=ACOES,
                            index=ACOES.index(acao_pre), key="dj_acao")
        horizonte = st.selectbox("Horizonte", options=[""] + HORIZONTES,
                                 format_func=lambda x: {"": "—", "curto": "Curto (< 6m)",
                                                         "medio": "Médio (6-18m)",
                                                         "longo": "Longo (> 18m)"}.get(x, x),
                                 key="dj_horizonte")
    with c2:
        data_dec = st.date_input("Data da decisão *", value=date.today(),
                                 format="DD/MM/YYYY", key="dj_data")
        expectativa = st.number_input("Expectativa retorno (%)", min_value=-100.0,
                                      max_value=1000.0, value=0.0, step=0.5,
                                      format="%.1f", key="dj_expectativa")
        revisao_em = st.date_input("Revisar em", value=None, format="DD/MM/YYYY",
                                   key="dj_revisao")

    tese = st.text_area("Tese de investimento *", height=120,
                        placeholder="Por que esta decisão? Quais são os catalisadores? "
                                    "Qual o risco principal?",
                        key="dj_tese")

    pode_salvar = bool(ativo and acao and tese.strip())
    if st.button("💾 Registrar Decisão", type="primary",
                 disabled=not pode_salvar, key="dj_btn_salvar"):
        payload = {
            "data_decisao": str(data_dec),
            "ativo": ativo,
            "acao": acao,
            "tese": tese.strip(),
            "expectativa_retorno_pct": expectativa if expectativa != 0 else None,
            "horizonte": horizonte or None,
            "revisao_em": str(revisao_em) if revisao_em else None,
            "evento_id": ev_id,
        }
        res = api.post("decisoes", data=payload)
        if res is not None:
            st.success(f"✅ Decisão sobre **{ativo}** registrada!")
            for k in ["dj_ativo", "dj_acao", "dj_horizonte", "dj_data",
                      "dj_expectativa", "dj_revisao", "dj_tese"]:
                st.session_state.pop(k, None)
            return True
    return False


def render():
    st.title("📓 Diário de Decisões")
    st.caption("Registre sua tese por trás de cada decisão. Revise depois e aprenda com os resultados.")

    ativos_lista = api.get("ativos") or []
    tickers = sorted(a["ticker"] for a in ativos_lista)

    # ─── Notificação de revisões pendentes ───────────────────────
    pendentes = api.get("decisoes/pendentes") or []
    if pendentes:
        st.warning(
            f"🔔 **{len(pendentes)} decisão/ões aguardam revisão** — "
            f"mais antiga: {pendentes[0].get('revisao_em', '?')} · "
            f"{pendentes[0].get('ativo', '')} ({pendentes[0].get('acao', '')})"
        )

    abas = st.tabs(["✏️ Nova Decisão", "🔄 Pendentes para Revisão", "📋 Histórico"])

    # ─── Aba 1: Nova decisão ───────────────────────────────────────
    with abas[0]:
        _form_nova_decisao(tickers)

    # ─── Aba 2: Pendentes ─────────────────────────────────────────
    with abas[1]:
        if not pendentes:
            st.info("Nenhuma decisão aguardando revisão. 🎉")
        else:
            for dec in pendentes:
                with st.expander(
                    f"#{dec['id']} — **{dec['ativo']}** ({dec['acao']}) · "
                    f"revisão prevista {dec.get('revisao_em', '?')}",
                    expanded=True,
                ):
                    st.markdown(f"**Tese:** {dec['tese']}")
                    if dec.get("expectativa_retorno_pct"):
                        st.caption(f"Expectativa: {dec['expectativa_retorno_pct']:+.1f}%  ·  "
                                   f"Horizonte: {dec.get('horizonte', '—')}")

                    res_key = f"rev_resultado_{dec['id']}"
                    notas_key = f"rev_notas_{dec['id']}"
                    resultado = st.text_area("Resultado da revisão *", key=res_key,
                                            placeholder="O que aconteceu? A tese se confirmou?")
                    notas = st.text_area("Notas / lições aprendidas", key=notas_key,
                                        placeholder="O que faria diferente?")

                    if st.button("✅ Salvar Revisão", type="primary",
                                 key=f"rev_btn_{dec['id']}",
                                 disabled=not resultado.strip()):
                        res = api.patch(f"decisoes/{dec['id']}",
                                        data={"resultado_revisao": resultado.strip(),
                                              "notas": notas.strip() or None})
                        if res is not None:
                            st.success("✅ Revisão registrada!")
                            st.rerun()

    # ─── Aba 3: Histórico ─────────────────────────────────────────
    with abas[2]:
        todas = api.get("decisoes") or []
        if not todas:
            st.info("Nenhuma decisão registrada ainda.")
        else:
            # Filtros
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                ativos_u = sorted({d["ativo"] for d in todas})
                ativo_f = st.multiselect("Ativo", ativos_u, key="dj_f_ativo")
            with fc2:
                acao_f = st.multiselect("Ação", ACOES, key="dj_f_acao")
            with fc3:
                horiz_f = st.multiselect("Horizonte", HORIZONTES, key="dj_f_horiz")

            filtradas = todas
            if ativo_f:
                filtradas = [d for d in filtradas if d["ativo"] in ativo_f]
            if acao_f:
                filtradas = [d for d in filtradas if d["acao"] in acao_f]
            if horiz_f:
                filtradas = [d for d in filtradas if d.get("horizonte") in horiz_f]

            st.caption(f"{len(filtradas)} decisão/ões")

            rows = []
            for d in filtradas:
                status = "✅ Revisado" if d.get("resultado_revisao") else (
                    "⏳ Pendente" if d.get("revisao_em") and
                    d["revisao_em"] <= str(date.today()) else "📌 Ativo"
                )
                rows.append({
                    "Data": d["data_decisao"],
                    "Ativo": d["ativo"],
                    "Ação": d["acao"],
                    "Horizonte": d.get("horizonte") or "—",
                    "Expectativa": f"{d['expectativa_retorno_pct']:+.1f}%" if d.get("expectativa_retorno_pct") else "—",
                    "Revisar em": d.get("revisao_em") or "—",
                    "Status": status,
                    "Tese": (d["tese"] or "")[:60] + "…" if len(d.get("tese", "")) > 60 else d.get("tese", ""),
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # Expandir decisão selecionada
            if filtradas:
                st.divider()
                ids_opcoes = {d["id"]: f"#{d['id']} {d['ativo']} ({d['acao']}) {d['data_decisao']}"
                              for d in filtradas}
                dec_id = st.selectbox("Ver detalhes de:", options=list(ids_opcoes.keys()),
                                      format_func=lambda x: ids_opcoes[x], key="dj_detalhe")
                dec_sel = next((d for d in filtradas if d["id"] == dec_id), None)
                if dec_sel:
                    st.markdown(f"**Tese:** {dec_sel['tese']}")
                    if dec_sel.get("resultado_revisao"):
                        st.markdown(f"**Resultado:** {dec_sel['resultado_revisao']}")
                    if dec_sel.get("notas"):
                        st.markdown(f"**Notas:** {dec_sel['notas']}")

                    if st.button("🗑️ Excluir decisão", key=f"del_dec_{dec_id}"):
                        st.session_state[f"confirm_del_dec_{dec_id}"] = True

                    if st.session_state.get(f"confirm_del_dec_{dec_id}"):
                        st.warning("Tem certeza? Esta ação é irreversível.")
                        ca, cb = st.columns(2)
                        with ca:
                            if st.button("✅ Confirmar exclusão", type="primary",
                                         key=f"del_dec_confirm_{dec_id}"):
                                api.delete(f"decisoes/{dec_id}")
                                st.session_state.pop(f"confirm_del_dec_{dec_id}", None)
                                st.rerun()
                        with cb:
                            if st.button("❌ Cancelar", key=f"del_dec_cancel_{dec_id}"):
                                st.session_state.pop(f"confirm_del_dec_{dec_id}", None)
                                st.rerun()
