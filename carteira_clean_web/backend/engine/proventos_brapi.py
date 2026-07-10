"""
engine/proventos_brapi.py — Proventos (dividendos/JCP) e eventos societários
(bonificação/desdobramento) via brapi `dividends=true`, persistidos em
eventos_corporativos (fonte='brapi').

Idempotente por delete+insert escopado em (ticker, fonte='brapi') — a
tabela não tem chave única, e o payload da brapi sempre traz o histórico
inteiro a cada chamada, então reinserir sem limpar duplicaria a cada cron.
"""
from __future__ import annotations

from datetime import date, datetime

from . import brapi_client
from .ingestao_utils import get_logger, registrar_job_run
from ..db.models import EventoCorporativo
from ..db.session import get_session

log = get_logger("proventos_brapi")


def _parse_data(valor) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def _dados_dividendos(resultado: dict) -> dict:
    """A brapi normalmente aninha em 'dividendsData'; fallback pra raiz por
    robustez a variação de schema."""
    sub = resultado.get("dividendsData")
    return sub if isinstance(sub, dict) else resultado


def _extrair_cash_dividends(dados: dict) -> list[dict]:
    itens = dados.get("cashDividends") or []
    out = []
    for item in itens:
        data_evento = _parse_data(item.get("paymentDate") or item.get("lastDatePrior") or item.get("approvedOn"))
        if not data_evento:
            continue
        label = str(item.get("label") or "").upper()
        tipo = "JCP" if any(p in label for p in ("JUROS", "INTEREST", "JCP")) else "DIVIDENDO"
        out.append({"data_evento": data_evento, "tipo": tipo, "descricao": item.get("label") or tipo})
    return out


def _extrair_stock_dividends(dados: dict) -> list[dict]:
    itens = dados.get("stockDividends") or []
    out = []
    for item in itens:
        data_evento = _parse_data(item.get("approvedOn") or item.get("lastDatePrior"))
        if not data_evento:
            continue
        label = str(item.get("label") or "").upper()
        tipo = "DESDOBRAMENTO" if any(p in label for p in ("SPLIT", "DESDOBRAMENTO")) else "BONIFICACAO"
        out.append({"data_evento": data_evento, "tipo": tipo, "descricao": item.get("label") or tipo})
    return out


def _buscar_proventos_ticker(ticker: str) -> list[dict]:
    resp = brapi_client.get(f"quote/{ticker}", {"dividends": "true"})
    resultados = resp.get("results", [])
    if not resultados:
        return []
    dados = _dados_dividendos(resultados[0])
    return _extrair_cash_dividends(dados) + _extrair_stock_dividends(dados)


def coletar_proventos(tickers: list[str]) -> dict:
    """Coleta proventos/eventos societários via brapi para os tickers dados.
    UPSERT (delete+insert por ticker, fonte='brapi') em eventos_corporativos."""
    with registrar_job_run("proventos_brapi") as job:
        agora = datetime.utcnow()
        por_ticker: dict[str, list[EventoCorporativo]] = {}
        invalidos = 0

        for ticker in tickers:
            ticker = ticker.upper()
            try:
                eventos = _buscar_proventos_ticker(ticker)
            except Exception as e:
                log.warning(f"proventos_brapi: falha em {ticker} — {e}")
                invalidos += 1
                continue
            por_ticker[ticker] = [
                EventoCorporativo(
                    ticker=ticker,
                    tipo=ev["tipo"],
                    data_evento=ev["data_evento"],
                    descricao=str(ev["descricao"])[:500],
                    fonte="brapi",
                    fetched_at=agora,
                )
                for ev in eventos
            ]

        n = 0
        with get_session() as db:
            for ticker, linhas in por_ticker.items():
                db.query(EventoCorporativo).filter(
                    EventoCorporativo.ticker == ticker,
                    EventoCorporativo.fonte == "brapi",
                ).delete()
                db.add_all(linhas)
                n += len(linhas)
            db.commit()

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidos
        log.info(f"proventos_brapi: {len(tickers)} tickers, {n} eventos, {invalidos} inválidos")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidos, "tickers_processados": len(tickers)}
