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

        if arquivo and st.button("🤖 Processar com Claude", type="primary", use_container_width=True):
            spinner_msg = (
                "Enviando para o Claude identificar e extrair... (~15-60s)"
                if tipo_documento == "auto"
                else f"Extraindo eventos ({tipo_label_sel})... (~15-60s)"
            )
            with st.spinner(spinner_msg):
                try:
                    resultado = _chamar_upload(arquivo, tipo_documento)
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
    if preview and preview.get("status") == "PREVIEW":
        _render_preview(preview)

    # ─── Seção 3: Histórico ──────────────────────────────────────────────────
    _render_historico()


def _chamar_upload(arquivo, tipo_documento: str) -> dict:
    """Envia arquivo para o endpoint de upload via requests multipart."""
    import requests
    from carteira_clean_web.frontend.utils.api import API_BASE
    url = f"{API_BASE}/importacao/upload"
    conteudo = arquivo.read() if hasattr(arquivo, "read") else arquivo.getvalue()
    files = {"arquivo": (arquivo.name, conteudo, arquivo.type or "application/octet-stream")}
    data = {"tipo_documento": tipo_documento}
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

    with col_ok:
        if st.button(f"✅ Confirmar {n_sel} eventos", type="primary", use_container_width=True, disabled=n_sel == 0):
            indices = [i for i, row in df_edit.iterrows() if row["incluir"]]
            with st.spinner("Gravando eventos..."):
                res = api.post(f"importacao/{imp_id}/confirmar", data={"indices_aprovados": indices})
            if res and res.get("ok"):
                gravados = res.get("eventos_gravados", 0)
                st.success(f"✅ {gravados} eventos importados com sucesso!")
                st.session_state.pop("importacao_preview", None)
                st.session_state.pop("importacao_eventos_sel", None)
                st.rerun()
            else:
                st.error("Erro ao confirmar importação.")

    with col_cancel:
        if st.button("❌ Cancelar", use_container_width=True, key=f"cancel_{imp_id}"):
            _cancelar(imp_id)


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
