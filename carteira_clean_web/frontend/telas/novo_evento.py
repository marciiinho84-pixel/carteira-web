"""
Página: Novo Evento — formulário com validação em tempo real.

Features:
  - Dropdown de ativos do CAD_ATIVOS
  - Dropdown dos 12 tipos de evento
  - Date picker
  - Auto-cálculo: se qtd + preço preenchidos → valor calculado automaticamente
  - Botão "Salvar e Recalcular" com feedback visual
  - Validação inline (ticker existe, tipo válido)
"""

from datetime import date, datetime

import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

TIPOS_EVENTO = [
    "COMPRA", "VENDA", "DIVIDENDO", "JCP", "RENDIMENTO",
    "AMORTIZACAO", "BONIFICACAO", "CONTRIBUICAO",
    "APORTE_EXTERNO", "RESGATE_EXTERNO", "SALDO_INICIAL", "VENCIMENTO",
]

TIPOS_COM_QTD_PRECO = {"COMPRA", "VENDA", "SALDO_INICIAL", "BONIFICACAO", "VENCIMENTO"}
TIPOS_SEM_QTD = {"DIVIDENDO", "JCP", "RENDIMENTO", "AMORTIZACAO",
                  "APORTE_EXTERNO", "RESGATE_EXTERNO", "CONTRIBUICAO"}


def render():
    st.title("➕ Novo Evento")
    st.caption(
        "Adicione um evento ao event log. "
        "Após salvar, o engine recalcula automaticamente toda a carteira."
    )

    # Carrega lista de ativos para o dropdown
    ativos_lista = api.get("ativos")
    if ativos_lista is None:
        st.error("Não foi possível carregar a lista de ativos. Verifique a API.")
        return

    tickers = sorted(a["ticker"] for a in ativos_lista)
    ativos_info = {a["ticker"]: a for a in ativos_lista}

    st.divider()

    col_form, col_ajuda = st.columns([3, 1])

    with col_form:
        # ── Ativo ──────────────────────────────────────────────────
        ticker_sel = st.selectbox(
            "Ativo *",
            options=tickers,
            help="Selecione o ativo. Para cadastrar novo, vá em ⚙️ Configurações.",
        )

        # Info inline do ativo selecionado
        if ticker_sel and ticker_sel in ativos_info:
            info = ativos_info[ticker_sel]
            st.caption(
                f"📌 {info.get('familia', '—')} · {info.get('setor', '—')} · "
                f"Composite: **{info.get('composite', '—')}**"
            )

        # ── Tipo ───────────────────────────────────────────────────
        tipo_sel = st.selectbox(
            "Tipo de Evento *",
            options=TIPOS_EVENTO,
            help="12 tipos disponíveis conforme event log.",
        )

        # ── Data ───────────────────────────────────────────────────
        data_sel = st.date_input(
            "Data *",
            value=date.today(),
            min_value=date(2026, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
        )

        st.divider()

        # ── Campos numéricos com auto-cálculo ─────────────────────
        usa_qtd_preco = tipo_sel in TIPOS_COM_QTD_PRECO

        if usa_qtd_preco:
            c1, c2, c3 = st.columns(3)
            with c1:
                qtd = st.number_input(
                    "Quantidade",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    format="%.6f",
                )
            with c2:
                preco = st.number_input(
                    "Preço (R$)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.4f",
                )
            with c3:
                # Auto-cálculo: se qtd e preco preenchidos, sugere valor
                valor_calc = qtd * preco if qtd > 0 and preco > 0 else 0.0
                valor = st.number_input(
                    "Valor R$",
                    min_value=0.0,
                    value=float(valor_calc),
                    step=0.01,
                    format="%.2f",
                    help="Preenchido automaticamente com Qtd × Preço. Edite se necessário.",
                )
            # Atualiza valor_calc após edição manual
            if qtd > 0 and preco > 0:
                st.caption(f"📐 Auto-calc: {qtd:.4f} × R$ {preco:.4f} = **{fmt.moeda(valor_calc)}**")
        else:
            qtd = None
            preco = None
            valor = st.number_input(
                "Valor R$ *",
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.2f",
                help="Valor sempre positivo. O sinal vem do tipo do evento.",
            )

        # ── Observação ─────────────────────────────────────────────
        obs = st.text_input(
            "Observação",
            placeholder="Ex: IRRF: R$ 12,50 | nota fiscal 1234",
            max_chars=200,
        )

        st.divider()

        # ── Validações inline ──────────────────────────────────────
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

        # ── Preview do evento ──────────────────────────────────────
        with st.expander("👁️ Preview do evento antes de salvar"):
            st.json({
                "data": str(data_sel),
                "ativo": ticker_sel,
                "tipo": tipo_sel,
                "qtd": qtd if qtd and qtd > 0 else None,
                "preco": preco if preco and preco > 0 else None,
                "valor": round(valor, 2),
                "obs": obs or None,
            })

        # ── Botão Salvar ───────────────────────────────────────────
        pode_salvar = not erros and valor > 0

        salvar = st.button(
            "💾 Salvar e Recalcular",
            type="primary",
            disabled=not pode_salvar,
            use_container_width=True,
        )

        if salvar and pode_salvar:
            payload = {
                "data": str(data_sel),
                "ativo": ticker_sel,
                "tipo": tipo_sel,
                "qtd": qtd if qtd and qtd > 0 else None,
                "preco": preco if preco and preco > 0 else None,
                "valor": round(valor, 2),
                "obs": obs or "",
            }
            with st.spinner("Salvando evento e recalculando..."):
                resultado = api.post("eventos", data=payload)

            if resultado is not None:
                st.success(
                    f"✅ Evento salvo! **{tipo_sel}** de "
                    f"**{ticker_sel}** em {data_sel.strftime('%d/%m/%Y')} "
                    f"— {fmt.moeda(valor)}"
                )
                # Força recálculo do cache
                recalc = api.post("calcular", params={"no_api": "true"})
                if recalc and recalc.get("ok"):
                    st.session_state["calculado_em"] = recalc.get("calculado_em", "")
                    pat = recalc.get("patrimonio_total")
                    pnl = recalc.get("pnl_vendas_rv")
                    st.info(
                        f"🔄 Engine recalculado. "
                        f"Patrimônio: {fmt.moeda(pat)} | "
                        f"P&L RV: {fmt.moeda(pnl, sinal=True)}"
                    )
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
