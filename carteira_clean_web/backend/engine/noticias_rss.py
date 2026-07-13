"""
engine/noticias_rss.py — Notícias por ativo via Google News RSS.

yfinance .news é descontinuado como fonte (instável, frequentemente vazio) —
substituído por Google News RSS, persistido em `noticias` (UPSERT por
ticker+titulo, dedupe pedido na Fase 5) e lido de lá por noticias_ativos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from urllib.parse import quote

import feedparser
import pandas as pd
import requests

from . import taxonomia
from .ingestao_utils import get_logger, registrar_job_run, retry_padrao, upsert_df
from ..db.models import Noticia
from ..db.session import get_session

log = get_logger("noticias_rss")

_RSS_BASE = "https://news.google.com/rss/search"
_TIMEOUT = 20

# Google News RSS "alarga" a busca silenciosamente quando a query exata tem
# poucos resultados — devolve manchetes populares sem relação alguma com o
# ticker (ex.: previsão do tempo). Filtramos aqui, do lado do coletor, em vez
# de confiar cegamente no que o Google retornou.
_STOPWORDS_NOME_EMPRESA = {
    "sa", "s.a", "ltda", "on", "pn", "pnb", "pna", "unit", "units",
    "de", "da", "do", "das", "dos", "e", "cia", "companhia", "participacoes",
    "holding", "brasil", "brasileira", "brasileiro",
}


def _normalizar(txt: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _palavras_significativas(nome: str) -> list[str]:
    """Palavras do nome da empresa úteis pra checar relevância — descarta
    conectivos/sufixos societários e palavras curtas demais (ruído)."""
    normalizado = _normalizar(nome)
    palavras = re.findall(r"[a-z0-9]+", normalizado)
    return [p for p in palavras if len(p) >= 4 and p not in _STOPWORDS_NOME_EMPRESA]


def _ticker_base(ticker: str) -> str:
    """PETR4 -> PETR, WEGE3 -> WEGE (remove o dígito de classe da ação)."""
    return re.sub(r"\d+$", "", ticker.upper())


def _titulo_relevante(titulo: str, ticker: str, palavras_nome: list[str]) -> bool:
    titulo_norm = _normalizar(titulo)
    if ticker.lower() in titulo_norm:
        return True
    base = _ticker_base(ticker).lower()
    if base and base in titulo_norm:
        return True
    return any(p in titulo_norm for p in palavras_nome)


def _montar_query(ticker: str, nome: str | None) -> str:
    if nome:
        return f'"{nome}" OR {ticker} when:2d'
    return f"{ticker} when:2d"


def _url_rss(query: str) -> str:
    return f"{_RSS_BASE}?q={quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


@retry_padrao
def _buscar_feed(url: str):
    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def _extrair_publicado_em(entry) -> datetime | None:
    parsed = entry.get("published_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6])
    except (TypeError, ValueError):
        return None


def _extrair_fonte(entry) -> str | None:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    # Google News RSS costuma sufixar o título com " - Nome da Fonte"
    titulo = entry.get("title", "")
    if " - " in titulo:
        return titulo.rsplit(" - ", 1)[-1]
    return None


def coletar_noticias_ticker(ticker: str) -> list[dict]:
    """Busca notícias recentes (últimos 2 dias) de 1 ticker no Google News RSS.
    Dedupe por título dentro do próprio resultado. Descarta manchetes sem
    relação com o ticker/empresa (Google News RSS às vezes "alarga" a busca e
    devolve conteúdo popular não relacionado, ex.: previsão do tempo) — a
    menos que isso descartaria tudo, caso em que mantém sem filtrar (nome de
    empresa provavelmente genérico/curto demais pro filtro) e loga aviso."""
    nome = taxonomia.nome_empresa(ticker)
    url = _url_rss(_montar_query(ticker, nome))
    feed = _buscar_feed(url)

    vistos: set[str] = set()
    candidatos = []
    for entry in feed.entries:
        titulo = entry.get("title", "").strip()
        if not titulo or titulo in vistos:
            continue
        vistos.add(titulo)
        candidatos.append({
            "ticker": ticker.upper(),
            "titulo": titulo,
            "fonte": _extrair_fonte(entry),
            "url": entry.get("link"),
            "publicado_em": _extrair_publicado_em(entry),
        })

    palavras_nome = _palavras_significativas(nome) if nome else []
    relevantes = [c for c in candidatos if _titulo_relevante(c["titulo"], ticker, palavras_nome)]

    if candidatos and not relevantes:
        log.warning(
            f"noticias_rss: filtro de relevância descartaria todas as {len(candidatos)} "
            f"notícia(s) de {ticker} (nome='{nome}') — mantendo sem filtro."
        )
        return candidatos

    descartados = len(candidatos) - len(relevantes)
    if descartados:
        log.info(f"noticias_rss: {ticker} — {descartados} notícia(s) descartada(s) por irrelevância.")

    return relevantes


def coletar_noticias(tickers: list[str]) -> dict:
    """Coleta notícias via Google News RSS para os tickers dados. UPSERT
    (ticker+titulo) em `noticias` — dedupe entre coletas do mesmo dia."""
    with registrar_job_run("noticias_rss") as job:
        agora = datetime.utcnow()
        linhas: list[dict] = []
        invalidos = 0

        for ticker in tickers:
            try:
                itens = coletar_noticias_ticker(ticker)
            except Exception as e:
                log.warning(f"noticias_rss: falha em {ticker} — {e}")
                invalidos += 1
                continue
            for item in itens:
                item["coletado_em"] = agora
                linhas.append(item)

        n = 0
        if linhas:
            df = pd.DataFrame(linhas)
            with get_session() as db:
                n = upsert_df(db, Noticia.__table__, ["ticker", "titulo"], df)

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidos
        log.info(f"noticias_rss: {len(tickers)} tickers, {n} notícias, {invalidos} inválidos")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidos, "tickers_processados": len(tickers)}


def ler_noticias(tickers: list[str] | None = None, dias: int = 7) -> list[dict]:
    """Lê notícias persistidas dos últimos `dias` dias (por publicado_em, ou
    coletado_em se a data de publicação não veio no feed)."""
    corte = datetime.utcnow() - timedelta(days=dias)
    with get_session() as db:
        q = db.query(Noticia).filter(
            (Noticia.publicado_em >= corte) | (Noticia.publicado_em.is_(None) & (Noticia.coletado_em >= corte))
        ).order_by(Noticia.publicado_em.desc().nullslast())
        if tickers:
            q = q.filter(Noticia.ticker.in_([t.upper() for t in tickers]))
        return [
            {
                "ticker": r.ticker,
                "titulo": r.titulo,
                "fonte": r.fonte,
                "link": r.url,
                "data": r.publicado_em.strftime("%Y-%m-%d") if r.publicado_em else "",
            }
            for r in q.all()
        ]
