"""
engine/taxonomia.py — Coletor de taxonomia setorial (brapi /api/quote/list)
e mapeamento setor → índice setorial B3.

Popula taxonomia_setorial (ticker → setor_brapi) e resolve, para cada
setor_brapi, qual índice setorial B3 (dos já persistidos em `benchmarks`,
prefixo IDX_ — ver engine/precos.py::_SETORIAL_YF_MAP) é o mais próximo.

O mapeamento é por substring (case-insensitive) porque a nomenclatura de
setor da brapi pode variar (ex.: "Financial Services" vs "Finance") — mais
robusto que exigir string exata.

Achado em produção (2026-07): a brapi classifica sistematicamente o setor
imobiliário brasileiro (construtoras, incorporadoras, shopping centers)
sob "Finance" — padrão de classificação FactSet, que trata estruturas de
propriedade/financiamento imobiliário como subsetor financeiro. Exemplos
confirmados: ALOS3 (shopping centers), MDNE3 e PLPL3 (incorporadoras).
Ativo novo desse setor que aparecer com setor_brapi="Finance" deve receber
o mesmo override (setor_correto="Imobiliário") via adicionar_override().
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import brapi_client
from .ingestao_utils import get_logger, registrar_job_run, upsert_df
from ..db.models import TaxonomiaOverride, TaxonomiaSetorial
from ..db.session import get_session

log = get_logger("taxonomia")

_PAGE_SIZE = 100
_MAX_PAGINAS = 200  # trava de segurança contra loop infinito de paginação

# Ordem importa: termos mais específicos primeiro (ex.: "electric" antes de
# "utilit", pra "Electric Utilities" cair em IEE, não em UTIL genérico).
# Inclui EN (vocabulário da brapi) e PT-BR (vocabulário usado em
# taxonomia_override, escrito por humano — ver adicionar_override()).
_MAPA_SETOR_INDICE: list[tuple[str, str]] = [
    ("electric", "IDX_IEE"),
    ("elétrica", "IDX_IEE"),
    ("eletrica", "IDX_IEE"),
    ("utilit", "IDX_UTIL"),
    ("saneamento", "IDX_UTIL"),
    ("real estate", "IDX_IMOB"),
    ("imobiliário", "IDX_IMOB"),
    ("imobiliaria", "IDX_IMOB"),
    ("shopping", "IDX_IMOB"),
    ("construção civil", "IDX_IMOB"),
    ("construcao civil", "IDX_IMOB"),
    ("financ", "IDX_IFNC"),
    ("banco", "IDX_IFNC"),
    ("energy", "IDX_IMAT"),
    ("materials", "IDX_IMAT"),
    ("materiais básicos", "IDX_IMAT"),
    ("materiais basicos", "IDX_IMAT"),
    ("petróleo", "IDX_IMAT"),
    ("petroleo", "IDX_IMAT"),
    ("mineração", "IDX_IMAT"),
    ("mineracao", "IDX_IMAT"),
    ("industrial", "IDX_INDX"),
    ("indústria", "IDX_INDX"),
    ("industria", "IDX_INDX"),
    ("consumer", "IDX_ICON"),
    ("consumo", "IDX_ICON"),
    ("varejo", "IDX_ICON"),
]

# Aliases PT-BR para permitir que o parâmetro `setor` das tools aceite termos
# do dia a dia (ex.: "Bancos") sem precisar saber a string exata da brapi.
DISPLAY_POR_INDICE: dict[str, str] = {
    "IDX_IFNC": "Bancos e Serviços Financeiros",
    "IDX_IMOB": "Construção Civil e Imobiliário",
    "IDX_UTIL": "Utilidade Pública / Saneamento",
    "IDX_IEE":  "Energia Elétrica",
    "IDX_INDX": "Industrial",
    "IDX_ICON": "Consumo",
    "IDX_IMAT": "Materiais Básicos / Petróleo e Gás / Mineração",
}


def mapear_setor_para_indice(setor_brapi: str | None) -> str | None:
    """Mapeia um setor_brapi (string livre) para o índice setorial B3
    correspondente (ex.: 'Financial Services' → 'IDX_IFNC'). None se não casar."""
    if not setor_brapi:
        return None
    s = setor_brapi.lower()
    for palavra, indice in _MAPA_SETOR_INDICE:
        if palavra in s:
            return indice
    return None


def _coletar_paginas() -> list[dict]:
    """Percorre /api/quote/list paginado até esgotar ou bater o limite de segurança."""
    linhas: list[dict] = []
    pagina = 1
    while pagina <= _MAX_PAGINAS:
        resp = brapi_client.get("quote/list", {"limit": _PAGE_SIZE, "page": pagina})
        stocks = resp.get("stocks", [])
        if not stocks:
            break
        for item in stocks:
            ticker = item.get("stock") or item.get("ticker")
            if not ticker:
                continue
            nome = item.get("name") or item.get("shortName") or item.get("longName")
            linhas.append({"ticker": ticker.upper(), "setor_brapi": item.get("sector"), "nome": nome})
        if not resp.get("hasNextPage", False):
            break
        pagina += 1
    if pagina > _MAX_PAGINAS:
        log.warning(f"taxonomia: atingiu o limite de segurança de {_MAX_PAGINAS} páginas")
    return linhas


def coletar_taxonomia_setorial() -> dict:
    """Coleta ticker→setor de todos os tickers listados na brapi e faz UPSERT
    em taxonomia_setorial. Retorna {"linhas_gravadas": N, "linhas_invalidas": M}."""
    with registrar_job_run("taxonomia_setorial") as job:
        linhas = _coletar_paginas()
        invalidas = sum(1 for l in linhas if not l.get("setor_brapi"))

        n = 0
        if linhas:
            df = pd.DataFrame(linhas)
            df["atualizado_em"] = datetime.utcnow()
            with get_session() as db:
                n = upsert_df(db, TaxonomiaSetorial.__table__, ["ticker"], df)

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidas
        log.info(f"taxonomia_setorial: {n} tickers gravados, {invalidas} sem setor")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidas}


def resolver_setor(ticker: str) -> str | None:
    """Lê o setor_brapi mais recente para um ticker. None se não encontrado."""
    with get_session() as db:
        row = (
            db.query(TaxonomiaSetorial)
            .filter(TaxonomiaSetorial.ticker == ticker.upper())
            .first()
        )
        return row.setor_brapi if row else None


def nome_empresa(ticker: str) -> str | None:
    """Lê o nome da empresa mais recente para um ticker. None se não encontrado."""
    with get_session() as db:
        row = (
            db.query(TaxonomiaSetorial)
            .filter(TaxonomiaSetorial.ticker == ticker.upper())
            .first()
        )
        return row.nome if row else None


def carregar_taxonomia_completa() -> dict[str, str | None]:
    """Retorna {ticker: setor_brapi} para todos os tickers coletados — setor
    bruto da brapi, sem override. Usado por definir_universo_peers() pra
    montar a query de descoberta de peers (/quote/list?sector=X), que
    precisa do vocabulário original da brapi pra casar de verdade."""
    with get_session() as db:
        rows = db.query(TaxonomiaSetorial).all()
        return {r.ticker: r.setor_brapi for r in rows}


def carregar_overrides() -> dict[str, str]:
    """Retorna {ticker: setor_correto} de todos os overrides cadastrados."""
    with get_session() as db:
        rows = db.query(TaxonomiaOverride).all()
        return {r.ticker: r.setor_correto for r in rows}


def carregar_setores_efetivos() -> dict[str, str | None]:
    """Retorna {ticker: setor}, com override manual (taxonomia_override)
    tendo prioridade sobre o setor_brapi coletado. Usado por
    contexto_setorial/peers_do_mesmo_setor (mapeamento pro índice B3) —
    diferente de carregar_taxonomia_completa(), que fica com o setor bruto
    da brapi pra não quebrar a query de descoberta de peers."""
    efetivos = carregar_taxonomia_completa()
    efetivos.update(carregar_overrides())
    return efetivos


def adicionar_override(ticker: str, setor_correto: str, motivo: str | None = None) -> None:
    """Cadastra ou atualiza a correção manual de setor de um ticker."""
    ticker = ticker.upper()
    with get_session() as db:
        existente = db.query(TaxonomiaOverride).filter(TaxonomiaOverride.ticker == ticker).first()
        if existente:
            existente.setor_correto = setor_correto
            existente.motivo = motivo
        else:
            db.add(TaxonomiaOverride(
                ticker=ticker, setor_correto=setor_correto, motivo=motivo,
                criado_em=datetime.utcnow(),
            ))
        db.commit()
