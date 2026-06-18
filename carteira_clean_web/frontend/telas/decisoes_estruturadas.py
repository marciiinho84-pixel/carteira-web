"""
Página: Decisões Estruturadas — diário com convicção e vínculo a teses (Fatia 5).
"""

from datetime import date

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

ACOES = ["COMPRA", "VENDA", "AUMENTO", "REDUCAO", "MANTER", "WATCHLIST"]

_CONV_LABEL = {
    1: "1 — Especulação",
    2: "2 — Convicção Baixa",
    3: "3 — Convicção Média",
    4: "4 — Convicção Alta",
    5: "5 — Alta Convicção",
}

_ESTRELAS = {1: "★☆☆☆☆", 2: "★★☆☆☆", 3: "★★★☆☆", 4: "★★★★☆", 5: "★★★★★"}


def _teses_ativas() -> list[dict]:
    dados = api.get("teses", params={"status_f": "ATIVA"}) or []
    return dados


def _label_tese(t: dict) -> str:
    racional = (t.get("racional") or "")[:60]
    return f"{t.get('ticker','?')} — {racional}{'…' if len(t.get('racional','')) > 60 else ''}"


def render():
    st.title("🧭 Decisões Estruturadas")
    st.caption("Registre cada decisão com convicção e vincule a uma tese ativa.")

    ativos_lista = api.get("ativos") or []
    tickers = sorted(a["ticker"] for a in ativos_lista)
    teses = _teses_ativas()

    abas = st.tabs(["✏️ Nova Decisão", "📋 Histórico"])

    # ─── Aba 1: Nova Decisão ─────────────────────────────────────────
    with abas[0]:
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.selectbox("Ativo *", options=tickers, key="de_ticker")
            data_decisao = st.date_input(
                "Data da decisão *", value=date.today(),
                format="DD/MM/YYYY", key="de_data"
            )
            acao = st.selectbox("Ação *", options=ACOES, key="de_acao")
        with c2:
            conviccao = st.slider(
                "Convicção",
                min_value=1, max_value=5, value=3, step=1,
                format="%d",
                help="1 = Especulação  |  3 = Convicção Média  |  5 = Alta Convicção",
                key="de_conviccao",
            )
            st.caption(f"Nível selecionado: **{_CONV_LABEL[conviccao]}**")
            preco_entrada = st.number_input(
                "Preço de entrada (R$)", min_value=0.0, value=0.0,
                step=0.01, format="%.2f", key="de_preco",
                help="Opcional. Deixe 0 para não registrar.",
            )

        racional = st.text_area(
            "Racional *", height=110,
            placeholder="Por que esta decisão?",
            key="de_racional",
        )
        cenario_esperado = st.text_area(
            "Cenário esperado (opcional)", height=80,
            placeholder="O que precisa acontecer para confirmar a tese?",
            key="de_cenario",
        )

        tese_opcoes = {None: "— (sem vínculo)"}
        for t in teses:
            tese_opcoes[t["id"]] = _label_tese(t)

        tese_sel = st.selectbox(
            "Vincular a tese ativa (opcional)",
            options=list(tese_opcoes.keys()),
            format_func=lambda x: tese_opcoes[x],
            key="de_tese",
        )

        pode_salvar = bool(ticker and acao and racional.strip())
        if st.button("💾 Registrar Decisão", type="primary",
                     disabled=not pode_salvar, key="de_btn_salvar"):
            payload = {
                "data_decisao": str(data_decisao),
                "ticker": ticker,
                "acao": acao,
                "racional": racional.strip(),
                "conviccao": conviccao,
                "cenario_esperado": cenario_esperado.strip() or None,
                "preco_entrada": preco_entrada if preco_entrada > 0 else None,
                "tese_id": tese_sel,
            }
            res = api.post("diario-decisoes", data=payload)
            if res is not None:
                st.success(f"Decisão sobre **{ticker}** registrada com sucesso!")
                for k in ["de_ticker", "de_data", "de_acao", "de_conviccao",
                          "de_preco", "de_racional", "de_cenario", "de_tese"]:
                    st.session_state.pop(k, None)
                st.rerun()

    # ─── Aba 2: Histórico ────────────────────────────────────────────
    with abas[1]:
        todas = api.get("diario-decisoes") or []
        if not todas:
            st.info("Nenhuma decisão registrada ainda.")
        else:
            # Filtros
            fc1, fc2 = st.columns(2)
            with fc1:
                ativos_u = sorted({d["ticker"] for d in todas})
                ativo_f = st.multiselect("Filtrar por ativo", ativos_u, key="de_f_ativo")
            with fc2:
                acao_f = st.multiselect("Filtrar por ação", ACOES, key="de_f_acao")

            filtradas = sorted(todas, key=lambda d: d.get("data_decisao", ""), reverse=True)
            if ativo_f:
                filtradas = [d for d in filtradas if d["ticker"] in ativo_f]
            if acao_f:
                filtradas = [d for d in filtradas if d["acao"] in acao_f]

            st.caption(f"{len(filtradas)} decisão/ões")

            rows = []
            for d in filtradas:
                racional_trunc = (d.get("racional") or "")
                racional_exib = racional_trunc[:70] + "…" if len(racional_trunc) > 70 else racional_trunc
                rows.append({
                    "Data": d.get("data_decisao", ""),
                    "Ativo": d.get("ticker", ""),
                    "Ação": d.get("acao", ""),
                    "Convicção": _ESTRELAS.get(d.get("conviccao", 3), ""),
                    "P.Entrada": fmt.moeda(d["preco_entrada"]) if d.get("preco_entrada") else "—",
                    "Racional": racional_exib,
                })

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.divider()

            for d in filtradas:
                dec_id = d["id"]
                label_exp = (
                    f"#{dec_id} — **{d['ticker']}** ({d['acao']}) · "
                    f"{d.get('data_decisao','?')} · {_ESTRELAS.get(d.get('conviccao',3),'')}"
                )
                with st.expander(label_exp):
                    st.markdown(f"**Racional:** {d.get('racional','')}")
                    if d.get("cenario_esperado"):
                        st.markdown(f"**Cenário esperado:** {d['cenario_esperado']}")
                    if d.get("preco_entrada"):
                        st.caption(f"Preço de entrada: {fmt.moeda(d['preco_entrada'])}")
                    if d.get("tese_id"):
                        st.caption(f"Tese vinculada: #{d['tese_id']}")

                    if st.button("🗑️ Excluir", key=f"de_del_{dec_id}"):
                        st.session_state[f"de_confirm_del_{dec_id}"] = True

                    if st.session_state.get(f"de_confirm_del_{dec_id}"):
                        st.warning("Tem certeza? Esta ação é irreversível.")
                        ca, cb = st.columns(2)
                        with ca:
                            if st.button("Confirmar exclusão", type="primary",
                                         key=f"de_del_confirm_{dec_id}"):
                                api.delete(f"diario-decisoes/{dec_id}")
                                st.session_state.pop(f"de_confirm_del_{dec_id}", None)
                                st.rerun()
                        with cb:
                            if st.button("Cancelar", key=f"de_del_cancel_{dec_id}"):
                                st.session_state.pop(f"de_confirm_del_{dec_id}", None)
                                st.rerun()
