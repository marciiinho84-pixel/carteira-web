"""
macro_client.py — Coleta e persiste indicadores macro e eventos corporativos.

Fontes:
  - BCB SGS (api.bcb.gov.br): Selic meta, Selic diária, IPCA, USD/BRL
  - BCB Olinda: Focus (expectativa IPCA mediana do mercado)
  - yfinance: earnings dates, ex-dividend dates dos ativos em carteira

Padrão append-only: cada coleta insere novas linhas.
Leitura usa MAX(fetched_at) por (indicador, data_referencia).
"""

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import yfinance as yf

from carteira_clean_web.backend.db.session import get_session
from carteira_clean_web.backend.db.models import MacroIndicador, EventoCorporativo

log = logging.getLogger("macro_client")

# ─── BCB SGS series codes ─────────────────────────────────────────────────────
_SGS = {
    "SELIC_META":   432,   # Taxa Selic meta (% a.a.) — mensal
    "SELIC_DIARIA": 12,    # CDI / Selic Over (% a.d.) — diária
    "IPCA":         433,   # IPCA (% a.m.) — mensal
    "USD_BRL":      1,     # USD/BRL PTAX venda — diária
}

_SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados"
_OLINDA_FOCUS = (
    "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
    "/ExpectativaMercadoAnuais"
    "?$filter=Indicador eq 'IPCA' and baseCalculo eq 0"
    "&$orderby=Data desc&$top=20&$format=json&$select=Data,Mediana,DataReferencia"
)

_TIMEOUT = 30
_HEADERS = {"Accept": "application/json"}


# ─── BCB SGS ──────────────────────────────────────────────────────────────────

def _fetch_sgs(codigo: int, data_inicio: str, data_fim: str) -> list[dict]:
    """Busca série SGS entre data_inicio e data_fim (formato DD/MM/YYYY)."""
    url = _SGS_BASE.format(codigo)
    params = {"formato": "json", "dataInicial": data_inicio, "dataFinal": data_fim}
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_bcb_date(s: str) -> date:
    """Converte '31/12/2025' → date(2025,12,31)."""
    d, m, y = s.split("/")
    return date(int(y), int(m), int(d))


def _coletar_sgs(indicador: str, codigo: int, janela_dias: int = 90) -> list[MacroIndicador]:
    hoje = date.today()
    inicio = hoje - timedelta(days=janela_dias)
    di = inicio.strftime("%d/%m/%Y")
    df = hoje.strftime("%d/%m/%Y")
    try:
        pontos = _fetch_sgs(codigo, di, df)
    except Exception as e:
        log.warning(f"SGS {indicador}({codigo}): {e}")
        return []

    now = datetime.utcnow()
    rows = []
    for p in pontos:
        try:
            dt = _parse_bcb_date(p["data"])
            val = float(p["valor"].replace(",", "."))
            rows.append(MacroIndicador(
                indicador=indicador,
                data_referencia=dt,
                valor=val,
                fonte=f"BCB_SGS_{codigo}",
                fetched_at=now,
            ))
        except Exception:
            pass
    return rows


# ─── Olinda Focus ─────────────────────────────────────────────────────────────

def _coletar_focus() -> list[MacroIndicador]:
    """Expectativa mediana IPCA anual (Focus/BCB Olinda) — últimas 20 observações."""
    try:
        resp = requests.get(_OLINDA_FOCUS, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json().get("value", [])
    except Exception as e:
        log.warning(f"Focus Olinda: {e}")
        return []

    now = datetime.utcnow()
    rows = []
    for item in data:
        try:
            dt = date.fromisoformat(item["Data"])
            val = float(item["Mediana"])
            rows.append(MacroIndicador(
                indicador="IPCA_FOCUS",
                data_referencia=dt,
                valor=val,
                fonte="BCB_OLINDA_FOCUS",
                fetched_at=now,
            ))
        except Exception:
            pass
    return rows


# ─── yfinance eventos corporativos ───────────────────────────────────────────

def _tickers_rv_carteira() -> list[str]:
    """Retorna tickers de RV da carteira via cache de ativos."""
    try:
        from carteira_clean_web.backend.api import cache as engine_cache
        estado = engine_cache.get_estado()
        ativos = estado.get("ativos", {})
        _RV = {"Ação BR", "BDR", "BDR de ETF", "ETF BR"}
        return [t for t, v in ativos.items() if v.get("classe") in _RV]
    except Exception:
        return []


def _coletar_eventos_yf(tickers: list[str]) -> list[EventoCorporativo]:
    """Coleta earnings_date e ex_dividend_date para cada ticker via yfinance."""
    rows = []
    now = datetime.utcnow()
    hoje = date.today()
    janela_futura = hoje + timedelta(days=180)

    for tkr in tickers:
        yf_symbol = tkr + ".SA" if not tkr.endswith(".SA") else tkr
        try:
            yf_t = yf.Ticker(yf_symbol)
            cal = yf_t.calendar
            if cal is None:
                continue

            # earnings date
            ed = cal.get("Earnings Date")
            if ed is not None:
                for raw_date in (ed if hasattr(ed, '__iter__') else [ed]):
                    try:
                        ev_date = (
                            raw_date.date()
                            if hasattr(raw_date, "date")
                            else date.fromisoformat(str(raw_date)[:10])
                        )
                        if hoje <= ev_date <= janela_futura:
                            rows.append(EventoCorporativo(
                                ticker=tkr,
                                tipo="EARNINGS_DATE",
                                data_evento=ev_date,
                                descricao="Divulgação de resultados (yfinance)",
                                fonte="yfinance",
                                fetched_at=now,
                            ))
                    except Exception:
                        pass

            # ex-dividend date
            xd = cal.get("Ex-Dividend Date")
            if xd is not None:
                try:
                    xd_date = (
                        xd.date() if hasattr(xd, "date") else date.fromisoformat(str(xd)[:10])
                    )
                    if hoje <= xd_date <= janela_futura:
                        rows.append(EventoCorporativo(
                            ticker=tkr,
                            tipo="EX_DIVIDEND_DATE",
                            data_evento=xd_date,
                            descricao="Data ex-dividendo (yfinance)",
                            fonte="yfinance",
                            fetched_at=now,
                        ))
                except Exception:
                    pass

        except Exception as e:
            log.warning(f"yfinance eventos {tkr}: {e}")
        time.sleep(0.3)

    return rows


# ─── Coleta macro completa ────────────────────────────────────────────────────

def coletar_macro(janela_dias: int = 90) -> dict:
    """
    Coleta todos os indicadores macro e persiste no banco.

    Retorna:
        {"linhas_inseridas": N, "por_indicador": {...}, "erros": [...]}
    """
    rows: list[MacroIndicador] = []
    for indicador, codigo in _SGS.items():
        r = _coletar_sgs(indicador, codigo, janela_dias)
        rows.extend(r)
        log.info(f"  SGS {indicador}: {len(r)} pontos")
        time.sleep(0.5)

    focus_rows = _coletar_focus()
    rows.extend(focus_rows)
    log.info(f"  Focus: {len(focus_rows)} pontos")

    # Calcular sumário ANTES de adicionar à session (objetos ficam expirados após close)
    by_ind: dict[str, int] = {}
    for r in rows:
        by_ind[r.indicador] = by_ind.get(r.indicador, 0) + 1
    n_rows = len(rows)

    with get_session() as db:
        for r in rows:
            db.add(r)
        db.commit()

    return {"linhas_inseridas": n_rows, "por_indicador": by_ind, "erros": []}


def coletar_eventos_corporativos(tickers: list[str] | None = None) -> dict:
    """
    Coleta eventos corporativos (earnings, ex-dividend) via yfinance.

    Args:
        tickers: lista de tickers. Se None, usa ativos RV da carteira.

    Retorna:
        {"linhas_inseridas": N, "tickers_processados": N}
    """
    if tickers is None:
        tickers = _tickers_rv_carteira()
    if not tickers:
        return {"linhas_inseridas": 0, "tickers_processados": 0}

    rows = _coletar_eventos_yf(tickers)

    with get_session() as db:
        for r in rows:
            db.add(r)
        db.commit()

    log.info(f"Eventos corporativos: {len(rows)} linhas para {len(tickers)} tickers")
    return {"linhas_inseridas": len(rows), "tickers_processados": len(tickers)}


# ─── Leitura (para tools MCP e tela) ─────────────────────────────────────────

def ler_macro(indicadores: list[str] | None = None, ultimos_n: int = 30) -> dict[str, list[dict]]:
    """
    Retorna os últimos N pontos de cada indicador macro.

    Returns:
        {"SELIC_META": [{"data": ..., "valor": ...}, ...], ...}
    """
    todos = ["SELIC_META", "SELIC_DIARIA", "IPCA", "USD_BRL", "IPCA_FOCUS"]
    alvo = indicadores if indicadores else todos

    result: dict[str, list[dict]] = {}
    with get_session() as db:
        for ind in alvo:
            linhas = (
                db.query(MacroIndicador)
                .filter(MacroIndicador.indicador == ind)
                .order_by(MacroIndicador.data_referencia.desc())
                .limit(ultimos_n)
                .all()
            )
            result[ind] = [
                {"data": str(r.data_referencia), "valor": r.valor, "fonte": r.fonte}
                for r in linhas
            ]
    return result


def ler_eventos_corporativos(
    ticker: str | None = None,
    janela_dias: int = 60,
) -> list[dict]:
    """
    Retorna eventos corporativos nos próximos janela_dias dias.

    Args:
        ticker: filtrar por ativo específico. None = todos.
        janela_dias: quantos dias à frente buscar (default 60).
    """
    hoje = date.today()
    ate = hoje + timedelta(days=janela_dias)

    with get_session() as db:
        q = (
            db.query(EventoCorporativo)
            .filter(
                EventoCorporativo.data_evento >= hoje,
                EventoCorporativo.data_evento <= ate,
            )
            .order_by(EventoCorporativo.data_evento)
        )
        if ticker:
            q = q.filter(EventoCorporativo.ticker == ticker.upper())
        return [r.to_dict() for r in q.all()]
