"""Router: CRUD do diário de decisões estruturado (Fatia 5)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import DiarioDecisao

router = APIRouter(tags=["diario_decisoes"])

_ACOES = ("COMPRA", "VENDA", "AUMENTO", "REDUCAO", "MANTER", "WATCHLIST")


class DiarioCreate(BaseModel):
    data_decisao: date
    ticker: str
    acao: str
    racional: str
    cenario_esperado: Optional[str] = None
    conviccao: int = 3
    preco_entrada: Optional[float] = None
    tese_id: Optional[int] = None


class DiarioUpdate(BaseModel):
    racional: Optional[str] = None
    cenario_esperado: Optional[str] = None
    conviccao: Optional[int] = None
    preco_entrada: Optional[float] = None


@router.get("/diario-decisoes")
def listar_diario(
    ticker: Optional[str] = None,
    acao: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(DiarioDecisao).order_by(DiarioDecisao.data_decisao.desc())
    if ticker:
        q = q.filter(DiarioDecisao.ticker == ticker.upper())
    if acao:
        q = q.filter(DiarioDecisao.acao == acao.upper())
    return [d.to_dict() for d in q.all()]


@router.get("/diario-decisoes/{entrada_id}")
def obter_entrada(entrada_id: int, db: Session = Depends(get_db)):
    d = db.get(DiarioDecisao, entrada_id)
    if not d:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    return d.to_dict()


@router.post("/diario-decisoes", status_code=status.HTTP_201_CREATED)
def criar_entrada(body: DiarioCreate, db: Session = Depends(get_db)):
    if body.acao.upper() not in _ACOES:
        raise HTTPException(422, f"acao inválida: {body.acao}")
    if not (1 <= body.conviccao <= 5):
        raise HTTPException(422, "conviccao deve ser entre 1 e 5")
    d = DiarioDecisao(
        data_decisao=body.data_decisao,
        ticker=body.ticker.upper(),
        acao=body.acao.upper(),
        racional=body.racional,
        cenario_esperado=body.cenario_esperado,
        conviccao=body.conviccao,
        preco_entrada=body.preco_entrada,
        tese_id=body.tese_id,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d.to_dict()


@router.patch("/diario-decisoes/{entrada_id}")
def atualizar_entrada(entrada_id: int, body: DiarioUpdate, db: Session = Depends(get_db)):
    d = db.get(DiarioDecisao, entrada_id)
    if not d:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    if body.racional is not None:
        d.racional = body.racional
    if body.cenario_esperado is not None:
        d.cenario_esperado = body.cenario_esperado
    if body.conviccao is not None:
        if not (1 <= body.conviccao <= 5):
            raise HTTPException(422, "conviccao deve ser entre 1 e 5")
        d.conviccao = body.conviccao
    if body.preco_entrada is not None:
        d.preco_entrada = body.preco_entrada
    db.commit()
    db.refresh(d)
    return d.to_dict()


@router.delete("/diario-decisoes/{entrada_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_entrada(entrada_id: int, db: Session = Depends(get_db)):
    d = db.get(DiarioDecisao, entrada_id)
    if not d:
        raise HTTPException(status_code=404, detail="Entrada não encontrada")
    db.delete(d)
    db.commit()
