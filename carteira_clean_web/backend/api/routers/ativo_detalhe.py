"""
GET /api/v1/ativos/{ticker}
Retorna dados agregados de um ativo: posição atual, sinais técnicos e fundamentos básicos.
Auth: require_auth
"""

import asyncio
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.api.routers.auth import require_auth
from carteira_clean_web.backend.engine.sinais_tecnicos import calcular_sinais_lote
from sqlalchemy.orm import Session

log = logging.getLogger("api.ativo_detalhe")

router = APIRouter(tags=["Ativo Detalhe"])


def _posicao_dict(ticker: str) -> Optional[dict]:
    """Retorna dados da posição do cache, ou None se não encontrado."""
    if not engine_cache.esta_calculado():
        return None
    estado = engine_cache.get_estado()
    posicoes = estado.get("posicoes", {})
    ativos = estado.get("ativos", {})
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado.get("hoje")

    p = posicoes.get(ticker)
    if p is None:
        return None

    info = ativos.get(ticker, {})

    from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO
    from carteira_clean_web.backend.engine.utils import preco_em

    familia = info.get("familia", "")
    preco_atual = None
    if familia in COTIZADO_PUBLICO:
        preco_atual = preco_em(precos_pub.get(ticker, {}), hoje)
    if preco_atual is None:
        preco_atual = preco_em(precos_man.get(ticker, {}), hoje, max_lookback_dias=60)

    if familia in AGREGADO_PRIVADO:
        valor_atual = preco_atual if preco_atual else p.custo_total
    else:
        valor_atual = p.qtd * preco_atual if preco_atual else p.custo_total

    pnl = valor_atual - p.custo_total
    pnl_pct = pnl / p.custo_total if p.custo_total > 0 else 0.0

    return {
        "ticker": ticker,
        "classe": info.get("classe"),
        "familia": familia,
        "bloco_ips": info.get("bloco_ips"),
        "setor": info.get("setor"),
        "composite": info.get("composite", "Gerida"),
        "qtd": float(p.qtd),
        "custo_total": float(p.custo_total),
        "custo_medio": float(p.custo_medio),
        "preco_atual": float(preco_atual) if preco_atual is not None else None,
        "valor_atual": float(valor_atual),
        "pnl": float(pnl),
        "pnl_pct": float(pnl_pct),
    }


def _sinais_dict(ticker: str) -> dict:
    """Retorna sinais técnicos para o ticker, ou dict vazio em caso de erro."""
    try:
        sinais = calcular_sinais_lote([ticker])
        if sinais:
            return sinais[0]
    except Exception as e:
        log.warning(f"Erro ao calcular sinais para {ticker}: {e}")
    return {}


async def _fundamentos_async(ticker: str) -> dict:
    """Chama fn_analise_fundamentalista em thread separada para não bloquear o event loop."""
    def _call():
        try:
            from carteira_clean_web.backend.mcp.tools.portfolio import fn_analise_fundamentalista
            return fn_analise_fundamentalista(ticker)
        except Exception as e:
            log.warning(f"Erro ao buscar fundamentos para {ticker}: {e}")
            return {}

    return await asyncio.to_thread(_call)


@router.get("/ativos/{ticker}")
async def ativo_detalhe(
    ticker: str,
    _email: Annotated[str, Depends(require_auth)],
    db: Session = Depends(get_db),
):
    """Dados agregados de um ativo: posição, sinais técnicos e fundamentos."""
    ticker = ticker.upper()

    # Posição atual
    posicao = _posicao_dict(ticker)

    # Sinais técnicos (rápido — yfinance local)
    sinais = await asyncio.to_thread(_sinais_dict, ticker)

    # Fundamentos (pode ser lento — 30s)
    fundamentos = await _fundamentos_async(ticker)

    # fn_analise_fundamentalista retorna {"todos_indicadores": {"P/L": v, "ROE (%)": v, ...}}
    fund_basicos: dict = {}
    if isinstance(fundamentos, dict) and "erro" not in fundamentos:
        todos = fundamentos.get("todos_indicadores", {})
        if todos:
            fund_basicos = {
                "pl": todos.get("P/L"),
                "pvp": todos.get("P/VP"),
                "roe": todos.get("ROE (%)"),
                "div_yield": todos.get("DY (%)"),
                "margem_ebitda": todos.get("Margem EBITDA (%)"),
                "div_liq_ebitda": todos.get("Dív.Líq/EBITDA"),
            }

    return {
        "ticker": ticker,
        "posicao": posicao,
        "sinais": sinais,
        "fundamentos": fund_basicos,
        "fundamentos_completos": fundamentos if isinstance(fundamentos, dict) and "erro" not in fundamentos else None,
    }


@router.get("/ativos/{ticker}/grafico")
async def ativo_grafico(
    ticker: str,
    _email: Annotated[str, Depends(require_auth)],
):
    """Gera gráfico técnico HTML via Plotly e retorna o nome do arquivo."""
    ticker = ticker.upper()
    loop = asyncio.get_event_loop()

    def _gen():
        try:
            from carteira_clean_web.backend.mcp.tools.portfolio import fn_grafico_tecnico
            return fn_grafico_tecnico(ticker)
        except Exception as e:
            log.warning(f"Erro ao gerar gráfico para {ticker}: {e}")
            return {"erro": str(e)}

    return await loop.run_in_executor(None, _gen)
