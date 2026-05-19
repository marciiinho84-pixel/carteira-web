"""Utilitários compartilhados: datas, liquidação D+2, lookback de preços."""

from datetime import date, timedelta

import pandas as pd


def preco_em(precos_ticker: dict, d: date, max_lookback_dias: int = 10):
    """Retorna preço em d ou o preço mais recente até max_lookback_dias atrás."""
    if not precos_ticker:
        return None
    if d in precos_ticker:
        return precos_ticker[d]
    datas_validas = sorted(dt for dt in precos_ticker.keys() if dt <= d)
    if not datas_validas:
        return None
    ultima = datas_validas[-1]
    if (d - ultima).days > max_lookback_dias:
        return None
    return precos_ticker[ultima]


def bdate_range(start: date, end: date) -> list:
    return [d.date() for d in pd.bdate_range(start=start, end=end)]


def num_dias_uteis_entre(d1: date, d2: date) -> int:
    """Conta dias úteis entre d1 (exclusivo) e d2 (inclusivo). Negativo se d2 < d1."""
    if d2 < d1:
        return -num_dias_uteis_entre(d2, d1)
    if d1 == d2:
        return 0
    return max(0, len(pd.bdate_range(start=d1, end=d2)) - 1)


def status_liquidacao(ev: dict, hoje: date) -> str:
    """LIQUIDADO / PENDENTE_ENTRADA / PENDENTE_SAIDA — com override manual via obs."""
    obs = str(ev.get("obs") or "")
    dias_uteis_passados = num_dias_uteis_entre(ev["data"], hoje)
    if "LIQUIDADO" in obs.upper() and "PENDENTE" not in obs.upper():
        return "LIQUIDADO"
    if dias_uteis_passados >= 2:
        return "LIQUIDADO"
    if ev["tipo"] == "COMPRA":
        return "PENDENTE_ENTRADA"
    elif ev["tipo"] == "VENDA":
        return "PENDENTE_SAIDA"
    return "LIQUIDADO"


def data_liquidacao(d_trade: date) -> date:
    """Data D+2 a partir da data do trade."""
    dias_uteis = pd.bdate_range(start=d_trade, periods=3)
    return dias_uteis[-1].date()


def status_liquidacao_d1(ev: dict, hoje: date) -> str:
    """LIQUIDADO / PENDENTE_ENTRADA / PENDENTE_SAIDA — prazo D+1 (fundos)."""
    obs = str(ev.get("obs") or "")
    dias_uteis_passados = num_dias_uteis_entre(ev["data"], hoje)
    if "LIQUIDADO" in obs.upper() and "PENDENTE" not in obs.upper():
        return "LIQUIDADO"
    if dias_uteis_passados >= 1:
        return "LIQUIDADO"
    if ev["tipo"] == "COMPRA":
        return "PENDENTE_ENTRADA"
    elif ev["tipo"] == "VENDA":
        return "PENDENTE_SAIDA"
    return "LIQUIDADO"


def data_liquidacao_d1(d_trade: date) -> date:
    """Data D+1 a partir da data do trade (para fundos CP)."""
    dias_uteis = pd.bdate_range(start=d_trade, periods=2)
    return dias_uteis[-1].date()
