"""Router: CRUD de teses de investimento (Fatia 4)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Tese

router = APIRouter(tags=["teses"])

_NIVEIS = ("VERDE", "AMARELO", "VERMELHO")
_STATUS = ("ATIVA", "INVALIDADA", "ENCERRADA")
_BLOCOS = ("SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA", "FORA_IPS")


class TeseCreate(BaseModel):
    ticker: str
    bloco_ips: Optional[str] = None
    racional: str
    cenario_esperado: Optional[str] = None
    criterio_invalidacao: Optional[str] = None
    nivel_invalidacao: str = "VERDE"


class TeseUpdate(BaseModel):
    nivel_invalidacao: Optional[str] = None
    criterio_invalidacao: Optional[str] = None
    cenario_esperado: Optional[str] = None
    status: Optional[str] = None
    observacao_encerramento: Optional[str] = None


@router.get("/teses")
def listar_teses(
    ticker: Optional[str] = None,
    status_f: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Tese).order_by(Tese.data_criacao.desc())
    if ticker:
        q = q.filter(Tese.ticker == ticker.upper())
    if status_f:
        q = q.filter(Tese.status == status_f.upper())
    return [t.to_dict() for t in q.all()]


@router.get("/teses/{tese_id}")
def obter_tese(tese_id: int, db: Session = Depends(get_db)):
    t = db.get(Tese, tese_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tese não encontrada")
    return t.to_dict()


@router.post("/teses", status_code=status.HTTP_201_CREATED)
def criar_tese(body: TeseCreate, db: Session = Depends(get_db)):
    if body.nivel_invalidacao not in _NIVEIS:
        raise HTTPException(422, f"nivel_invalidacao inválido: {body.nivel_invalidacao}")
    t = Tese(
        ticker=body.ticker.upper(),
        bloco_ips=body.bloco_ips,
        racional=body.racional,
        cenario_esperado=body.cenario_esperado,
        criterio_invalidacao=body.criterio_invalidacao,
        nivel_invalidacao=body.nivel_invalidacao,
        data_criacao=date.today(),
        status="ATIVA",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t.to_dict()


@router.patch("/teses/{tese_id}")
def atualizar_tese(tese_id: int, body: TeseUpdate, db: Session = Depends(get_db)):
    t = db.get(Tese, tese_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tese não encontrada")
    if body.nivel_invalidacao is not None:
        if body.nivel_invalidacao not in _NIVEIS:
            raise HTTPException(422, f"nivel_invalidacao inválido: {body.nivel_invalidacao}")
        t.nivel_invalidacao = body.nivel_invalidacao
    if body.criterio_invalidacao is not None:
        t.criterio_invalidacao = body.criterio_invalidacao
    if body.cenario_esperado is not None:
        t.cenario_esperado = body.cenario_esperado
    if body.status is not None:
        if body.status not in _STATUS:
            raise HTTPException(422, f"status inválido: {body.status}")
        t.status = body.status
        if body.status in ("INVALIDADA", "ENCERRADA"):
            t.data_atualizacao = date.today()
    if body.observacao_encerramento is not None:
        t.observacao_encerramento = body.observacao_encerramento
    db.commit()
    db.refresh(t)
    return t.to_dict()


@router.delete("/teses/{tese_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_tese(tese_id: int, db: Session = Depends(get_db)):
    t = db.get(Tese, tese_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tese não encontrada")
    db.delete(t)
    db.commit()
