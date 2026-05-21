"""
POST /api/v1/importacao/upload     — recebe arquivo, chama Claude, retorna preview
GET  /api/v1/importacao/{id}/preview — retorna eventos com marcação de duplicata
POST /api/v1/importacao/{id}/confirmar — grava eventos aprovados no banco
DELETE /api/v1/importacao/{id}     — cancela importação
GET  /api/v1/importacoes           — histórico
"""

import hashlib
import json
import logging
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Evento, Importacao, ImportacaoEvento

log = logging.getLogger("api.importacao")
router = APIRouter(tags=["Importação"])


def _arquivo_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _arquivo_dir(ano: int, mes: int) -> Path:
    base = Path.home() / "Carteira" / "extratos" / str(ano) / f"{mes:02d}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _hashes_existentes(db: Session) -> set[str]:
    """Retorna set de hashes de todos os eventos já gravados (para detecção de duplicatas)."""
    rows = db.query(Evento).with_entities(
        Evento.data, Evento.ativo, Evento.tipo, Evento.qtd, Evento.valor
    ).all()
    hashes = set()
    for r in rows:
        from carteira_clean_web.backend.engine.importacao.extrator import calcular_hash_evento
        h = calcular_hash_evento(str(r.data), r.ativo, r.tipo, r.qtd, r.valor)
        hashes.add(h)
    return hashes


def _proximo_linha_excel(db: Session) -> int:
    from sqlalchemy import func
    max_linha = db.query(func.max(Evento.linha_excel)).scalar() or 0
    return max_linha + 1


@router.post("/importacao/upload")
async def upload_extrato(
    arquivo: UploadFile = File(...),
    tipo_documento: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Recebe arquivo, processa com Claude e retorna preview de eventos.
    """
    from carteira_clean_web.backend.engine.importacao.extrator import extrair_eventos
    from carteira_clean_web.backend.engine.importacao.detector import TIPOS_DOCUMENTO

    if tipo_documento not in TIPOS_DOCUMENTO:
        raise HTTPException(400, f"tipo_documento inválido. Use um de: {TIPOS_DOCUMENTO}")

    conteudo = await arquivo.read()
    if len(conteudo) == 0:
        raise HTTPException(400, "Arquivo vazio")
    if len(conteudo) > 32 * 1024 * 1024:
        raise HTTPException(400, "Arquivo excede 32 MB")

    arquivo_hash = _arquivo_hash(conteudo)
    nome_arquivo = arquivo.filename or "documento"

    # Verifica se este arquivo já foi importado antes
    importacao_anterior = db.query(Importacao).filter(
        Importacao.arquivo_hash == arquivo_hash,
        Importacao.status == "CONFIRMED",
    ).first()
    if importacao_anterior:
        raise HTTPException(409, f"Este arquivo já foi importado (importação #{importacao_anterior.id})")

    # Cria registro de importação
    imp = Importacao(
        arquivo_nome=nome_arquivo,
        arquivo_hash=arquivo_hash,
        formato=nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else "desconhecido",
        tipo_documento=tipo_documento,
        status="PROCESSING",
        data_upload=datetime.utcnow(),
    )
    db.add(imp)
    db.commit()
    db.refresh(imp)

    try:
        # Chama Claude
        eventos, custo = extrair_eventos(conteudo, nome_arquivo, tipo_documento)

        # Detecta duplicatas
        hashes_existentes = _hashes_existentes(db)
        for ev in eventos:
            ev["duplicata"] = ev["hash"] in hashes_existentes

        # Arquiva o arquivo original
        agora = datetime.utcnow()
        dest_dir = _arquivo_dir(agora.year, agora.month)
        dest_path = dest_dir / f"{arquivo_hash[:8]}-{nome_arquivo}"
        try:
            dest_path.write_bytes(conteudo)
        except Exception as e:
            log.warning(f"Falha ao arquivar {nome_arquivo}: {e}")

        # Atualiza registro
        n_dup = sum(1 for ev in eventos if ev["duplicata"])
        imp.status = "PREVIEW"
        imp.total_eventos_extraidos = len(eventos)
        imp.total_eventos_duplicados = n_dup
        imp.custo_api_usd = custo
        imp.eventos_extraidos_json = json.dumps(eventos, default=str)
        imp.arquivo_path = str(dest_path)
        db.commit()

        return {
            "importacao_id": imp.id,
            "status": "PREVIEW",
            "total_eventos": len(eventos),
            "duplicatas": n_dup,
            "custo_api_usd": round(custo, 6),
            "eventos": eventos,
        }

    except Exception as e:
        imp.status = "ERROR"
        imp.erro_mensagem = str(e)
        db.commit()
        log.error(f"Erro na importação {imp.id}: {e}", exc_info=True)
        raise HTTPException(500, f"Erro ao processar arquivo: {str(e)}")


@router.get("/importacao/{importacao_id}/preview")
def get_preview(importacao_id: int, db: Session = Depends(get_db)):
    """Retorna eventos extraídos com marcação de duplicata."""
    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    if imp.status not in ("PREVIEW", "CONFIRMED"):
        raise HTTPException(400, f"Importação no status '{imp.status}' não tem preview disponível")

    eventos = json.loads(imp.eventos_extraidos_json) if imp.eventos_extraidos_json else []
    return {
        "importacao_id": imp.id,
        "status": imp.status,
        "arquivo_nome": imp.arquivo_nome,
        "tipo_documento": imp.tipo_documento,
        "total_eventos": len(eventos),
        "duplicatas": imp.total_eventos_duplicados,
        "custo_api_usd": imp.custo_api_usd,
        "eventos": eventos,
    }


@router.post("/importacao/{importacao_id}/confirmar")
def confirmar_importacao(
    importacao_id: int,
    body: dict = Body(default=None),
    db: Session = Depends(get_db),
):
    """
    Grava os eventos aprovados no banco de dados.

    Body (opcional): {"eventos_aprovados": [lista de índices ou todos se omitido]}
    """
    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    if imp.status != "PREVIEW":
        raise HTTPException(400, f"Importação no status '{imp.status}' — só é possível confirmar status PREVIEW")

    eventos = json.loads(imp.eventos_extraidos_json) if imp.eventos_extraidos_json else []

    # Filtra eventos aprovados (exclui duplicatas e eventos marcados para excluir)
    indices_aprovados = None
    if body and "indices_aprovados" in body:
        indices_aprovados = set(body["indices_aprovados"])

    proxima_linha = _proximo_linha_excel(db)
    gravados = 0
    ids_gravados = []

    for i, ev in enumerate(eventos):
        if indices_aprovados is not None and i not in indices_aprovados:
            continue
        if ev.get("duplicata") or ev.get("ignorar"):
            continue

        try:
            data_ev = date.fromisoformat(ev["data"]) if isinstance(ev["data"], str) else ev["data"]
            evento_db = Evento(
                linha_excel=proxima_linha + gravados,
                data=data_ev,
                ativo=ev["ativo"],
                tipo=ev["tipo"],
                qtd=ev.get("qtd"),
                preco=ev.get("preco"),
                valor=float(ev.get("valor") or 0),
                obs=ev.get("obs") or f"Importado #{importacao_id}",
            )
            db.add(evento_db)
            db.flush()
            assoc = ImportacaoEvento(importacao_id=imp.id, evento_id=evento_db.id)
            db.add(assoc)
            ids_gravados.append(evento_db.id)
            gravados += 1
        except Exception as e:
            log.warning(f"Evento {i} não gravado: {e} — {ev}")

    imp.status = "CONFIRMED"
    imp.total_eventos_gravados = gravados
    imp.data_confirmacao = datetime.utcnow()
    db.commit()

    # Dispara recálculo do engine
    try:
        from carteira_clean_web.backend.api import cache as engine_cache
        engine_cache.recalcular(no_api=True)
    except Exception as e:
        log.warning(f"Recálculo pós-importação falhou: {e}")

    return {
        "ok": True,
        "importacao_id": imp.id,
        "eventos_gravados": gravados,
        "ids_eventos": ids_gravados,
    }


@router.delete("/importacao/{importacao_id}")
def cancelar_importacao(importacao_id: int, db: Session = Depends(get_db)):
    """Cancela uma importação em PREVIEW (não remove arquivos arquivados)."""
    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    if imp.status == "CONFIRMED":
        raise HTTPException(400, "Não é possível cancelar uma importação já confirmada")
    imp.status = "CANCELLED"
    db.commit()
    return {"ok": True, "importacao_id": imp.id, "status": "CANCELLED"}


@router.get("/importacoes")
def listar_importacoes(
    limite: int = 50,
    db: Session = Depends(get_db),
):
    """Lista o histórico de importações (mais recentes primeiro)."""
    rows = (
        db.query(Importacao)
        .order_by(Importacao.data_upload.desc())
        .limit(limite)
        .all()
    )
    return [r.to_dict() for r in rows]


@router.get("/importacoes/{importacao_id}")
def detalhe_importacao(importacao_id: int, db: Session = Depends(get_db)):
    """Detalhes completos de uma importação."""
    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    d = imp.to_dict()
    if imp.eventos_extraidos_json:
        d["eventos"] = json.loads(imp.eventos_extraidos_json)
    return d
