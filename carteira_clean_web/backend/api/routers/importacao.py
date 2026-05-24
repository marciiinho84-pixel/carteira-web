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
from carteira_clean_web.backend.db.models import Evento, Importacao, ImportacaoEvento, PrecoManual
from sqlalchemy import func

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
    max_linha = db.query(func.max(Evento.linha_excel)).scalar() or 0
    return max_linha + 1


def _processar_cotas_funcef(
    db: Session,
    historico_cotas: list[dict],
    force_update: bool = False,
) -> dict:
    """
    Salva historico_cotas_mensais em precos_manuais (ticker=FUNCEF).
    - Novo valor: INSERT
    - Valor existente diferente >0.1%: registra conflito (ou sobrescreve se force_update)
    - Valor igual (≤0.1%): skip silencioso
    Returns: {inseridas: N, conflitos: [{data, valor_existente, valor_novo, diferenca_pct}]}
    """
    from carteira_clean_web.backend.engine.importacao.extrator import _normalizar_data
    inseridas = 0
    conflitos = []

    for entrada in historico_cotas:
        try:
            data_raw = entrada.get("data") or ""
            data_str = _normalizar_data(str(data_raw))
            if not data_str or data_str == "None":
                continue
            data_cota = date.fromisoformat(data_str)
            valor_cota = float(entrada.get("valor_cota") or 0)
            if valor_cota <= 0:
                continue

            existente = db.query(PrecoManual).filter(
                PrecoManual.ticker == "FUNCEF",
                PrecoManual.data == data_cota,
            ).first()

            if existente is None:
                db.add(PrecoManual(
                    data=data_cota,
                    ticker="FUNCEF",
                    valor=valor_cota,
                    fonte="importacao-funcef",
                ))
                inseridas += 1
            else:
                diferenca_pct = abs(existente.valor - valor_cota) / existente.valor * 100
                if diferenca_pct > 0.1:
                    if force_update:
                        existente.valor = valor_cota
                        existente.fonte = "importacao-funcef-override"
                        inseridas += 1
                    else:
                        conflitos.append({
                            "data": str(data_cota),
                            "valor_existente": round(existente.valor, 10),
                            "valor_novo": round(valor_cota, 10),
                            "diferenca_pct": round(diferenca_pct, 3),
                        })
                # diferença ≤0.1%: skip silencioso
        except Exception as e:
            log.warning(f"FUNCEF: cota não processada {entrada}: {e}")

    return {"inseridas": inseridas, "conflitos": conflitos}


def _reconciliar_funcef(db: Session, saldo_extrato: dict | None) -> dict:
    """
    Compara posição FUNCEF calculada pelo banco vs saldo reportado no extrato.
    Usa: SALDO_INICIAL.qtd + Σ CONTRIBUICAO.qtd e última cota de precos_manuais.
    Returns: {divergencia_cotas, divergencia_valor_pct, alerta_criado}
    """
    resultado = {
        "divergencia_cotas": None,
        "divergencia_valor_pct": None,
        "alerta_criado": False,
        "qtd_calculada": None,
        "patrimonio_calculado": None,
    }

    if not saldo_extrato:
        return resultado

    try:
        qtd_saldo_inicial = db.query(func.sum(Evento.qtd)).filter(
            Evento.ativo == "FUNCEF",
            Evento.tipo == "SALDO_INICIAL",
        ).scalar() or 0.0

        qtd_contribuicoes = db.query(func.sum(Evento.qtd)).filter(
            Evento.ativo == "FUNCEF",
            Evento.tipo == "CONTRIBUICAO",
        ).scalar() or 0.0

        qtd_calculada = float(qtd_saldo_inicial) + float(qtd_contribuicoes)

        ultima_cota = (
            db.query(PrecoManual)
            .filter(PrecoManual.ticker == "FUNCEF")
            .order_by(PrecoManual.data.desc())
            .first()
        )
        patrimonio_calculado = qtd_calculada * ultima_cota.valor if ultima_cota else 0.0

        qtd_extrato = float(saldo_extrato.get("quantidade_cotas") or 0)
        valor_extrato = float(saldo_extrato.get("valor_real") or 0)

        div_cotas = abs(qtd_calculada - qtd_extrato)
        div_cotas_pct = div_cotas / qtd_extrato * 100 if qtd_extrato else 0
        div_valor_pct = (
            abs(patrimonio_calculado - valor_extrato) / valor_extrato * 100
            if valor_extrato else 0
        )

        resultado.update({
            "qtd_calculada": round(qtd_calculada, 4),
            "patrimonio_calculado": round(patrimonio_calculado, 2),
            "divergencia_cotas": round(div_cotas, 4),
            "divergencia_cotas_pct": round(div_cotas_pct, 4),
            "divergencia_valor_pct": round(div_valor_pct, 4),
        })

        if div_cotas_pct > 0.5 or div_valor_pct > 0.5:
            diff_r = abs(patrimonio_calculado - valor_extrato)
            log.warning(
                f"FUNCEF: divergência de reconciliação — "
                f"cotas calc={qtd_calculada:.2f} vs extrato={qtd_extrato:.2f} | "
                f"patrimônio calc=R${patrimonio_calculado:,.2f} vs extrato=R${valor_extrato:,.2f} "
                f"(diff={div_valor_pct:.2f}%)"
            )
            resultado["alerta_criado"] = True
            resultado["alerta_mensagem"] = (
                f"FUNCEF: posição calculada diverge do extrato em "
                f"R$ {diff_r:,.2f} ({div_valor_pct:.1f}%). Verificar HISTORICO_PRECOS."
            )

    except Exception as e:
        log.warning(f"Reconciliação FUNCEF falhou: {e}")
        resultado["erro"] = str(e)

    return resultado


def _gravar_eventos(
    db: Session,
    imp_id: int,
    eventos: list[dict],
    indices_aprovados: set | None,
    proxima_linha: int,
    force_update_cotas: bool = False,
) -> dict:
    """
    Grava eventos aprovados no banco.
    Para eventos FUNCEF: processa cotas + reconcilia automaticamente.
    Returns: {gravados, ids_gravados, cotas_inseridas, cotas_conflito, reconciliacao}
    """
    gravados = 0
    ids_gravados = []
    cotas_inseridas = 0
    cotas_conflito = []
    reconciliacao = {}

    for i, ev in enumerate(eventos):
        if indices_aprovados is not None and i not in indices_aprovados:
            continue
        if ev.get("duplicata") or ev.get("ignorar"):
            continue

        # Processar cotas FUNCEF antes de gravar o evento
        if ev.get("ativo") == "FUNCEF" and ev.get("tipo") == "CONTRIBUICAO":
            historico = ev.get("_funcef_historico_cotas") or []
            if historico:
                res_cotas = _processar_cotas_funcef(db, historico, force_update=force_update_cotas)
                cotas_inseridas += res_cotas["inseridas"]
                cotas_conflito.extend(res_cotas["conflitos"])
                if res_cotas["inseridas"] > 0:
                    log.info(f"FUNCEF: {res_cotas['inseridas']} cota(s) inserida(s) em precos_manuais")
                if res_cotas["conflitos"]:
                    log.warning(f"FUNCEF: {len(res_cotas['conflitos'])} conflito(s) de cota detectado(s)")

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
                obs=ev.get("obs") or f"Importado #{imp_id}",
            )
            db.add(evento_db)
            db.flush()
            assoc = ImportacaoEvento(importacao_id=imp_id, evento_id=evento_db.id)
            db.add(assoc)
            ids_gravados.append(evento_db.id)
            gravados += 1
        except Exception as e:
            log.warning(f"Evento {i} não gravado: {e} — {ev}")

    # Reconciliação FUNCEF (executada após commit para ler posição atualizada)
    saldo_funcef = None
    for ev in eventos:
        if ev.get("ativo") == "FUNCEF" and ev.get("_funcef_saldo"):
            saldo_funcef = ev["_funcef_saldo"]
            break
    if saldo_funcef:
        reconciliacao = _reconciliar_funcef(db, saldo_funcef)

    return {
        "gravados": gravados,
        "ids_gravados": ids_gravados,
        "cotas_inseridas": cotas_inseridas,
        "cotas_conflito": cotas_conflito,
        "reconciliacao": reconciliacao,
    }


@router.post("/importacao/upload")
async def upload_extrato(
    arquivo: UploadFile = File(...),
    tipo_documento: str = Form("auto"),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    """
    Recebe arquivo, chama Claude e retorna preview.
    - tipo_documento="auto" (default): Claude identifica o tipo automaticamente
    - tipo_documento=<tipo>: usa o tipo informado diretamente, sem validação prévia
    - dry_run=True: não cria registro no DB nem grava eventos — retorna apenas o JSON extraído
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
    formato_detectado = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else "desconhecido"

    # dry_run: não verifica duplicata de arquivo, não cria registro
    if not dry_run:
        importacao_anterior = db.query(Importacao).filter(
            Importacao.arquivo_hash == arquivo_hash,
            Importacao.status == "CONFIRMED",
        ).first()
        if importacao_anterior:
            raise HTTPException(409, f"Este arquivo já foi importado (importação #{importacao_anterior.id})")

    alertas_pre = []
    if formato_detectado == "pdf":
        from carteira_clean_web.backend.engine.importacao.processadores.pdf import contar_paginas_pdf
        n_pags = contar_paginas_pdf(conteudo)
        if n_pags > 30:
            alertas_pre.append(
                f"PDF extenso ({n_pags} páginas) — apenas as primeiras 100 serão processadas. "
                f"Para melhor resultado, divida em períodos menores."
            )

    # Arquiva o arquivo (mesmo em dry_run, para permitir reprocessamento)
    agora = datetime.utcnow()
    dest_dir = _arquivo_dir(agora.year, agora.month)
    dest_path = dest_dir / f"{arquivo_hash[:8]}-{nome_arquivo}"
    try:
        dest_path.write_bytes(conteudo)
    except Exception as e:
        log.warning(f"Falha ao arquivar {nome_arquivo}: {e}")
        dest_path = None

    # Chama Claude
    log.info(f"{'[DRY_RUN] ' if dry_run else ''}Chamando Claude para {nome_arquivo}...")
    try:
        eventos, custo, meta = extrair_eventos(conteudo, nome_arquivo, tipo_documento)
    except Exception as e:
        log.error(f"Erro ao chamar Claude: {e}", exc_info=True)
        if dry_run:
            raise HTTPException(500, f"Erro ao processar arquivo: {e}")
        # Em modo normal cria registro de erro
        imp = Importacao(
            arquivo_nome=nome_arquivo,
            arquivo_hash=arquivo_hash,
            formato=formato_detectado,
            tipo_documento=tipo_documento,
            status="ERROR",
            data_upload=agora,
            erro_mensagem=str(e)[:1000],
            arquivo_path=str(dest_path) if dest_path else None,
        )
        db.add(imp)
        db.commit()
        raise HTTPException(500, f"Erro ao processar arquivo: {e}")

    # Detecta duplicatas (mesmo em dry_run)
    hashes_existentes = _hashes_existentes(db)
    for ev in eventos:
        ev["duplicata"] = ev["hash"] in hashes_existentes

    n_dup = sum(1 for ev in eventos if ev["duplicata"])
    raw_json = json.dumps({"meta": meta, "eventos": eventos}, default=str, ensure_ascii=False, indent=2)

    if dry_run:
        return {
            "importacao_id": None,
            "status": "DRY_RUN",
            "dry_run": True,
            "total_eventos": len(eventos),
            "duplicatas": n_dup,
            "custo_api_usd": round(custo, 6),
            "tipo_identificado": meta.get("tipo_identificado"),
            "confianca": meta.get("confianca"),
            "justificativa": meta.get("justificativa"),
            "eventos": eventos,
            "raw_claude_response": meta.get("raw_claude_response", ""),  # resposta bruta da IA
            "raw_json_ia": raw_json,
            "alertas": alertas_pre,
            "arquivo_path": str(dest_path) if dest_path else None,
            "arquivo_hash": arquivo_hash,
            "nome_arquivo": nome_arquivo,
            "tipo_documento": tipo_documento,
        }

    # Modo normal: cria registro no DB
    imp = Importacao(
        arquivo_nome=nome_arquivo,
        arquivo_hash=arquivo_hash,
        formato=formato_detectado,
        tipo_documento=tipo_documento,
        status="PROCESSING",
        data_upload=agora,
        modo_teste=False,
        raw_json_ia=raw_json,
    )
    db.add(imp)
    db.commit()
    db.refresh(imp)

    imp.status = "PREVIEW"
    imp.total_eventos_extraidos = len(eventos)
    imp.total_eventos_duplicados = n_dup
    imp.custo_api_usd = custo
    imp.eventos_extraidos_json = json.dumps(eventos, default=str)
    imp.arquivo_path = str(dest_path) if dest_path else None
    imp.tipo_identificado_ia = meta.get("tipo_identificado")
    imp.confianca_ia = meta.get("confianca")
    imp.justificativa_ia = meta.get("justificativa")
    db.commit()

    return {
        "importacao_id": imp.id,
        "status": "PREVIEW",
        "dry_run": False,
        "total_eventos": len(eventos),
        "duplicatas": n_dup,
        "custo_api_usd": round(custo, 6),
        "tipo_identificado": meta.get("tipo_identificado"),
        "confianca": meta.get("confianca"),
        "justificativa": meta.get("justificativa"),
        "eventos": eventos,
        "alertas": alertas_pre,
    }


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
    Body: {indices_aprovados: [...], force_update_cotas: bool}
    Para eventos FUNCEF: salva historico_cotas_mensais em precos_manuais e reconcilia.
    """
    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    if imp.status != "PREVIEW":
        raise HTTPException(400, f"Importação no status '{imp.status}' — só é possível confirmar status PREVIEW")

    eventos = json.loads(imp.eventos_extraidos_json) if imp.eventos_extraidos_json else []

    indices_aprovados = None
    force_update_cotas = False
    if body:
        if "indices_aprovados" in body:
            indices_aprovados = set(body["indices_aprovados"])
        force_update_cotas = bool(body.get("force_update_cotas", False))

    proxima_linha = _proximo_linha_excel(db)
    res = _gravar_eventos(db, imp.id, eventos, indices_aprovados, proxima_linha, force_update_cotas)

    imp.status = "CONFIRMED"
    imp.total_eventos_gravados = res["gravados"]
    imp.data_confirmacao = datetime.utcnow()
    db.commit()

    try:
        from carteira_clean_web.backend.api import cache as engine_cache
        engine_cache.recalcular(no_api=True)
    except Exception as e:
        log.warning(f"Recálculo pós-importação falhou: {e}")

    rec = res["reconciliacao"]
    return {
        "ok": True,
        "importacao_id": imp.id,
        "eventos_gravados": res["gravados"],
        "ids_eventos": res["ids_gravados"],
        "cotas_inseridas": res["cotas_inseridas"],
        "cotas_conflito": res["cotas_conflito"],
        "reconciliacao": rec,
    }


@router.post("/importacao/confirmar-direto")
def confirmar_direto(
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    Confirma eventos de uma sessão dry_run.
    Body: {eventos, indices_aprovados, arquivo_path, arquivo_hash, nome_arquivo,
           tipo_documento, custo_api_usd, meta, force_update_cotas}
    Cria registro de importação (modo_teste=True) e grava eventos aprovados.
    Para eventos FUNCEF: salva cotas em precos_manuais e reconcilia.
    """
    eventos = body.get("eventos", [])
    indices_aprovados = set(body.get("indices_aprovados", list(range(len(eventos)))))
    arquivo_path = body.get("arquivo_path")
    arquivo_hash = body.get("arquivo_hash", "")
    nome_arquivo = body.get("nome_arquivo", "documento")
    tipo_documento = body.get("tipo_documento", "auto")
    custo = float(body.get("custo_api_usd", 0))
    meta = body.get("meta", {})
    force_update_cotas = bool(body.get("force_update_cotas", False))

    agora = datetime.utcnow()
    imp = Importacao(
        arquivo_nome=nome_arquivo,
        arquivo_hash=arquivo_hash,
        formato=nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else "desconhecido",
        tipo_documento=tipo_documento,
        status="PROCESSING",
        data_upload=agora,
        modo_teste=True,
        arquivo_path=arquivo_path,
        tipo_identificado_ia=meta.get("tipo_identificado"),
        confianca_ia=meta.get("confianca"),
        justificativa_ia=meta.get("justificativa"),
        custo_api_usd=custo,
        total_eventos_extraidos=len(eventos),
        total_eventos_duplicados=sum(1 for ev in eventos if ev.get("duplicata")),
        eventos_extraidos_json=json.dumps(eventos, default=str),
    )
    db.add(imp)
    db.commit()
    db.refresh(imp)

    proxima_linha = _proximo_linha_excel(db)
    res = _gravar_eventos(db, imp.id, eventos, indices_aprovados, proxima_linha, force_update_cotas)

    imp.status = "CONFIRMED"
    imp.total_eventos_gravados = res["gravados"]
    imp.data_confirmacao = agora
    db.commit()

    try:
        from carteira_clean_web.backend.api import cache as engine_cache
        engine_cache.recalcular(no_api=True)
    except Exception as e:
        log.warning(f"Recálculo pós-importação direta falhou: {e}")

    rec = res["reconciliacao"]
    return {
        "ok": True,
        "importacao_id": imp.id,
        "eventos_gravados": res["gravados"],
        "ids_eventos": res["ids_gravados"],
        "cotas_inseridas": res["cotas_inseridas"],
        "cotas_conflito": res["cotas_conflito"],
        "reconciliacao": rec,
    }


@router.post("/importacao/{importacao_id}/reprocessar")
def reprocessar_importacao(
    importacao_id: int,
    body: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    """
    Reprocessa uma importação PREVIEW com um tipo diferente.
    Usa o arquivo já arquivado — não precisa fazer novo upload.
    Body: {"tipo_documento": "funcef"}
    """
    from carteira_clean_web.backend.engine.importacao.extrator import extrair_eventos
    from carteira_clean_web.backend.engine.importacao.detector import TIPOS_DOCUMENTO

    imp = db.query(Importacao).filter(Importacao.id == importacao_id).first()
    if not imp:
        raise HTTPException(404, "Importação não encontrada")
    if imp.status not in ("PREVIEW", "ERROR"):
        raise HTTPException(400, f"Só é possível reprocessar status PREVIEW ou ERROR (atual: {imp.status})")
    if not imp.arquivo_path or not Path(imp.arquivo_path).exists():
        raise HTTPException(400, "Arquivo original não encontrado no arquivo — faça novo upload")

    novo_tipo = body.get("tipo_documento", imp.tipo_documento)
    if novo_tipo not in TIPOS_DOCUMENTO:
        raise HTTPException(400, f"tipo_documento inválido: {novo_tipo}")

    conteudo = Path(imp.arquivo_path).read_bytes()
    imp.status = "PROCESSING"
    imp.tipo_documento = novo_tipo
    db.commit()

    try:
        eventos, custo, meta = extrair_eventos(conteudo, imp.arquivo_nome, novo_tipo)
        hashes_existentes = _hashes_existentes(db)
        for ev in eventos:
            ev["duplicata"] = ev["hash"] in hashes_existentes

        n_dup = sum(1 for ev in eventos if ev["duplicata"])
        imp.status = "PREVIEW"
        imp.total_eventos_extraidos = len(eventos)
        imp.total_eventos_duplicados = n_dup
        imp.custo_api_usd = (imp.custo_api_usd or 0) + custo
        imp.eventos_extraidos_json = json.dumps(eventos, default=str)
        imp.tipo_identificado_ia = meta.get("tipo_identificado")
        imp.confianca_ia = meta.get("confianca")
        imp.justificativa_ia = meta.get("justificativa")
        db.commit()

        return {
            "importacao_id": imp.id,
            "status": "PREVIEW",
            "tipo_documento": novo_tipo,
            "tipo_identificado": meta.get("tipo_identificado"),
            "confianca": meta.get("confianca"),
            "justificativa": meta.get("justificativa"),
            "total_eventos": len(eventos),
            "duplicatas": n_dup,
            "custo_api_usd": round(custo, 6),
            "eventos": eventos,
        }
    except Exception as e:
        imp.status = "ERROR"
        imp.erro_mensagem = str(e)[:1000]
        db.commit()
        raise HTTPException(500, f"Erro ao reprocessar: {str(e)}")


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
