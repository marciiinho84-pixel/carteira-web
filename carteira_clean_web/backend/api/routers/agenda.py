"""
Router: CRUD de agenda de eventos corporativos.
GET  /api/v1/agenda           → lista (filtro opcional: ativo, dias)
POST /api/v1/agenda           → criar evento
DELETE /api/v1/agenda/{id}   → remover evento
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import AgendaEvento

router = APIRouter(tags=["agenda"])

TIPOS_VALIDOS = {"EX_DIV", "BALANCO", "DIVIDENDO", "PROVENTOS", "OUTRO"}


class AgendaCreate(BaseModel):
    data: date
    ativo: str
    tipo: str
    descricao: Optional[str] = None


@router.get("/agenda")
def listar_agenda(
    ativo: Optional[str] = Query(None),
    dias: Optional[int] = Query(None, description="Próximos N dias a partir de hoje"),
    db: Session = Depends(get_db),
):
    q = db.query(AgendaEvento).order_by(AgendaEvento.data)
    if ativo:
        q = q.filter(AgendaEvento.ativo == ativo.upper())
    if dias is not None:
        limite = date.today() + timedelta(days=dias)
        q = q.filter(AgendaEvento.data <= limite, AgendaEvento.data >= date.today())
    return [e.to_dict() for e in q.all()]


@router.post("/agenda", status_code=201)
def criar_evento(ev: AgendaCreate, db: Session = Depends(get_db)):
    tipo = ev.tipo.upper()
    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(422, f"tipo inválido: '{tipo}'. Válidos: {sorted(TIPOS_VALIDOS)}")
    obj = AgendaEvento(
        data=ev.data,
        ativo=ev.ativo.upper(),
        tipo=tipo,
        descricao=ev.descricao,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj.to_dict()


@router.delete("/agenda/{evento_id}")
def deletar_evento(evento_id: int, db: Session = Depends(get_db)):
    obj = db.query(AgendaEvento).filter(AgendaEvento.id == evento_id).first()
    if not obj:
        raise HTTPException(404, "Evento não encontrado")
    db.delete(obj)
    db.commit()
    return {"ok": True}
