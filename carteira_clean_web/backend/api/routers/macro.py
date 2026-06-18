"""Router: indicadores macro + eventos corporativos (Fatia 3)."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter(tags=["macro"])


@router.get("/macro/indicadores")
def listar_macro(
    indicador: Optional[str] = None,
    ultimos_n: int = 30,
):
    """
    Retorna os últimos N pontos de cada indicador macro.

    Query params:
      indicador: filtrar por indicador específico (SELIC_META, IPCA, USD_BRL, …)
      ultimos_n: quantos pontos retornar por indicador (default 30)
    """
    from carteira_clean_web.backend.engine.macro_client import ler_macro
    indicadores = [indicador.upper()] if indicador else None
    return ler_macro(indicadores=indicadores, ultimos_n=ultimos_n)


@router.get("/macro/eventos-corporativos")
def listar_eventos_corp(
    ticker: Optional[str] = None,
    janela_dias: int = 60,
):
    """
    Retorna eventos corporativos futuros (earnings, ex-dividend).

    Query params:
      ticker: filtrar por ativo (ex: WEGE3)
      janela_dias: horizonte em dias (default 60)
    """
    from carteira_clean_web.backend.engine.macro_client import ler_eventos_corporativos
    return ler_eventos_corporativos(ticker=ticker, janela_dias=janela_dias)


@router.post("/macro/coletar", status_code=202)
def coletar_macro_endpoint(background_tasks: BackgroundTasks):
    """Dispara coleta assíncrona de indicadores macro (BCB SGS + Focus)."""
    from carteira_clean_web.backend.engine.macro_client import coletar_macro
    background_tasks.add_task(coletar_macro)
    return {"mensagem": "Coleta macro iniciada em background"}


@router.post("/macro/coletar-eventos", status_code=202)
def coletar_eventos_endpoint(background_tasks: BackgroundTasks):
    """Dispara coleta assíncrona de eventos corporativos (yfinance)."""
    from carteira_clean_web.backend.engine.macro_client import coletar_eventos_corporativos
    background_tasks.add_task(coletar_eventos_corporativos)
    return {"mensagem": "Coleta de eventos corporativos iniciada em background"}
