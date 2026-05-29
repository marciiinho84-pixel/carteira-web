"""
GET /api/v1/sinais?tickers=ITSA4,WEGE3&apenas_ativos=true
GET /api/v1/sinais/carteira_rv?apenas_ativos=true
"""

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.db.models import WatchlistItem
from carteira_clean_web.backend.engine.sinais_tecnicos import calcular_sinais_lote

router = APIRouter(prefix="/sinais", tags=["Sinais"])


def _filtrar(sinais: list, apenas_ativos: bool) -> list:
    if apenas_ativos:
        return [s for s in sinais if s.get("tem_sinal_ativo")]
    return sinais


@router.get("")
def sinais(tickers: str = Query(..., description="Tickers separados por vírgula"),
           apenas_ativos: bool = True):
    lista = [t for t in tickers.split(",") if t.strip()]
    if not lista:
        raise HTTPException(400, "Informe ao menos um ticker")
    return _filtrar(calcular_sinais_lote(lista), apenas_ativos)


@router.get("/carteira_rv")
def sinais_carteira_rv(apenas_ativos: bool = True, db: Session = Depends(get_db)):
    """Sinais de todos os ativos RV em carteira + watchlist, anotando a fonte."""
    pos_tickers: set[str] = set()
    if engine_cache.esta_calculado():
        estado = engine_cache.get_estado()
        posicoes_dict = estado["posicoes"]
        ativos = estado["ativos"]
        for tkr, p in posicoes_dict.items():
            if getattr(p, "qtd", 0) > 1e-9 and ativos.get(tkr, {}).get("classe") == "Renda Variável":
                pos_tickers.add(tkr.upper())

    wl_tickers = {
        i.ticker.upper()
        for i in db.query(WatchlistItem).filter(WatchlistItem.ativo == 1).all()
    }

    todos = sorted(pos_tickers | wl_tickers)
    if not todos:
        return []

    resultado = calcular_sinais_lote(todos)
    for s in resultado:
        t = s.get("ticker", "").upper()
        in_pos, in_wl = t in pos_tickers, t in wl_tickers
        s["fonte"] = "ambos" if (in_pos and in_wl) else ("posicao" if in_pos else "watchlist")

    return _filtrar(resultado, apenas_ativos)
