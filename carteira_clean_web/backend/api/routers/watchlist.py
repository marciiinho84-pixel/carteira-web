"""
GET    /api/v1/watchlist
POST   /api/v1/watchlist
PUT    /api/v1/watchlist/{id}
DELETE /api/v1/watchlist/{id}  (soft delete)
"""

import time
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from carteira_clean_web.backend.db.models import WatchlistItem
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.engine.utils import yf_symbol as _yf_symbol

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])

# ── Cache de cotações (15 min) ────────────────────────────────────
_cotacao_cache: dict[str, tuple[float, float]] = {}
_CACHE_TTL = 900  # segundos


def _get_cotacao(ticker: str) -> Optional[float]:
    now = time.time()
    cached = _cotacao_cache.get(ticker)
    if cached and (now - cached[1]) < _CACHE_TTL:
        return cached[0]
    try:
        import yfinance as yf
        sym = _yf_symbol(ticker)
        hist = yf.Ticker(sym).history(period="2d")
        if not hist.empty:
            preco = float(hist["Close"].iloc[-1])
            if preco > 0:
                _cotacao_cache[ticker] = (preco, now)
                return preco
    except Exception:
        pass
    return None


def _sinal(cotacao: Optional[float], preco_alvo: float) -> str:
    if cotacao is None:
        return "SEM_DADOS"
    if cotacao <= preco_alvo:
        return "NA_ZONA"
    if cotacao <= preco_alvo * 1.05:
        return "PROXIMO"
    return "ACIMA"


def _to_out(item: WatchlistItem) -> dict:
    cotacao = _get_cotacao(item.ticker)
    alvo = item.preco_alvo
    stop = item.stop_loss
    dist_alvo = (alvo - cotacao) / cotacao * 100 if cotacao else None
    dist_stop = (cotacao - stop) / stop * 100 if (cotacao and stop) else None
    return {
        "id": item.id,
        "ticker": item.ticker,
        "preco_alvo": alvo,
        "stop_loss": stop,
        "motivo": item.motivo,
        "data_adicao": str(item.data_adicao),
        "cotacao_atual": round(cotacao, 2) if cotacao else None,
        "distancia_alvo_pct": round(dist_alvo, 2) if dist_alvo is not None else None,
        "distancia_stop_pct": round(dist_stop, 2) if dist_stop is not None else None,
        "sinal": _sinal(cotacao, alvo),
    }


# ── Schemas ───────────────────────────────────────────────────────

class WatchlistCreate(BaseModel):
    ticker: str
    preco_alvo: float
    stop_loss: Optional[float] = None
    motivo: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def ticker_nao_vazio(cls, v):
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker não pode ser vazio")
        return v

    @field_validator("preco_alvo")
    @classmethod
    def alvo_positivo(cls, v):
        if v <= 0:
            raise ValueError("preco_alvo deve ser maior que zero")
        return v


class WatchlistUpdate(BaseModel):
    ticker: Optional[str] = None
    preco_alvo: Optional[float] = None
    stop_loss: Optional[float] = None
    motivo: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("")
def listar(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.ativo == 1).order_by(WatchlistItem.id).all()
    return [_to_out(i) for i in items]


@router.post("", status_code=201)
def criar(body: WatchlistCreate, db: Session = Depends(get_db)):
    if body.stop_loss is not None and body.stop_loss >= body.preco_alvo:
        raise HTTPException(400, "stop_loss deve ser menor que preco_alvo")
    item = WatchlistItem(
        ticker=body.ticker,
        preco_alvo=body.preco_alvo,
        stop_loss=body.stop_loss,
        motivo=body.motivo,
        data_adicao=date.today(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.put("/{item_id}")
def atualizar(item_id: int, body: WatchlistUpdate, db: Session = Depends(get_db)):
    item = db.get(WatchlistItem, item_id)
    if not item or item.ativo == 0:
        raise HTTPException(404, "Item não encontrado")
    if body.ticker is not None:
        item.ticker = body.ticker.strip().upper()
    if body.preco_alvo is not None:
        item.preco_alvo = body.preco_alvo
    if body.stop_loss is not None:
        item.stop_loss = body.stop_loss
    if body.motivo is not None:
        item.motivo = body.motivo
    if item.stop_loss and item.stop_loss >= item.preco_alvo:
        raise HTTPException(400, "stop_loss deve ser menor que preco_alvo")
    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.delete("/{item_id}")
def remover(item_id: int, db: Session = Depends(get_db)):
    item = db.get(WatchlistItem, item_id)
    if not item or item.ativo == 0:
        raise HTTPException(404, "Item não encontrado")
    item.ativo = 0
    db.commit()
    return {"ok": True}
