"""Router: CRUD de regra de aportes mensais (Fatia 7)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import RegraAporte

router = APIRouter(tags=["regra_aportes"])

_TIPOS = ("PROGRAMADO", "OPORTUNISTICO", "MISTO")


class RegraCreate(BaseModel):
    valor_mensal_alvo: float
    tipo: str = "PROGRAMADO"
    criterio_oportunismo: Optional[str] = None


class RegraUpdate(BaseModel):
    valor_mensal_alvo: Optional[float] = None
    tipo: Optional[str] = None
    criterio_oportunismo: Optional[str] = None


@router.get("/regra-aportes")
def listar_regras(db: Session = Depends(get_db)):
    regras = db.query(RegraAporte).order_by(RegraAporte.id.desc()).all()
    return [r.to_dict() for r in regras]


@router.get("/regra-aportes/ativa")
def regra_ativa(db: Session = Depends(get_db)):
    r = db.query(RegraAporte).filter(RegraAporte.ativo == 1).first()
    return r.to_dict() if r else None


@router.post("/regra-aportes", status_code=status.HTTP_201_CREATED)
def criar_regra(body: RegraCreate, db: Session = Depends(get_db)):
    if body.tipo.upper() not in _TIPOS:
        raise HTTPException(422, f"tipo inválido: {body.tipo}")
    if body.valor_mensal_alvo <= 0:
        raise HTTPException(422, "valor_mensal_alvo deve ser positivo")
    # Desativa regra anterior
    db.query(RegraAporte).filter(RegraAporte.ativo == 1).update({"ativo": 0})
    r = RegraAporte(
        valor_mensal_alvo=body.valor_mensal_alvo,
        tipo=body.tipo.upper(),
        criterio_oportunismo=body.criterio_oportunismo,
        data_criacao=date.today(),
        ativo=1,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r.to_dict()


@router.patch("/regra-aportes/{regra_id}")
def atualizar_regra(regra_id: int, body: RegraUpdate, db: Session = Depends(get_db)):
    r = db.get(RegraAporte, regra_id)
    if not r:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    if body.valor_mensal_alvo is not None:
        r.valor_mensal_alvo = body.valor_mensal_alvo
    if body.tipo is not None:
        if body.tipo.upper() not in _TIPOS:
            raise HTTPException(422, f"tipo inválido: {body.tipo}")
        r.tipo = body.tipo.upper()
    if body.criterio_oportunismo is not None:
        r.criterio_oportunismo = body.criterio_oportunismo
    db.commit()
    db.refresh(r)
    return r.to_dict()
