"""
engine/fundamentos_brapi.py — Fundamentos de peers via brapi
(defaultKeyStatistics + financialData), persistidos na tabela `fundamentos`
existente (fonte='brapi'), mesmo padrão append-only já usado por
fundamentals_client.py (yfinance, fonte='yfinance', só a carteira).

Cobre o universo inteiro (carteira + peers, ~80-100 tickers) — o
yfinance-based salvar_fundamentos_db() continua rodando só para a
carteira; os dois convivem na mesma tabela, diferenciados por `fonte`.
"""
from __future__ import annotations

from datetime import date, datetime

from . import brapi_client
from .ingestao_utils import get_logger, registrar_job_run
from ..db.models import Fundamento
from ..db.session import get_session

log = get_logger("fundamentos_brapi")

_MODULOS = "defaultKeyStatistics,financialData"

# Candidatos por indicador — brapi historicamente espelha os nomes de campo
# do Yahoo Finance para esses módulos; múltiplos candidatos por robustez a
# variação de schema entre módulos.
_CANDIDATOS: dict[str, list[str]] = {
    "PL":             ["trailingPE", "priceEarnings", "forwardPE"],
    "PVP":            ["priceToBook", "priceBook"],
    "ROE":            ["returnOnEquity"],
    "DY":             ["dividendYield", "trailingAnnualDividendYield"],
    "MARGEM_EBITDA":  ["ebitdaMargins", "ebitdaMargin"],
    "MARGEM_LIQUIDA": ["profitMargins", "netMargin"],
    "EV_EBITDA":      ["enterpriseToEbitda", "evToEbitda"],
}
# Indicadores que vêm como fração (0.15) e precisam virar percentual (15.0).
_SAO_PERCENTUAL = {"ROE", "DY", "MARGEM_EBITDA", "MARGEM_LIQUIDA"}


def _flatten(resultado: dict) -> dict:
    """Achata defaultKeyStatistics + financialData + raiz num único dict
    (raiz tem prioridade em caso de chave duplicada)."""
    flat: dict = {}
    for modulo in ("defaultKeyStatistics", "financialData"):
        sub = resultado.get(modulo) or {}
        if isinstance(sub, dict):
            flat.update(sub)
    flat.update({k: v for k, v in resultado.items() if not isinstance(v, (dict, list))})
    return flat


def _buscar_primeiro(flat: dict, chaves: list[str]) -> float | None:
    for chave in chaves:
        v = flat.get(chave)
        if v is None:
            continue
        try:
            f = float(v)
            if f != 0.0:
                return f
        except (TypeError, ValueError):
            continue
    return None


def _extrair_brapi(resultado: dict) -> dict[str, float | None]:
    flat = _flatten(resultado)
    out: dict[str, float | None] = {}
    for indicador, chaves in _CANDIDATOS.items():
        val = _buscar_primeiro(flat, chaves)
        if val is not None and indicador in _SAO_PERCENTUAL and abs(val) <= 1.0:
            val = val * 100
        out[indicador] = round(val, 4) if val is not None else None
    return out


def _buscar_ticker(ticker: str) -> dict[str, float | None] | None:
    resp = brapi_client.get(f"quote/{ticker}", {"modules": _MODULOS})
    resultados = resp.get("results", [])
    if not resultados:
        return None
    return _extrair_brapi(resultados[0])


def coletar_fundamentos_peers(tickers: list[str]) -> dict:
    """Coleta fundamentos via brapi para os tickers dados (universo_peers) e
    INSERE em `fundamentos` (fonte='brapi') — append-only, mesmo padrão do
    coletor yfinance. Falhas por ticker são contadas como inválidas, não
    interrompem a coleta dos demais."""
    with registrar_job_run("fundamentos_peers") as job:
        hoje = date.today()
        agora = datetime.utcnow()
        linhas = []
        invalidos = 0

        for ticker in tickers:
            try:
                indicadores = _buscar_ticker(ticker)
            except Exception as e:
                log.warning(f"fundamentos_peers: falha em {ticker} — {e}")
                invalidos += 1
                continue
            if indicadores is None:
                invalidos += 1
                continue
            for indicador, valor in indicadores.items():
                linhas.append(Fundamento(
                    ticker=ticker.upper(),
                    data_referencia=hoje,
                    indicador=indicador,
                    valor=valor,
                    fonte="brapi",
                    fetched_at=agora,
                ))

        if linhas:
            with get_session() as db:
                db.bulk_save_objects(linhas)
                db.commit()

        job.linhas_gravadas = len(linhas)
        job.linhas_invalidas = invalidos
        log.info(f"fundamentos_peers: {len(tickers)} tickers, {len(linhas)} linhas, {invalidos} inválidos")
        return {"linhas_gravadas": len(linhas), "linhas_invalidas": invalidos, "tickers_processados": len(tickers)}
