"""
GET  /api/v1/precos-manuais
POST /api/v1/precos-manuais
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from carteira_clean_web.backend.db.models import PrecoManual
from carteira_clean_web.backend.api.schemas import PrecoManualOut, PrecoManualCreate
from carteira_clean_web.backend.api.deps import get_db

router = APIRouter(prefix="/precos-manuais", tags=["Preços Manuais"])


@router.get("", response_model=list[PrecoManualOut])
def listar_precos(db: Session = Depends(get_db)):
    """Lista todos os preços manuais (HISTORICO_PRECOS)."""
    rows = db.query(PrecoManual).order_by(PrecoManual.ticker, PrecoManual.data).all()
    return [{"id": r.id, "data": r.data, "ticker": r.ticker, "valor": r.valor, "fonte": r.fonte}
            for r in rows]


@router.post("", response_model=PrecoManualOut, status_code=201)
def adicionar_preco(payload: PrecoManualCreate, db: Session = Depends(get_db)):
    """Adiciona ou atualiza um ponto de preço manual."""
    existente = (
        db.query(PrecoManual)
        .filter(PrecoManual.ticker == payload.ticker, PrecoManual.data == payload.data)
        .first()
    )
    if existente:
        existente.valor = payload.valor
        existente.fonte = payload.fonte
        db.commit()
        db.refresh(existente)
        return {"id": existente.id, "data": existente.data, "ticker": existente.ticker,
                "valor": existente.valor, "fonte": existente.fonte}
    preco = PrecoManual(**payload.model_dump())
    db.add(preco)
    db.commit()
    db.refresh(preco)
    return {"id": preco.id, "data": preco.data, "ticker": preco.ticker,
            "valor": preco.valor, "fonte": preco.fonte}
