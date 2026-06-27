"""Router: CRUD de alertas/gatilhos monitorados pelo Maestro (Camada 3)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import Alerta

router = APIRouter(tags=["alertas"])

_TIPOS = ("RSI", "banda_IPS", "preco", "invalidacao")


class AlertaCreate(BaseModel):
    tipo: str
    condicao: str
    ativo: Optional[str] = None
    valor_gatilho: Optional[float] = None


class AlertaUpdate(BaseModel):
    habilitado: Optional[bool] = None
    condicao: Optional[str] = None
    valor_gatilho: Optional[float] = None


@router.get("/alertas")
def listar_alertas(
    apenas_ativos: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(Alerta).order_by(Alerta.criado_em.desc())
    if apenas_ativos:
        q = q.filter(Alerta.ativo_bool == 1)
    return [a.to_dict() for a in q.all()]


@router.post("/alertas", status_code=status.HTTP_201_CREATED)
def criar_alerta(body: AlertaCreate, db: Session = Depends(get_db)):
    if body.tipo not in _TIPOS:
        raise HTTPException(422, f"tipo inválido: {body.tipo}. Use {list(_TIPOS)}.")
    if not body.condicao or not body.condicao.strip():
        raise HTTPException(422, "condicao é obrigatória.")
    alvo = (body.ativo or "").strip()
    if body.tipo in ("RSI", "preco", "banda_IPS"):
        alvo = alvo.upper()
    a = Alerta(
        tipo=body.tipo,
        ativo=alvo or None,
        condicao=body.condicao.strip(),
        valor_gatilho=body.valor_gatilho,
        ativo_bool=1,
        disparado_em=None,
        criado_em=datetime.utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a.to_dict()


@router.patch("/alertas/{alerta_id}")
def atualizar_alerta(alerta_id: int, body: AlertaUpdate, db: Session = Depends(get_db)):
    a = db.get(Alerta, alerta_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    if body.habilitado is not None:
        a.ativo_bool = 1 if body.habilitado else 0
        if body.habilitado:
            a.disparado_em = None  # reativar limpa o disparo anterior
    if body.condicao is not None:
        a.condicao = body.condicao.strip()
    if body.valor_gatilho is not None:
        a.valor_gatilho = body.valor_gatilho
    db.commit()
    db.refresh(a)
    return a.to_dict()


@router.delete("/alertas/{alerta_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_alerta(alerta_id: int, db: Session = Depends(get_db)):
    a = db.get(Alerta, alerta_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    db.delete(a)
    db.commit()
