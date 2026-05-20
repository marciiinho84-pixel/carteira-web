"""
Página: Novo Evento — formulário com validação em tempo real.

Features:
  - Dropdown de ativos do CAD_ATIVOS
  - Dropdown dos 12 tipos de evento
  - Date picker com auto-cálculo Qtd × Preço
  - Seção "Corrigir / Remover Evento": edição e exclusão dos últimos 20 eventos
"""

from datetime import date

import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

TIPOS_EVENTO = [
    "COMPRA", "VENDA", "DIVIDENDO", "JCP", "RENDIMENTO",
    "AMORTIZACAO", "BONIFICACAO", "CONTRIBUICAO",
    "APORTE_EXTERNO", "RESGATE_EXTERNO", "SALDO_INICIAL", "VENCIMENTO",
]

TIPOS_COM_QTD_PRECO = {"COMPRA", "VENDA", "SALDO_INICIAL", "BONIFICACAO", "VENCIMENTO"}


# ─── Formulário de novo evento ────────────────────────────────────────────────

def _form_novo_evento(tickers, ativos_info):
    col_form, col_ajuda = st.columns([3, 1])

    with col_form:
        ticker_sel = st.selectbox(
            "Ativo *",
            options=tickers,
            help="Selecione o ativo. Para cadastrar novo, vá em ⚙️ Configurações.",
            key="ne_ticker",
        )

        if ticker_sel and ticker_sel in ativos_info:
            info = ativos_info[ticker_sel]
            st.caption(
                f"📌 {info.get('familia', '—')} · {info.get('setor', '—')} · "
                f"Composite: **{info.get('composite', '—')}**"
            )

        tipo_sel = st.selectbox(
            "Tipo de Evento *",
            options=TIPOS_EVENTO,
            help="12 tipos disponíveis conforme event log.",
            key="ne_tipo",
        )

        data_sel = st.date_input(
            "Data *",
            value=date.today(),
            min_value=date(2026, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="ne_data",
        )

        st.divider()

        usa_qtd_preco = tipo_sel in TIPOS_COM_QTD_PRECO
        if usa_qtd_preco:
            def _sync_valor():
                q = st.session_state.get("ne_qtd", 0) or 0
                p = st.session_state.get("ne_preco", 0) or 0
                if q > 0 and p > 0:
                    st.session_state["ne_valor"] = round(q * p, 2)

            c1, c2, c3 = st.columns(3)
            with c1:
                qtd = st.number_input("Quantidade", min_value=0.0, value=0.0,
                                      step=1.0, format="%.6f", key="ne_qtd",
                                      on_change=_sync_valor)
            with c2:
                preco = st.number_input("Preço (R$)", min_value=0.0, value=0.0,
                                        step=0.01, format="%.4f", key="ne_preco",
                                        on_change=_sync_valor)
            with c3:
                valor_calc = qtd * preco if qtd > 0 and preco > 0 else 0.0
                valor = st.number_input("Valor R$", min_value=0.0,
                                        value=float(valor_calc), step=0.01,
                                        format="%.2f",
                                        help="Preenchido automaticamente com Qtd × Preço.",
                                        key="ne_valor")
            if qtd > 0 and preco > 0:
                st.caption(f"📐 Auto-calc: {qtd:.4f} × R$ {preco:.4f} = **{fmt.moeda(valor_calc)}**")
        else:
            qtd = preco = None
            valor = st.number_input("Valor R$ *", min_value=0.0, value=0.0,
                                    step=0.01, format="%.2f",
                                    help="Valor sempre positivo. O sinal vem do tipo do evento.",
                                    key="ne_valor_simples")

        obs = st.text_input("Observação",
                            placeholder="Ex: IRRF: R$ 12,50 | nota fiscal 1234",
                            max_chars=200, key="ne_obs")

        st.divider()

        erros = []
        avisos = []
        if valor <= 0:
            erros.append("Valor deve ser maior que zero.")
        if usa_qtd_preco and qtd <= 0:
            avisos.append("Quantidade não preenchida — o valor informado será usado diretamente.")
        if tipo_sel in {"COMPRA", "VENDA"} and qtd <= 0:
            erros.append("COMPRA e VENDA exigem quantidade > 0.")
        for e in erros:
            st.error(f"❌ {e}")
        for a in avisos:
            st.warning(f"⚠️ {a}")

        with st.expander("👁️ Preview do evento antes de salvar"):
            st.json({
                "data": str(data_sel), "ativo": ticker_sel, "tipo": tipo_sel,
                "qtd": qtd if qtd and qtd > 0 else None,
                "preco": preco if preco and preco > 0 else None,
                "valor": round(valor, 2), "obs": obs or None,
            })

        pode_salvar = not erros and valor > 0
        salvar = st.button("💾 Salvar e Recalcular", type="primary",
                           disabled=not pode_salvar, use_container_width=True,
                           key="ne_btn_salvar")

        if salvar and pode_salvar:
            payload = {
                "data": str(data_sel), "ativo": ticker_sel, "tipo": tipo_sel,
                "qtd": qtd if qtd and qtd > 0 else None,
                "preco": preco if preco and preco > 0 else None,
                "valor": round(valor, 2), "obs": obs or "",
            }
            with st.spinner("Salvando e recalculando..."):
                resultado = api.post("eventos", data=payload)
            if resultado is not None:
                ev_id_salvo = resultado.get("id")
                st.success(
                    f"✅ Evento salvo! **{tipo_sel}** de **{ticker_sel}** "
                    f"em {data_sel.strftime('%d/%m/%Y')} — {fmt.moeda(valor)}"
                )
                recalc = api.post("calcular", params={"no_api": "true"})
                if recalc and recalc.get("ok"):
                    st.session_state["calculado_em"] = recalc.get("calculado_em", "")
                    st.info(
                        f"🔄 Engine recalculado. "
                        f"Patrimônio: {fmt.moeda(recalc.get('patrimonio_total'))} | "
                        f"P&L RV: {fmt.moeda(recalc.get('pnl_vendas_rv'), sinal=True)}"
                    )
                # Oferta opcional de registrar tese (apenas COMPRA)
                if tipo_sel == "COMPRA":
                    if st.button("📓 Registrar tese para esta compra (opcional)",
                                 key="ne_btn_tese"):
                        st.session_state["ne_tese_ev_id"] = ev_id_salvo
                        st.session_state["ne_tese_ativo"] = ticker_sel
                        st.rerun()
                st.balloons()

    with col_ajuda:
        st.markdown("### 💡 Dicas")
        st.markdown("""
**Tipos mais usados:**
- `COMPRA` — compra de ativo
- `VENDA` — venda de ativo
- `DIVIDENDO` — dividendo recebido
- `JCP` — juros s/ capital próprio
- `RENDIMENTO` — rend. de RF
- `APORTE_EXTERNO` — dinheiro novo entrando

**Regras:**
- Valor sempre **positivo**
- O sinal vem do tipo do evento
- D+2 detectado automaticamente

**Auto-cálculo:**
- Preencha Qtd + Preço
- Valor é calculado na hora
- Você pode editar manualmente
        """)


# ─── Seção: Corrigir / Remover Evento ────────────────────────────────────────

def _secao_corrigir(tickers, ativos_info):
    st.subheader("✏️ Corrigir / Remover Evento")
    st.caption("Selecione um dos últimos 20 eventos para editar ou excluir.")

    eventos_raw = api.get("eventos") or []
    ultimos20 = sorted(eventos_raw, key=lambda e: (e["id"]), reverse=True)[:20]

    if not ultimos20:
        st.info("Nenhum evento encontrado.")
        return

    # ── Tabela exibição ───────────────────────────────────────────
    import pandas as pd
    rows = []
    for ev in ultimos20:
        dt = ev["data"]
        dt_fmt = f"{dt[8:10]}/{dt[5:7]}/{dt[:4]}" if len(dt) == 10 else dt
        rows.append({
            "ID": ev["id"],
            "Data": dt_fmt,
            "Ativo": ev["ativo"],
            "Tipo": ev["tipo"],
            "Qtd": f"{ev['qtd']:,.4f}" if ev.get("qtd") else "—",
            "Valor": fmt.moeda(ev.get("valor", 0)),
            "Observação": (ev.get("obs") or "")[:40],
        })
    df_evs = pd.DataFrame(rows)
    st.dataframe(df_evs, hide_index=True, use_container_width=True)

    st.caption("Exportar últimos 20 eventos:")
    fmt.botoes_exportar(df_evs, "eventos", key="ev")

    st.divider()

    # ── Seletor de evento ─────────────────────────────────────────
    opcoes = {
        ev["id"]: (
            f"#{ev['id']:>4} | {ev['data'][8:10]}/{ev['data'][5:7]} | "
            f"{ev['ativo']} | {ev['tipo']} | {fmt.moeda(ev.get('valor', 0))}"
        )
        for ev in ultimos20
    }
    ids_ordenados = [ev["id"] for ev in ultimos20]

    ev_id_sel = st.selectbox(
        "Evento selecionado",
        options=ids_ordenados,
        format_func=lambda x: opcoes[x],
        key="ne_ev_sel",
    )

    ev_sel = next((e for e in ultimos20 if e["id"] == ev_id_sel), None)
    if ev_sel is None:
        return

    c_edit, c_del, _ = st.columns([1, 1, 4])

    with c_edit:
        if st.button("✏️ Editar", key="ne_btn_edit", use_container_width=True):
            st.session_state["ne_editando"] = ev_id_sel
            st.session_state.pop("ne_excluindo", None)
            st.rerun()

    with c_del:
        eh_saldo_inicial = ev_sel.get("tipo") == "SALDO_INICIAL"
        if st.button("🗑️ Excluir", key="ne_btn_del", use_container_width=True,
                     disabled=eh_saldo_inicial,
                     help="Não é permitido excluir SALDO_INICIAL" if eh_saldo_inicial else ""):
            st.session_state["ne_excluindo"] = ev_id_sel
            st.session_state.pop("ne_editando", None)
            st.rerun()

    # ── Painel de edição ──────────────────────────────────────────
    if st.session_state.get("ne_editando") == ev_id_sel:
        _painel_edicao(ev_sel, tickers, ativos_info)

    # ── Painel de exclusão ────────────────────────────────────────
    if st.session_state.get("ne_excluindo") == ev_id_sel:
        _painel_exclusao(ev_sel)


def _painel_edicao(ev, tickers, ativos_info):
    st.divider()
    st.markdown(f"**✏️ Editando evento #{ev['id']} — {ev['ativo']} | {ev['tipo']}**")

    tipo_orig = ev["tipo"]
    data_orig = date.fromisoformat(ev["data"])

    col_e, _ = st.columns([3, 1])
    with col_e:
        ticker_e = st.selectbox(
            "Ativo",
            options=tickers,
            index=tickers.index(ev["ativo"]) if ev["ativo"] in tickers else 0,
            key=f"edit_ticker_{ev['id']}",
        )
        tipo_e = st.selectbox(
            "Tipo de Evento",
            options=TIPOS_EVENTO,
            index=TIPOS_EVENTO.index(tipo_orig) if tipo_orig in TIPOS_EVENTO else 0,
            key=f"edit_tipo_{ev['id']}",
        )
        if tipo_e != tipo_orig:
            st.warning(
                f"⚠️ Alterando tipo de **{tipo_orig}** para **{tipo_e}** "
                "pode impactar PEPS e cálculos de P&L."
            )
        data_e = st.date_input(
            "Data",
            value=data_orig,
            min_value=date(2026, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key=f"edit_data_{ev['id']}",
        )

        st.divider()

        usa_qtd = tipo_e in TIPOS_COM_QTD_PRECO
        if usa_qtd:
            c1, c2, c3 = st.columns(3)
            with c1:
                qtd_e = st.number_input("Quantidade", min_value=0.0,
                                        value=float(ev["qtd"] or 0),
                                        step=1.0, format="%.6f",
                                        key=f"edit_qtd_{ev['id']}")
            with c2:
                preco_e = st.number_input("Preço (R$)", min_value=0.0,
                                          value=float(ev["preco"] or 0),
                                          step=0.01, format="%.4f",
                                          key=f"edit_preco_{ev['id']}")
            with c3:
                valor_calc_e = qtd_e * preco_e if qtd_e > 0 and preco_e > 0 else float(ev["valor"] or 0)
                valor_e = st.number_input("Valor R$", min_value=0.0,
                                          value=valor_calc_e,
                                          step=0.01, format="%.2f",
                                          key=f"edit_valor_{ev['id']}")
        else:
            qtd_e = preco_e = None
            valor_e = st.number_input("Valor R$", min_value=0.0,
                                      value=float(ev["valor"] or 0),
                                      step=0.01, format="%.2f",
                                      key=f"edit_valor_s_{ev['id']}")

        obs_e = st.text_input("Observação",
                              value=ev.get("obs") or "",
                              max_chars=200,
                              key=f"edit_obs_{ev['id']}")

        st.divider()

        ca, cb = st.columns(2)
        with ca:
            if st.button("💾 Salvar Edição", type="primary",
                         use_container_width=True, key=f"edit_save_{ev['id']}"):
                payload = {
                    "data": str(data_e),
                    "ativo": ticker_e,
                    "tipo": tipo_e,
                    "qtd": qtd_e if qtd_e and qtd_e > 0 else None,
                    "preco": preco_e if preco_e and preco_e > 0 else None,
                    "valor": round(valor_e, 2),
                    "obs": obs_e or "",
                }
                with st.spinner("Salvando e recalculando..."):
                    res = api.patch(f"eventos/{ev['id']}", data=payload)
                if res is not None:
                    st.session_state.pop("ne_editando", None)
                    st.success(
                        f"✅ Evento #{ev['id']} atualizado! "
                        f"{tipo_e} de {ticker_e} — {fmt.moeda(valor_e)}"
                    )
                    api.post("calcular", params={"no_api": "true"})
                    st.rerun()
        with cb:
            if st.button("❌ Cancelar", use_container_width=True,
                         key=f"edit_cancel_{ev['id']}"):
                st.session_state.pop("ne_editando", None)
                st.rerun()


def _painel_exclusao(ev):
    st.divider()
    st.warning(
        f"⚠️ **Tem certeza?** Isso excluirá o evento #{ev['id']} "
        f"(**{ev['tipo']}** de **{ev['ativo']}** em {ev['data'][:10]} "
        f"— {fmt.moeda(ev.get('valor', 0))}) e recalculará toda a carteira."
    )
    ca, cb, _ = st.columns([1, 1, 4])
    with ca:
        if st.button("✅ Confirmar exclusão", type="primary",
                     use_container_width=True, key=f"del_confirm_{ev['id']}"):
            with st.spinner("Excluindo e recalculando..."):
                ok = api.delete(f"eventos/{ev['id']}")
            if ok:
                st.session_state.pop("ne_excluindo", None)
                st.success(f"✅ Evento #{ev['id']} excluído. Carteira recalculada.")
                api.post("calcular", params={"no_api": "true"})
                st.rerun()
    with cb:
        if st.button("❌ Cancelar", use_container_width=True,
                     key=f"del_cancel_{ev['id']}"):
            st.session_state.pop("ne_excluindo", None)
            st.rerun()


# ─── Entry point ─────────────────────────────────────────────────────────────

def render():
    st.title("➕ Novo Evento")
    st.caption(
        "Adicione um evento ao event log. "
        "Após salvar, o engine recalcula automaticamente toda a carteira."
    )

    ativos_lista = api.get("ativos")
    if ativos_lista is None:
        st.error("Não foi possível carregar a lista de ativos. Verifique a API.")
        return

    tickers = sorted(a["ticker"] for a in ativos_lista)
    ativos_info = {a["ticker"]: a for a in ativos_lista}

    st.divider()
    _form_novo_evento(tickers, ativos_info)

    # Formulário de tese (aparece após COMPRA, opcional)
    if st.session_state.get("ne_tese_ev_id"):
        ev_id_tese = st.session_state["ne_tese_ev_id"]
        ativo_tese = st.session_state.get("ne_tese_ativo", "")
        st.divider()
        with st.expander("📓 Registrar tese de investimento", expanded=True):
            from carteira_clean_web.frontend.telas.diario import _form_nova_decisao
            salvo = _form_nova_decisao(tickers, ev_id=ev_id_tese,
                                       ativo_pre=ativo_tese, acao_pre="COMPRA")
            if salvo:
                st.session_state.pop("ne_tese_ev_id", None)
                st.session_state.pop("ne_tese_ativo", None)
            if st.button("⏭️ Pular — registrar depois", key="ne_btn_pular_tese"):
                st.session_state.pop("ne_tese_ev_id", None)
                st.session_state.pop("ne_tese_ativo", None)
                st.rerun()

    st.divider()
    _secao_corrigir(tickers, ativos_info)
