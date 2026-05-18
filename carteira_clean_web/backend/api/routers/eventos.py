"""
GET    /api/v1/eventos?from=...&to=...
POST   /api/v1/eventos
PATCH  /api/v1/eventos/{id}
DELETE /api/v1/eventos/{id}

Após qualquer mutação, recalcula o engine automaticamente (síncrono no MVP).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from carteira_clean_web.backend.db.models import Evento, Ativo
from carteira_clean_web.backend.api.schemas import EventoOut, EventoCreate, EventoUpdate
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.api import cache as engine_cache

router = APIRouter(prefix="/eventos", tags=["Eventos"])


def _to_out(e: Evento) -> dict:
    return {
        "id": e.id,
        "linha": e.linha_excel,
        "data": e.data,
        "ativo": e.ativo,
        "tipo": e.tipo,
        "qtd": e.qtd,
        "preco": e.preco,
        "valor": e.valor or 0,
        "obs": e.obs or "",
    }


@router.get("", response_model=list[EventoOut])
def listar_eventos(
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
    ativo: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista eventos com filtros opcionais de data, ativo e tipo."""
    q = db.query(Evento)
    if from_:
        q = q.filter(Evento.data >= from_)
    if to:
        q = q.filter(Evento.data <= to)
    if ativo:
        q = q.filter(Evento.ativo == ativo.upper())
    if tipo:
        q = q.filter(Evento.tipo == tipo.upper())
    return [_to_out(e) for e in q.order_by(Evento.data, Evento.ativo, Evento.linha_excel).all()]


@router.post("", response_model=EventoOut, status_code=201)
def criar_evento(payload: EventoCreate, db: Session = Depends(get_db)):
    """Adiciona um evento ao event log e recalcula o engine."""
    ativo = db.query(Ativo).filter(Ativo.ticker == payload.ativo).first()
    if not ativo:
        raise HTTPException(
            400,
            f"Ativo '{payload.ativo}' não encontrado em CAD_ATIVOS. "
            "Cadastre o ativo antes de adicionar eventos."
        )
    max_linha = db.query(func.max(Evento.linha_excel)).scalar() or 4
    evento = Evento(
        linha_excel=max_linha + 1,
        data=payload.data,
        ativo=payload.ativo,
        tipo=payload.tipo,
        qtd=payload.qtd,
        preco=payload.preco,
        valor=payload.valor,
        obs=payload.obs or "",
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    # Recalcular engine após mutação
    try:
        engine_cache.recalcular(no_api=True)
    except Exception:
        pass  # não falhar o POST por causa do recálculo
    return _to_out(evento)


@router.patch("/{evento_id}", response_model=EventoOut)
def editar_evento(evento_id: int, payload: EventoUpdate, db: Session = Depends(get_db)):
    """Edita um evento existente e recalcula o engine."""
    evento = db.query(Evento).filter(Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(404, f"Evento id={evento_id} não encontrado")
    for campo, valor in payload.model_dump(exclude_none=True).items():
        db_campo = "linha_excel" if campo == "linha" else campo
        setattr(evento, db_campo, valor)
    db.commit()
    db.refresh(evento)
    try:
        engine_cache.recalcular(no_api=True)
    except Exception:
        pass
    return _to_out(evento)


@router.delete("/{evento_id}", status_code=204)
def deletar_evento(evento_id: int, db: Session = Depends(get_db)):
    """Remove um evento e recalcula o engine."""
    evento = db.query(Evento).filter(Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(404, f"Evento id={evento_id} não encontrado")
    db.delete(evento)
    db.commit()
    try:
        engine_cache.recalcular(no_api=True)
    except Exception:
        pass
