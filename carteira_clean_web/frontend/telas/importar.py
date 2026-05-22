"""
Tela de importação de extratos via Claude API.
"""

import json

import pandas as pd
import streamlit as st

from carteira_clean_web.frontend.utils import api
from carteira_clean_web.backend.engine.importacao.detector import TIPOS_DOCUMENTO, TIPO_LABELS


class _TipoConflito(Exception):
    def __init__(self, mensagem: str, tipo_detectado: str, tipo_informado: str):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.tipo_detectado = tipo_detectado
        self.tipo_informado = tipo_informado


def render():
    st.title("📥 Importar Extrato")
    st.caption("Importe PDFs, imagens ou planilhas de extratos. O Claude extrai os eventos automaticamente.")

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
                help="Selecione o tipo do documento para orientar a extração.",
            )
            tipo_documento = opcoes_tipo[tipo_label_sel]

        if arquivo and st.button("🤖 Processar com Claude", type="primary", use_container_width=True):
            with st.spinner("Lendo arquivo e enviando para o Claude... (~15-60s)"):
                try:
                    resultado = _chamar_upload(arquivo, tipo_documento)
                    # Mostra alertas pré-processamento (ex: PDF longo)
                    for alerta in resultado.get("alertas", []):
                        st.warning(f"⚠️ {alerta}")
                    st.session_state["importacao_preview"] = resultado
                    st.session_state["importacao_eventos_sel"] = {
                        i: not ev.get("duplicata", False)
                        for i, ev in enumerate(resultado.get("eventos", []))
                    }
                    st.rerun()
                except _TipoConflito as e:
                    # Divergência detector vs. seleção manual
                    st.warning(f"⚠️ {e.mensagem}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button(f"Usar tipo detectado: {e.tipo_detectado}", use_container_width=True):
                            st.session_state["tipo_override"] = e.tipo_detectado
                            st.rerun()
                    with col_b:
                        if st.button(f"Forçar tipo selecionado: {tipo_documento}", use_container_width=True):
                            with st.spinner("Processando com override..."):
                                try:
                                    resultado = _chamar_upload(arquivo, tipo_documento, confirmar_override=True)
                                    st.session_state["importacao_preview"] = resultado
                                    st.rerun()
                                except Exception as e2:
                                    st.error(f"Erro: {e2}")
                except Exception as e:
                    st.error(f"Erro: {e}")

    # ─── Seção 2: Preview ─────────────────────────────────────────────────────
    preview = st.session_state.get("importacao_preview")
    if preview and preview.get("status") == "PREVIEW":
        _render_preview(preview)

    # ─── Seção 3: Histórico ──────────────────────────────────────────────────
    _render_historico()


def _chamar_upload(arquivo, tipo_documento: str, confirmar_override: bool = False) -> dict:
    """Envia arquivo para o endpoint de upload via requests multipart."""
    import requests
    from carteira_clean_web.frontend.utils.api import API_BASE
    url = f"{API_BASE}/importacao/upload"
    conteudo = arquivo.read() if hasattr(arquivo, "read") else arquivo.getvalue()
    files = {"arquivo": (arquivo.name, conteudo, arquivo.type or "application/octet-stream")}
    data = {"tipo_documento": tipo_documento, "confirmar_override": str(confirmar_override).lower()}
    resp = requests.post(url, files=files, data=data, timeout=120)
    if resp.status_code == 409:
        detail = resp.json().get("detail", {})
        # Verifica se é conflito de tipo ou arquivo duplicado
        if isinstance(detail, dict) and "tipo_detectado" in detail:
            raise _TipoConflito(
                mensagem=detail.get("mensagem", "Tipo de documento divergente"),
                tipo_detectado=detail["tipo_detectado"],
                tipo_informado=detail["tipo_informado"],
            )
        msg = detail if isinstance(detail, str) else detail.get("mensagem", "Arquivo já importado anteriormente.")
        raise Exception(msg)
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

    st.divider()
    st.subheader(f"🔍 Preview — {len(eventos)} eventos extraídos")

    col1, col2, col3 = st.columns(3)
    col1.metric("Eventos", len(eventos))
    col2.metric("Duplicatas", n_dup, help="Já existem no banco — marcados para ignorar")
    col3.metric("Custo API", f"${custo:.4f}")

    if not eventos:
        st.info("Nenhum evento extraído. Verifique se o tipo do documento está correto.")
        if st.button("Cancelar"):
            _cancelar(imp_id)
        return

    # Converte para DataFrame editável
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

    n_sel = df_edit["incluir"].sum()
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
        if st.button("❌ Cancelar", use_container_width=True):
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

    if not res:
        st.info("Nenhuma importação registrada.")
        return

    df = pd.DataFrame(res)
    if df.empty:
        st.info("Nenhuma importação registrada.")
        return

    colunas = ["id", "data_upload", "arquivo_nome", "tipo_documento", "status",
               "total_eventos_extraidos", "total_eventos_gravados", "custo_api_usd"]
    df_show = df[[c for c in colunas if c in df.columns]].copy()
    df_show.columns = [c.replace("_", " ").title() for c in df_show.columns]

    status_cores = {
        "CONFIRMED": "✅",
        "PREVIEW": "🔍",
        "PROCESSING": "⏳",
        "CANCELLED": "❌",
        "ERROR": "🚨",
        "UPLOADED": "📤",
    }
    if "Status" in df_show.columns:
        df_show["Status"] = df_show["Status"].map(lambda s: f"{status_cores.get(s, '')} {s}")

    st.dataframe(df_show, hide_index=True, use_container_width=True)
