"""
Tela de importação de extratos via Claude API.
"""

import json

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api
from carteira_clean_web.backend.engine.importacao.detector import (
    TIPOS_DOCUMENTO, TIPO_LABELS, CONFIANCA_ICON,
)


def render():
    st.title("📥 Importar Extrato")
    st.caption("Importe PDFs, imagens ou planilhas de extratos. O Claude identifica o tipo e extrai os eventos automaticamente.")

    # ─── Seção 1: Upload ───────────────────────────────────────────────────────
    with st.expander("📤 Enviar novo extrato", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            arquivo = st.file_uploader(
                "Selecione o arquivo",
                type=["pdf", "jpg", "jpeg", "png", "xlsx", "csv"],
                help="PDF (nativo ou escaneado), JPEG, PNG, XLSX ou CSV. Máx. 32 MB.",
            )
        with col2:
            opcoes_tipo = {TIPO_LABELS.get(t, t): t for t in TIPOS_DOCUMENTO}
            tipo_label_sel = st.selectbox(
                "Tipo do documento",
                list(opcoes_tipo.keys()),
                index=0,  # "auto" é sempre o primeiro
                help=(
                    "**Detectar automaticamente** (recomendado): o Claude identifica o tipo "
                    "e você confirma no preview.\n\n"
                    "Selecione um tipo manualmente apenas se souber que o documento é atípico."
                ),
            )
            tipo_documento = opcoes_tipo[tipo_label_sel]

        dry_run = st.checkbox(
            "🧪 Modo de teste (não gravar no banco)",
            value=False,
            help=(
                "Envia o arquivo para o Claude e exibe o JSON extraído, mas **não cria nenhum registro** "
                "no banco de dados. Use para validar extratos novos antes de confirmar."
            ),
        )

        btn_label = "🧪 Testar com Claude (sem gravar)" if dry_run else "🤖 Processar com Claude"
        if arquivo and st.button(btn_label, type="primary", use_container_width=True):
            spinner_msg = (
                "Enviando para o Claude identificar e extrair... (~15-60s)"
                if tipo_documento == "auto"
                else f"Extraindo eventos ({tipo_label_sel})... (~15-60s)"
            )
            with st.spinner(spinner_msg):
                try:
                    resultado = _chamar_upload(arquivo, tipo_documento, dry_run=dry_run)
                    for alerta in resultado.get("alertas", []):
                        st.warning(f"⚠️ {alerta}")
                    st.session_state["importacao_preview"] = resultado
                    st.session_state["importacao_eventos_sel"] = {
                        i: not ev.get("duplicata", False)
                        for i, ev in enumerate(resultado.get("eventos", []))
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # ─── Seção 2: Preview ─────────────────────────────────────────────────────
    preview = st.session_state.get("importacao_preview")
    if preview:
        status = preview.get("status")
        if status == "DRY_RUN":
            _render_dry_run_preview(preview)
        elif status == "PREVIEW":
            _render_preview(preview)

    # ─── Seção 3: Histórico ──────────────────────────────────────────────────
    _render_historico()


def _chamar_upload(arquivo, tipo_documento: str, dry_run: bool = False) -> dict:
    """Envia arquivo para o endpoint de upload via requests multipart."""
    import requests
    from carteira_clean_web.frontend.utils.api import API_BASE
    url = f"{API_BASE}/importacao/upload"
    conteudo = arquivo.read() if hasattr(arquivo, "read") else arquivo.getvalue()
    files = {"arquivo": (arquivo.name, conteudo, arquivo.type or "application/octet-stream")}
    data = {"tipo_documento": tipo_documento, "dry_run": "true" if dry_run else "false"}
    resp = requests.post(url, files=files, data=data, timeout=120)
    if resp.status_code == 409:
        try:
            detail = resp.json().get("detail", "Arquivo já importado anteriormente.")
        except Exception:
            detail = "Arquivo já importado anteriormente."
        raise Exception(detail if isinstance(detail, str) else str(detail))
    if not resp.ok:
        try:
            detalhe = resp.json().get("detail", resp.text[:300])
        except Exception:
            detalhe = resp.text[:300]
        raise Exception(f"HTTP {resp.status_code}: {detalhe}")
    return resp.json()


def _chamar_reprocessar(imp_id: int, tipo_documento: str) -> dict:
    """Reprocessa importação já arquivada com novo tipo."""
    import requests
    from carteira_clean_web.frontend.utils.api import API_BASE
    url = f"{API_BASE}/importacao/{imp_id}/reprocessar"
    resp = requests.post(url, json={"tipo_documento": tipo_documento}, timeout=120)
    if not resp.ok:
        try:
            detalhe = resp.json().get("detail", resp.text[:300])
        except Exception:
            detalhe = resp.text[:300]
        raise Exception(f"HTTP {resp.status_code}: {detalhe}")
    return resp.json()


def _render_dry_run_preview(preview: dict):
    """Renderiza preview do modo de teste (dry_run) — sem importação_id no DB."""
    eventos = preview.get("eventos", [])
    n_dup = preview.get("duplicatas", 0)
    custo = preview.get("custo_api_usd", 0)
    tipo_id = preview.get("tipo_identificado")
    confianca = preview.get("confianca")
    justificativa = preview.get("justificativa")
    raw_json = preview.get("raw_json_ia", "")

    st.divider()
    st.info("🧪 **Modo de teste** — os dados abaixo foram extraídos pelo Claude, mas **nada foi gravado** no banco. Revise e confirme se estiverem corretos.")

    # ── Banner de identificação ───────────────────────────────────────────────
    if tipo_id and confianca:
        icon = CONFIANCA_ICON.get(confianca, "⚪")
        label = TIPO_LABELS.get(tipo_id, tipo_id)
        with st.container(border=True):
            st.markdown(f"**🤖 Identificado pelo Claude:** {icon} {label} (confiança {confianca})")
            if justificativa:
                st.caption(justificativa)

    st.subheader(f"🔍 Resultado do teste — {len(eventos)} eventos extraídos")

    col1, col2, col3 = st.columns(3)
    col1.metric("Eventos", len(eventos))
    col2.metric("Duplicatas", n_dup, help="Já existem no banco — serão ignoradas")
    col3.metric("Custo API", f"${custo:.4f}")

    # ── JSON bruto expandível ─────────────────────────────────────────────────
    _render_expander_json(preview, key_suffix="dry")

    if not eventos:
        st.warning("Nenhum evento foi extraído. Verifique o tipo do documento e tente novamente.")
        if st.button("🗑️ Descartar resultado", key="dry_run_descartar_vazio"):
            st.session_state.pop("importacao_preview", None)
            st.session_state.pop("importacao_eventos_sel", None)
            st.rerun()
        return

    # ── Tabela editável ───────────────────────────────────────────────────────
    sel_state = st.session_state.get("importacao_eventos_sel", {})
    df_rows = []
    for i, ev in enumerate(eventos):
        status_icon = "⚠️ Duplicata" if ev.get("duplicata") else "✅ Novo"
        df_rows.append({
            "incluir": sel_state.get(i, not ev.get("duplicata", False)),
            "status": status_icon,
            "data": ev.get("data", ""),
            "ativo": ev.get("ativo", ""),
            "tipo": ev.get("tipo", ""),
            "qtd": ev.get("qtd"),
            "preco": ev.get("preco"),
            "valor": ev.get("valor", 0),
            "obs": ev.get("obs", ""),
        })

    df = pd.DataFrame(df_rows)
    st.caption("Revise os eventos extraídos. Desmarque os que não devem ser gravados. Quando estiver tudo certo, clique em Confirmar e Gravar.")

    df_edit = st.data_editor(
        df,
        column_config={
            "incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "status": st.column_config.TextColumn("Status", width="medium"),
            "data": st.column_config.TextColumn("Data"),
            "ativo": st.column_config.TextColumn("Ativo"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "qtd": st.column_config.NumberColumn("Qtd", format="%.4f"),
            "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "obs": st.column_config.TextColumn("Obs"),
        },
        hide_index=True,
        use_container_width=True,
        key="editor_dry_run",
    )

    n_sel = int(df_edit["incluir"].sum())
    col_ok, col_cancel = st.columns(2)

    # Conflito de cotas pendente de resolução
    conflito = st.session_state.get("funcef_conflito_pendente")
    if conflito:
        _render_conflito_cotas(conflito, endpoint="importacao/confirmar-direto")

    with col_ok:
        if not conflito and st.button(
            f"✅ Confirmar e gravar {n_sel} eventos",
            type="primary",
            use_container_width=True,
            disabled=n_sel == 0,
        ):
            indices = [i for i, row in df_edit.iterrows() if row["incluir"]]
            body = {
                "eventos": eventos,
                "indices_aprovados": indices,
                "arquivo_path": preview.get("arquivo_path"),
                "arquivo_hash": preview.get("arquivo_hash"),
                "nome_arquivo": preview.get("nome_arquivo"),
                "tipo_documento": preview.get("tipo_documento"),
                "custo_api_usd": custo,
                "meta": {
                    "tipo_identificado": tipo_id,
                    "confianca": confianca,
                    "justificativa": justificativa,
                },
            }
            with st.spinner("Gravando eventos no banco..."):
                res = api.post("importacao/confirmar-direto", data=body)
            _processar_resultado_confirmacao(res, body, "importacao/confirmar-direto")

    with col_cancel:
        if st.button("🗑️ Descartar (não gravar)", use_container_width=True, key="dry_run_descartar"):
            st.session_state.pop("importacao_preview", None)
            st.session_state.pop("importacao_eventos_sel", None)
            st.session_state.pop("funcef_conflito_pendente", None)
            st.rerun()


def _render_preview(preview: dict):
    imp_id = preview["importacao_id"]
    eventos = preview.get("eventos", [])
    n_dup = preview.get("duplicatas", 0)
    custo = preview.get("custo_api_usd", 0)
    tipo_id = preview.get("tipo_identificado")
    confianca = preview.get("confianca")
    justificativa = preview.get("justificativa")

    st.divider()

    # ── Banner de identificação automática ───────────────────────────────────
    if tipo_id and confianca:
        icon = CONFIANCA_ICON.get(confianca, "⚪")
        label = TIPO_LABELS.get(tipo_id, tipo_id)
        with st.container(border=True):
            col_info, col_reprocess = st.columns([3, 1])
            with col_info:
                st.markdown(f"**🤖 Identificado pelo Claude:** {icon} {label} (confiança {confianca})")
                if justificativa:
                    st.caption(justificativa)
            with col_reprocess:
                # Permite corrigir o tipo e reprocessar sem novo upload
                opcoes = {TIPO_LABELS.get(t, t): t for t in TIPOS_DOCUMENTO if t != "auto"}
                tipo_atual_label = TIPO_LABELS.get(tipo_id, tipo_id)
                idx_atual = list(opcoes.keys()).index(tipo_atual_label) if tipo_atual_label in opcoes else 0
                novo_tipo_label = st.selectbox(
                    "Corrigir tipo",
                    list(opcoes.keys()),
                    index=idx_atual,
                    key=f"reprocess_tipo_{imp_id}",
                    label_visibility="collapsed",
                )
                novo_tipo = opcoes[novo_tipo_label]
                if novo_tipo != tipo_id:
                    if st.button("🔄 Reprocessar", use_container_width=True, key=f"btn_reprocess_{imp_id}"):
                        with st.spinner(f"Reprocessando como {novo_tipo_label}..."):
                            try:
                                resultado = _chamar_reprocessar(imp_id, novo_tipo)
                                st.session_state["importacao_preview"] = resultado
                                st.session_state["importacao_eventos_sel"] = {
                                    i: not ev.get("duplicata", False)
                                    for i, ev in enumerate(resultado.get("eventos", []))
                                }
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao reprocessar: {e}")

    st.subheader(f"🔍 Preview — {len(eventos)} eventos extraídos")

    col1, col2, col3 = st.columns(3)
    col1.metric("Eventos", len(eventos))
    col2.metric("Duplicatas", n_dup, help="Já existem no banco — marcados para ignorar")
    col3.metric("Custo API", f"${custo:.4f}")

    # ── JSON bruto expandível ─────────────────────────────────────────────────
    _render_expander_json(preview, imp_id)

    if not eventos:
        st.info("Nenhum evento extraído. Se o tipo identificado estiver errado, corrija acima e clique em Reprocessar.")
        if st.button("❌ Cancelar", key=f"cancel_empty_{imp_id}"):
            _cancelar(imp_id)
        return

    # ── Tabela editável de eventos ───────────────────────────────────────────
    sel_state = st.session_state.get("importacao_eventos_sel", {})
    df_rows = []
    for i, ev in enumerate(eventos):
        status_icon = "⚠️ Duplicata" if ev.get("duplicata") else "✅ Novo"
        df_rows.append({
            "incluir": sel_state.get(i, not ev.get("duplicata", False)),
            "status": status_icon,
            "data": ev.get("data", ""),
            "ativo": ev.get("ativo", ""),
            "tipo": ev.get("tipo", ""),
            "qtd": ev.get("qtd"),
            "preco": ev.get("preco"),
            "valor": ev.get("valor", 0),
            "obs": ev.get("obs", ""),
        })

    df = pd.DataFrame(df_rows)
    st.caption("Desmarque eventos que não devem ser importados. Duplicatas já estão desmarcadas.")

    df_edit = st.data_editor(
        df,
        column_config={
            "incluir": st.column_config.CheckboxColumn("Incluir", width="small"),
            "status": st.column_config.TextColumn("Status", width="medium"),
            "data": st.column_config.TextColumn("Data"),
            "ativo": st.column_config.TextColumn("Ativo"),
            "tipo": st.column_config.TextColumn("Tipo"),
            "qtd": st.column_config.NumberColumn("Qtd", format="%.4f"),
            "preco": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "obs": st.column_config.TextColumn("Obs"),
        },
        hide_index=True,
        use_container_width=True,
        key=f"editor_preview_{imp_id}",
    )

    n_sel = int(df_edit["incluir"].sum())
    col_ok, col_cancel = st.columns(2)

    # Conflito de cotas pendente de resolução
    conflito = st.session_state.get("funcef_conflito_pendente")
    if conflito:
        _render_conflito_cotas(conflito, endpoint=f"importacao/{imp_id}/confirmar")

    with col_ok:
        if not conflito and st.button(
            f"✅ Confirmar {n_sel} eventos",
            type="primary",
            use_container_width=True,
            disabled=n_sel == 0,
        ):
            indices = [i for i, row in df_edit.iterrows() if row["incluir"]]
            body = {"indices_aprovados": indices}
            with st.spinner("Gravando eventos..."):
                res = api.post(f"importacao/{imp_id}/confirmar", data=body)
            _processar_resultado_confirmacao(res, body, f"importacao/{imp_id}/confirmar")

    with col_cancel:
        if st.button("❌ Cancelar", use_container_width=True, key=f"cancel_{imp_id}"):
            st.session_state.pop("funcef_conflito_pendente", None)
            _cancelar(imp_id)


def _render_expander_json(preview: dict, key_suffix: str = ""):
    """
    Expander com a resposta BRUTA da IA — útil para auditoria e debug.
    Prioridade: raw_claude_response (texto puro da IA) > raw_json_ia > dados processados.
    """
    with st.expander("🔍 Ver JSON extraído pela IA", expanded=False):
        raw_bruto = preview.get("raw_claude_response", "")
        if raw_bruto:
            st.caption("Resposta bruta do Claude (antes de qualquer parse pelo sistema):")
            st.code(raw_bruto, language="json")
        else:
            # Fallback: mostra dados processados quando raw não disponível (PREVIEW normal)
            eventos_limpos = [
                {k: v for k, v in ev.items() if not k.startswith("_")}
                for ev in preview.get("eventos", [])
            ]
            dados_exibir = {
                "tipo_identificado": preview.get("tipo_identificado"),
                "confianca": preview.get("confianca"),
                "eventos": eventos_limpos,
            }
            # Tenta extrair bloco debug da IA a partir do raw_json_ia
            raw = preview.get("raw_json_ia", "")
            if raw:
                try:
                    raw_parsed = json.loads(raw)
                    meta = raw_parsed.get("meta", {})
                    if "raw_claude_response" in meta:
                        st.caption("Resposta bruta do Claude:")
                        st.code(meta["raw_claude_response"], language="json")
                        return
                    if "debug" in meta:
                        dados_exibir["_debug_ia"] = meta["debug"]
                except Exception:
                    pass
            st.caption("Dados processados (raw_claude_response não disponível nesta importação):")
            st.json(dados_exibir)


def _processar_resultado_confirmacao(res: dict | None, body_original: dict, endpoint: str):
    """Trata resposta do /confirmar ou /confirmar-direto, exibindo alertas FUNCEF se necessário."""
    if not res or not res.get("ok"):
        st.error("Erro ao confirmar importação.")
        return

    gravados = res.get("eventos_gravados", 0)
    cotas_inseridas = res.get("cotas_inseridas", 0)
    cotas_conflito = res.get("cotas_conflito", [])
    rec = res.get("reconciliacao", {})

    st.success(f"✅ {gravados} eventos gravados com sucesso!" +
               (f" | {cotas_inseridas} cota(s) FUNCEF salva(s)." if cotas_inseridas else ""))

    # Alerta de reconciliação FUNCEF
    if rec.get("alerta_criado"):
        st.warning(
            f"⚠️ {rec.get('alerta_mensagem', 'FUNCEF: divergência detectada.')} "
            f"(calc: R${rec.get('patrimonio_calculado', 0):,.2f} "
            f"vs extrato: aprox. ver log)"
        )

    if cotas_conflito:
        # Armazena conflito no state para o widget de resolução aparecer
        st.session_state["funcef_conflito_pendente"] = {
            "conflitos": cotas_conflito,
            "body_original": body_original,
            "endpoint": endpoint,
        }
        st.rerun()
    else:
        st.session_state.pop("importacao_preview", None)
        st.session_state.pop("importacao_eventos_sel", None)
        st.session_state.pop("funcef_conflito_pendente", None)
        st.rerun()


def _render_conflito_cotas(conflito: dict, endpoint: str):
    """Exibe conflitos de cota FUNCEF e oferece opção de forçar atualização."""
    lista = conflito.get("conflitos", [])
    if not lista:
        st.session_state.pop("funcef_conflito_pendente", None)
        return

    with st.container(border=True):
        st.warning(
            f"⚠️ **{len(lista)} cota(s) FUNCEF com valor divergente** — "
            f"não foram atualizadas automaticamente."
        )
        rows = [{
            "data": c["data"],
            "valor_atual": c["valor_existente"],
            "valor_novo": c["valor_novo"],
            "diferença %": c["diferenca_pct"],
        } for c in lista]
        st.dataframe(rows, hide_index=True, use_container_width=True)
        st.caption(
            "Os valores acima já existem em HISTORICO_PRECOS com valor diferente. "
            "Clique em **Forçar atualização** para sobrescrever com os valores do extrato. "
            "Se preferir manter os valores atuais, clique em **Ignorar conflitos**."
        )
        col_force, col_ignore = st.columns(2)
        with col_force:
            if st.button("🔄 Forçar atualização de cotas", type="primary", use_container_width=True):
                body = dict(conflito.get("body_original", {}))
                body["force_update_cotas"] = True
                with st.spinner("Atualizando cotas e finalizando..."):
                    res = api.post(endpoint, data=body)
                if res and res.get("ok"):
                    cotas_ins = res.get("cotas_inseridas", 0)
                    st.success(f"✅ {cotas_ins} cota(s) atualizada(s) com sucesso!")
                else:
                    st.error("Erro ao forçar atualização.")
                st.session_state.pop("importacao_preview", None)
                st.session_state.pop("importacao_eventos_sel", None)
                st.session_state.pop("funcef_conflito_pendente", None)
                st.rerun()
        with col_ignore:
            if st.button("⏭️ Ignorar conflitos (manter valores atuais)", use_container_width=True):
                st.session_state.pop("importacao_preview", None)
                st.session_state.pop("importacao_eventos_sel", None)
                st.session_state.pop("funcef_conflito_pendente", None)
                st.rerun()


def _cancelar(imp_id: int):
    res = api.delete(f"importacao/{imp_id}")
    if res:
        st.info("Importação cancelada.")
        st.session_state.pop("importacao_preview", None)
        st.session_state.pop("importacao_eventos_sel", None)
        st.rerun()


def _render_historico():
    st.divider()
    st.subheader("📋 Histórico de importações")

    res = api.get("importacoes")
    if not res:
        st.info("Nenhuma importação registrada.")
        return

    df = pd.DataFrame(res)
    if df.empty:
        st.info("Nenhuma importação registrada.")
        return

    colunas = [
        "id", "data_upload", "arquivo_nome",
        "tipo_identificado_ia", "confianca_ia", "status",
        "total_eventos_extraidos", "total_eventos_gravados", "custo_api_usd",
    ]
    df_show = df[[c for c in colunas if c in df.columns]].copy()

    status_cores = {"CONFIRMED": "✅", "PREVIEW": "🔍", "PROCESSING": "⏳",
                    "CANCELLED": "❌", "ERROR": "🚨", "UPLOADED": "📤"}
    confianca_cores = {"alta": "🟢", "media": "🟡", "baixa": "🔴"}

    if "status" in df_show.columns:
        df_show["status"] = df_show["status"].map(lambda s: f"{status_cores.get(s,'')} {s}")
    if "confianca_ia" in df_show.columns:
        df_show["confianca_ia"] = df_show["confianca_ia"].map(
            lambda c: f"{confianca_cores.get(c,'')} {c}" if c else ""
        )
    if "tipo_identificado_ia" in df_show.columns:
        df_show["tipo_identificado_ia"] = df_show["tipo_identificado_ia"].map(
            lambda t: TIPO_LABELS.get(t, t) if t else ""
        )

    df_show.columns = [
        c.replace("_ia", " (IA)").replace("_", " ").title()
        for c in df_show.columns
    ]
    st.dataframe(df_show, hide_index=True, use_container_width=True)
