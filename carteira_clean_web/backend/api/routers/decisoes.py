"""
Router: CRUD completo para decisões de investimento (diário).
"""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Decisao

router = APIRouter(tags=["decisoes"])


# ─── Schemas locais ───────────────────────────────────────────────

class DecisaoCreate(BaseModel):
    data_decisao: date
    evento_id: Optional[int] = None
    ativo: str
    acao: str
    tese: str
    expectativa_retorno_pct: Optional[float] = None
    horizonte: Optional[str] = None
    revisao_em: Optional[date] = None


class DecisaoUpdate(BaseModel):
    resultado_revisao: Optional[str] = None
    notas: Optional[str] = None
    revisao_em: Optional[date] = None


# ─── Endpoints ───────────────────────────────────────────────────

@router.get("/decisoes")
def listar_decisoes(db: Session = Depends(get_db)):
    decisoes = db.query(Decisao).order_by(Decisao.data_decisao.desc()).all()
    return [d.to_dict() for d in decisoes]


@router.get("/decisoes/pendentes")
def decisoes_pendentes(db: Session = Depends(get_db)):
    hoje = date.today()
    pendentes = (
        db.query(Decisao)
        .filter(Decisao.revisao_em <= hoje, Decisao.resultado_revisao == None)  # noqa: E711
        .order_by(Decisao.revisao_em)
        .all()
    )
    return [d.to_dict() for d in pendentes]


@router.get("/decisoes/{decisao_id}")
def obter_decisao(decisao_id: int, db: Session = Depends(get_db)):
    d = db.get(Decisao, decisao_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    return d.to_dict()


@router.post("/decisoes", status_code=status.HTTP_201_CREATED)
def criar_decisao(body: DecisaoCreate, db: Session = Depends(get_db)):
    if body.acao not in ("COMPRA", "VENDA", "MANTER", "OBSERVAR"):
        raise HTTPException(status_code=422, detail=f"acao inválida: {body.acao}")
    if body.horizonte and body.horizonte not in ("curto", "medio", "longo"):
        raise HTTPException(status_code=422, detail=f"horizonte inválido: {body.horizonte}")
    d = Decisao(
        data_decisao=body.data_decisao,
        evento_id=body.evento_id,
        ativo=body.ativo,
        acao=body.acao,
        tese=body.tese,
        expectativa_retorno_pct=body.expectativa_retorno_pct,
        horizonte=body.horizonte,
        revisao_em=body.revisao_em,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d.to_dict()


@router.patch("/decisoes/{decisao_id}")
def revisar_decisao(decisao_id: int, body: DecisaoUpdate, db: Session = Depends(get_db)):
    d = db.get(Decisao, decisao_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    if body.resultado_revisao is not None:
        d.resultado_revisao = body.resultado_revisao
    if body.notas is not None:
        d.notas = body.notas
    if body.revisao_em is not None:
        d.revisao_em = body.revisao_em
    db.commit()
    db.refresh(d)
    return d.to_dict()


@router.delete("/decisoes/{decisao_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_decisao(decisao_id: int, db: Session = Depends(get_db)):
    d = db.get(Decisao, decisao_id)
    if not d:
        raise HTTPException(status_code=404, detail="Decisão não encontrada")
    db.delete(d)
    db.commit()
