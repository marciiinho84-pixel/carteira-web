"""
GET  /api/v1/ativos
POST /api/v1/ativos
PATCH /api/v1/ativos/{ticker}
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from carteira_clean_web.backend.db.models import Ativo
from carteira_clean_web.backend.api.schemas import AtivoOut, AtivoCreate, AtivoUpdate
from carteira_clean_web.backend.api.deps import get_db

router = APIRouter(prefix="/ativos", tags=["Ativos"])


@router.get("", response_model=list[AtivoOut])
def listar_ativos(db: Session = Depends(get_db)):
    """Lista todos os ativos do cadastro mestre."""
    return [a.to_dict() for a in db.query(Ativo).order_by(Ativo.ticker).all()]


@router.post("", response_model=AtivoOut, status_code=201)
def criar_ativo(payload: AtivoCreate, db: Session = Depends(get_db)):
    """Cadastra um novo ativo."""
    if db.query(Ativo).filter(Ativo.ticker == payload.ticker).first():
        raise HTTPException(400, f"Ativo '{payload.ticker}' já existe no cadastro")
    ativo = Ativo(**payload.model_dump())
    db.add(ativo)
    db.commit()
    db.refresh(ativo)
    return ativo.to_dict()


@router.patch("/{ticker}", response_model=AtivoOut)
def editar_ativo(ticker: str, payload: AtivoUpdate, db: Session = Depends(get_db)):
    """Edita campos de um ativo existente."""
    ativo = db.query(Ativo).filter(Ativo.ticker == ticker).first()
    if not ativo:
        raise HTTPException(404, f"Ativo '{ticker}' não encontrado")
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(ativo, campo, valor)
    db.commit()
    db.refresh(ativo)
    return ativo.to_dict()
