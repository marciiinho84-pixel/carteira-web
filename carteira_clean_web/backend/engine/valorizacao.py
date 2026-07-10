"""
engine/valorizacao.py — Fórmula única de "preço atual" e "valor de posição".

Extraído literalmente de resultados.py::posicoes() (a tela de posições),
que era a versão mais completa entre ~9 cópias quase idênticas espalhadas
por mcp/tools/portfolio.py e api/routers/resultados.py. Nenhuma mudança de
comportamento — só isolamento em função compartilhada.
"""

from .constantes import AGREGADO_PRIVADO, COTIZADO_PUBLICO
from .utils import preco_em


def familia_agregada(ticker: str, familia: str) -> bool:
    """Ticker valorizado sem multiplicar por qtd (ex.: LCI/LCA, Letra de Crédito).

    Inclui detecção por prefixo do ticker mesmo sem familia cadastrada —
    comportamento de resultados.py::posicoes() ("a tela"), adotado aqui como
    único e canônico.
    """
    return familia in AGREGADO_PRIVADO or ticker.upper().startswith(("LCI-", "LCA-"))


def determinar_preco_atual(
    ticker: str,
    familia: str,
    precos_publicos: dict,
    precos_manuais: dict,
    data,
    max_lookback_dias: int = 60,
) -> float | None:
    """Preço público (se COTIZADO_PUBLICO) primeiro, manual com lookback depois."""
    preco = None
    if familia in COTIZADO_PUBLICO:
        preco = preco_em(precos_publicos.get(ticker, {}), data)
    if preco is None:
        preco = preco_em(precos_manuais.get(ticker, {}), data, max_lookback_dias=max_lookback_dias)
    return preco


def valorizar_posicao(
    pos,
    ticker: str,
    ativos: dict,
    precos_publicos: dict,
    precos_manuais: dict,
    data,
) -> dict:
    """{familia, is_agregado, preco_atual, valor_atual} para 1 posição.

    Não decide skip de qtd~0 — cada chamador mantém seu próprio filtro.
    """
    info = ativos.get(ticker, {})
    familia = info.get("familia", "")
    is_agregado = familia_agregada(ticker, familia)
    preco_atual = determinar_preco_atual(ticker, familia, precos_publicos, precos_manuais, data)

    if is_agregado:
        valor_atual = preco_atual if preco_atual else pos.custo_total
    else:
        valor_atual = pos.qtd * preco_atual if preco_atual else pos.custo_total

    return {
        "familia": familia,
        "is_agregado": is_agregado,
        "preco_atual": preco_atual,
        "valor_atual": valor_atual,
    }
