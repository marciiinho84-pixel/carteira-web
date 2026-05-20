"""
Página: Configurações — edição de ativos, premissas da Meta, info do sistema.
"""

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api, fmt

_META_KEY = "premissas_meta"


def _premissas_default():
    return {
        "meta_valor": 3_000_000.0,
        "aporte_funcef_mensal": 6_392.0,
        "aporte_gerida_marco": 10_000.0,
        "aporte_gerida_outubro": 10_000.0,
    }


def render():
    st.title("⚙️ Configurações")
    aba = st.tabs(["📋 CAD_ATIVOS", "🎯 Premissas da Meta", "ℹ️ Sistema"])

    # ─── Aba 1: Edição de Ativos ──────────────────────────────────
    with aba[0]:
        # ── Formulário: Cadastrar novo ativo ──────────────────────
        with st.expander("➕ Cadastrar novo ativo", expanded=False):
            st.caption("Preencha os campos obrigatórios e clique em Cadastrar.")
            fa1, fa2 = st.columns(2)
            with fa1:
                novo_ticker = st.text_input(
                    "Ticker *", placeholder="Ex: BBAS3",
                    key="cfg_novo_ticker",
                ).upper().strip()
                novo_classe = st.selectbox(
                    "Classe *",
                    options=["Renda Variável", "Renda Fixa", "Multimercado", "Previdência"],
                    key="cfg_novo_classe",
                )
                novo_familia = st.selectbox(
                    "Família *",
                    options=["Ação BR", "BDR", "BDR de ETF", "ETF BR",
                             "Fundo CP", "Fundo de Pensão", "Fundo Indexado",
                             "Tesouro Direto", "Letra de Crédito"],
                    key="cfg_novo_familia",
                )
                novo_setor = st.text_input(
                    "Setor *", placeholder="Ex: Bancos",
                    key="cfg_novo_setor",
                )
            with fa2:
                novo_composite = st.selectbox(
                    "Composite *",
                    options=["Gerida", "FUNCEF"],
                    key="cfg_novo_composite",
                )
                novo_indexador = st.text_input(
                    "Indexador (opcional)", placeholder="Ex: CDI+1%",
                    key="cfg_novo_indexador",
                )
                novo_benchmark = st.text_input(
                    "Benchmark (opcional)", placeholder="Ex: IBOV",
                    key="cfg_novo_benchmark",
                )
                novo_obs = st.text_input(
                    "Observação (opcional)", placeholder="Ex: Banco do Brasil",
                    key="cfg_novo_obs",
                )
                familias_com_vencimento = {"Letra de Crédito", "Tesouro Direto", "Fundo Indexado"}
                if novo_familia in familias_com_vencimento:
                    novo_vencimento = st.date_input(
                        "Data de vencimento", value=None, format="DD/MM/YYYY",
                        key="cfg_novo_vencimento",
                    )
                else:
                    novo_vencimento = None

            pode_cadastrar = bool(novo_ticker and novo_setor)
            if not novo_ticker:
                st.warning("⚠️ Ticker obrigatório.")
            if not novo_setor:
                st.warning("⚠️ Setor obrigatório.")

            if st.button("💾 Cadastrar Ativo", type="primary",
                         disabled=not pode_cadastrar, key="cfg_btn_cadastrar"):
                payload = {
                    "ticker": novo_ticker,
                    "classe": novo_classe,
                    "familia": novo_familia,
                    "setor": novo_setor,
                    "composite": novo_composite,
                    "indexador": novo_indexador or None,
                    "benchmark": novo_benchmark or None,
                    "observacao": novo_obs or None,
                    "data_vencimento": str(novo_vencimento) if novo_vencimento else None,
                }
                res = api.post("ativos", data=payload)
                if res is not None:
                    st.success(
                        f"✅ **{novo_ticker}** cadastrado com sucesso! "
                        "Disponível em ➕ Novo Evento."
                    )
                    st.rerun()

        st.divider()
        st.subheader("Editar Ativos Cadastrados")
        st.caption(
            "Edite Setor, Benchmark, Observação e Data de Vencimento diretamente na tabela. "
            "Ticker, Família e Composite estão bloqueados para proteger os cálculos."
        )

        ativos = api.get("ativos")
        if ativos is None:
            return

        COLUNAS_BLOQUEADAS = ["ticker", "familia", "composite", "classe", "indexador"]
        COLUNAS_EDITAVEIS = ["setor", "benchmark", "observacao", "data_vencimento"]

        df_orig = pd.DataFrame(ativos).reindex(
            columns=["ticker", "familia", "composite", "classe",
                     "setor", "benchmark", "indexador", "observacao", "data_vencimento"],
        )
        string_cols = ["ticker", "familia", "composite", "classe",
                       "setor", "benchmark", "indexador", "observacao"]
        df_orig[string_cols] = df_orig[string_cols].fillna("")
        df_orig["data_vencimento"] = pd.to_datetime(
            df_orig["data_vencimento"], errors="coerce"
        ).dt.date

        df_edit = st.data_editor(
            df_orig,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            height=520,
            disabled=COLUNAS_BLOQUEADAS,
            column_config={
                "ticker":     st.column_config.TextColumn("Ticker", width="small"),
                "familia":    st.column_config.TextColumn("Família", width="medium"),
                "composite":  st.column_config.TextColumn("Composite", width="small"),
                "classe":     st.column_config.TextColumn("Classe", width="small"),
                "setor":      st.column_config.TextColumn("Setor ✏️", width="medium"),
                "benchmark":  st.column_config.TextColumn("Benchmark ✏️", width="medium"),
                "indexador":      st.column_config.TextColumn("Indexador", width="small"),
                "observacao":     st.column_config.TextColumn("Observação ✏️", width="large"),
                "data_vencimento": st.column_config.DateColumn(
                    "Vencimento ✏️", format="DD/MM/YYYY", width="small"
                ),
            },
            key="ativos_editor",
        )

        # Detectar linhas com alterações nas colunas editáveis
        linhas_alteradas = []
        for orig_row, edit_row in zip(df_orig.itertuples(), df_edit.itertuples()):
            for col in COLUNAS_EDITAVEIS:
                if getattr(orig_row, col) != getattr(edit_row, col):
                    linhas_alteradas.append(edit_row.ticker)
                    break

        if linhas_alteradas:
            st.info(
                f"✏️ {len(linhas_alteradas)} ativo(s) com alterações pendentes: "
                f"{', '.join(linhas_alteradas)}"
            )

        salvar = st.button(
            "💾 Salvar Alterações",
            type="primary",
            disabled=not linhas_alteradas,
            key="btn_salvar_ativos",
        )

        if salvar:
            st.session_state["confirmar_ativos"] = True

        if st.session_state.get("confirmar_ativos"):
            st.warning(
                f"⚠️ Tem certeza? Isso atualizará **{len(linhas_alteradas)} ativo(s)** no banco."
            )
            c1, c2, _ = st.columns([1, 1, 4])
            with c1:
                if st.button("✅ Confirmar", type="primary", key="btn_confirm_ativos"):
                    erros = []
                    for ticker in linhas_alteradas:
                        row = df_edit[df_edit["ticker"] == ticker].iloc[0]
                        dv = row["data_vencimento"]
                        payload = {
                            "setor":           row["setor"] or None,
                            "benchmark":       row["benchmark"] or None,
                            "observacao":      row["observacao"] or None,
                            "data_vencimento": str(dv) if pd.notna(dv) and dv is not None else None,
                        }
                        res = api.patch(f"ativos/{ticker}", data=payload)
                        if res is None:
                            erros.append(ticker)
                    st.session_state.pop("confirmar_ativos", None)
                    if erros:
                        st.error(f"Erro ao salvar: {', '.join(erros)}")
                    else:
                        st.success(f"✅ {len(linhas_alteradas)} ativo(s) atualizado(s)!")
                        st.rerun()
            with c2:
                if st.button("❌ Cancelar", key="btn_cancel_ativos"):
                    st.session_state.pop("confirmar_ativos", None)
                    st.rerun()

        st.divider()
        st.caption("Exportar tabela de ativos cadastrados:")
        fmt.botoes_exportar(df_orig, "cad_ativos", key="cfg_ativos")

    # ─── Aba 2: Premissas da Meta ─────────────────────────────────
    with aba[1]:
        st.subheader("Premissas da Projeção Patrimonial")
        st.caption(
            "Estes valores alimentam a página Meta Patrimônio. "
            "Ficam ativos enquanto o browser estiver aberto."
        )

        premissas = st.session_state.get(_META_KEY, _premissas_default())

        pm1, pm2 = st.columns(2)
        with pm1:
            meta_valor = st.number_input(
                "🎯 Meta patrimonial (R$)",
                min_value=100_000.0,
                max_value=50_000_000.0,
                value=float(premissas["meta_valor"]),
                step=100_000.0,
                format="%.0f",
                key="cfg_meta_valor",
            )
            aporte_funcef = st.number_input(
                "🏛️ Aporte FUNCEF mensal (R$)",
                min_value=0.0,
                value=float(premissas["aporte_funcef_mensal"]),
                step=100.0,
                format="%.2f",
                key="cfg_aporte_funcef",
            )
        with pm2:
            aporte_marco = st.number_input(
                "📅 Aporte Gerida — março (R$)",
                min_value=0.0,
                value=float(premissas["aporte_gerida_marco"]),
                step=1_000.0,
                format="%.0f",
                key="cfg_aporte_marco",
            )
            aporte_outubro = st.number_input(
                "📅 Aporte Gerida — outubro (R$)",
                min_value=0.0,
                value=float(premissas["aporte_gerida_outubro"]),
                step=1_000.0,
                format="%.0f",
                key="cfg_aporte_outubro",
            )

        aporte_anual_calc = aporte_funcef * 12 + aporte_marco + aporte_outubro
        st.info(
            f"Aporte anual calculado: **{fmt.moeda(aporte_anual_calc)}** "
            f"(FUNCEF {fmt.moeda(aporte_funcef)}/mês × 12 "
            f"+ março {fmt.moeda(aporte_marco)} + outubro {fmt.moeda(aporte_outubro)})"
        )

        if st.button("💾 Salvar e aplicar na Meta", type="primary", key="btn_salvar_premissas"):
            st.session_state[_META_KEY] = {
                "meta_valor":            meta_valor,
                "aporte_funcef_mensal":  aporte_funcef,
                "aporte_gerida_marco":   aporte_marco,
                "aporte_gerida_outubro": aporte_outubro,
            }
            st.success("✅ Premissas salvas! Acesse Meta Patrimônio para ver o novo cenário.")

    # ─── Aba 3: Informações do Sistema ───────────────────────────
    with aba[2]:
        st.subheader("Informações do Sistema")

        status = api.get("status")
        precos = api.get("precos-manuais") or []

        if status:
            if status.get("erro"):
                st.error(f"🔴 Erro no engine: {status['erro']}")
            elif status.get("n_eventos", 0) > 0:
                st.success(f"✅ Engine OK — calculado em {status.get('calculado_em', '—')}")
            else:
                st.warning("⚠️ Engine ainda não calculado.")

            s1, s2, s3, s4 = st.columns(4)
            with s1:
                fmt.card_kpi("Versão", "2.3.0")
            with s2:
                calc_em = status.get("calculado_em", "")
                fmt.card_kpi("Último cálculo", calc_em[:16].replace("T", " ") if calc_em else "—")
            with s3:
                fmt.card_kpi(
                    "Ativos | Eventos",
                    f"{status.get('n_ativos', 0)} | {status.get('n_eventos', 0)}",
                )
            with s4:
                fmt.card_kpi("Preços manuais", str(len(precos)))

        st.divider()
        st.markdown("**Forçar recálculo:**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Recalcular (sem API externa)", type="primary",
                         use_container_width=True, key="btn_recalc_noapi"):
                with st.spinner("Calculando..."):
                    res = api.post("calcular", params={"no_api": "true"})
                if res and res.get("ok"):
                    st.success(
                        f"✅ Recalculado! "
                        f"Patrimônio: {fmt.moeda(res.get('patrimonio_total'))} | "
                        f"P&L RV: {fmt.moeda(res.get('pnl_vendas_rv'), sinal=True)}"
                    )
                    st.rerun()
        with c2:
            if st.button("🌐 Recalcular (com preços de mercado)",
                         use_container_width=True, key="btn_recalc_api"):
                with st.spinner("Baixando preços e calculando… (pode demorar até 60s)"):
                    res = api.post("calcular", params={"no_api": "false"})
                if res and res.get("ok"):
                    st.success(
                        f"✅ Atualizado com preços de mercado! "
                        f"Patrimônio: {fmt.moeda(res.get('patrimonio_total'))}"
                    )
                    st.rerun()

        if status and status.get("alertas"):
            st.divider()
            st.subheader(f"Alertas ativos ({len(status['alertas'])})")
            for a in status["alertas"]:
                msg = f"**{a['ativo']}**: {a['mensagem']}"
                if a["nivel"] == "ERRO":
                    st.error(f"🔴 {msg}")
                elif a["nivel"] == "AVISO":
                    st.warning(f"🟡 {msg}")
                else:
                    st.info(f"🔵 {msg}")

        st.divider()
        st.markdown("**💾 Backup do banco de dados:**")
        if st.button("💾 Fazer backup agora", use_container_width=True,
                     key="btn_backup_manual"):
            with st.spinner("Fazendo backup..."):
                res = api.post("backup")
            if res and res.get("ok"):
                st.success(
                    f"✅ Backup criado: `{res['arquivo']}` "
                    f"({res.get('tamanho_bytes', 0) // 1024} KB)"
                )
            else:
                st.error("❌ Falha ao criar backup.")

        backups = api.get("backup/listar") or []
        if backups:
            st.caption("Últimos 5 backups (em ~/Carteira/backups/):")
            df_bkp = pd.DataFrame(backups)
            df_bkp["tamanho"] = df_bkp["tamanho_bytes"].apply(
                lambda x: f"{x // 1024} KB"
            )
            df_bkp = df_bkp[["arquivo", "criado_em", "tamanho"]]
            df_bkp.columns = ["Arquivo", "Criado em", "Tamanho"]
            st.dataframe(df_bkp, hide_index=True, use_container_width=True)
        else:
            st.caption("Nenhum backup encontrado em ~/Carteira/backups/")
