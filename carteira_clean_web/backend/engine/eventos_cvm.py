"""
engine/eventos_cvm.py — Fatos relevantes / avisos / calendário via IPE CVM
(dados.cvm.gov.br, CSV anual em ZIP), casados por CNPJ com ativos.cnpj_cvm.

Schema do CSV validado ao vivo na Fase 6 (nomes de coluna batem com
_CANDIDATOS_COLUNA). Achado no mesmo backfill: só 2 dos 38 ativos da
carteira tinham cnpj_cvm cadastrado (2 fundos internos — nenhuma ação),
então o join nunca casava nada. popular_cnpj_ativos() resolve isso via
brapi summaryProfile (módulo disponível no plano gratuito, confirmado
pela própria mensagem de erro dos módulos pagos) antes da coleta.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime

import pandas as pd
import requests

from . import brapi_client
from .ingestao_utils import get_logger, registrar_job_run, retry_padrao
from ..db.models import Ativo, EventoCorporativo
from ..db.session import get_session

log = get_logger("eventos_cvm")

_URL_IPE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip"
_HEADERS = {"User-Agent": "curl/7.68.0"}
_TIMEOUT = 60

# Categoria do IPE (normalizada: strip + lower) → tipo em eventos_corporativos.
_CATEGORIAS_ALVO = {
    "calendário de eventos corporativos": "CALENDARIO_EVENTO",
    "calendario de eventos corporativos": "CALENDARIO_EVENTO",
    "fato relevante": "FATO_RELEVANTE",
    "aviso aos acionistas": "AVISO_ACIONISTAS",
}

_CANDIDATOS_COLUNA = {
    "cnpj": ["cnpj_companhia", "cnpj_cia", "cnpj"],
    "categoria": ["categoria"],
    "data": ["data_referencia", "data_entrega"],
    "assunto": ["assunto", "especie", "tipo"],
}


def _normalizar_cnpj(cnpj) -> str:
    return "".join(c for c in str(cnpj) if c.isdigit())


@retry_padrao
def _baixar_ipe(ano: int) -> pd.DataFrame:
    url = _URL_IPE.format(ano=ano)
    resp = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        nomes_csv = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not nomes_csv:
            return pd.DataFrame()
        with zf.open(nomes_csv[0]) as f:
            return pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)


def _achar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidatos:
        if cand in cols_lower:
            return cols_lower[cand]
    for cand in candidatos:
        for lower, orig in cols_lower.items():
            if cand in lower:
                return orig
    return None


def _mapear_cnpj_ticker() -> dict[str, str]:
    with get_session() as db:
        rows = db.query(Ativo.ticker, Ativo.cnpj_cvm).filter(Ativo.cnpj_cvm.isnot(None)).all()
    return {_normalizar_cnpj(cnpj): ticker for ticker, cnpj in rows if cnpj}


def popular_cnpj_ativos(tickers: list[str]) -> dict:
    """Preenche ativos.cnpj_cvm via brapi summaryProfile pros tickers dados
    que ainda não têm — sem isso o join do IPE CVM nunca casa nada. Só
    escreve quando cnpj_cvm está vazio (não sobrescreve cadastro manual)."""
    with registrar_job_run("cnpj_ativos") as job:
        with get_session() as db:
            existentes = dict(
                db.query(Ativo.ticker, Ativo.cnpj_cvm).filter(Ativo.ticker.in_(tickers)).all()
            )

        n, invalidos = 0, 0
        for ticker in tickers:
            if existentes.get(ticker):
                continue
            try:
                resp = brapi_client.get(f"quote/{ticker}", {"modules": "summaryProfile"})
            except Exception as e:
                log.debug(f"cnpj_ativos: falha em {ticker} — {e}")
                invalidos += 1
                continue
            resultados = resp.get("results", [])
            cnpj = (resultados[0].get("summaryProfile") or {}).get("cnpj") if resultados else None
            if not cnpj:
                invalidos += 1
                continue
            with get_session() as db:
                db.query(Ativo).filter(Ativo.ticker == ticker).update({"cnpj_cvm": cnpj})
                db.commit()
            n += 1

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidos
        log.info(f"cnpj_ativos: {n} tickers preenchidos, {invalidos} sem cnpj/erro")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidos}


def coletar_eventos_ipe(ano: int | None = None) -> dict:
    """Baixa o IPE da CVM do ano dado (default: ano corrente), filtra
    Calendário de Eventos/Fato Relevante/Aviso aos Acionistas, casa por CNPJ
    com ativos.cnpj_cvm e faz UPSERT (delete+insert por ticker,
    fonte='cvm_ipe') em eventos_corporativos."""
    with registrar_job_run("eventos_ipe_cvm") as job:
        ano = ano or date.today().year
        cnpj_ticker = _mapear_cnpj_ticker()
        if not cnpj_ticker:
            job.linhas_invalidas = 1
            log.warning("eventos_ipe_cvm: nenhum ativo com cnpj_cvm cadastrado — nada a casar")
            return {"linhas_gravadas": 0, "linhas_invalidas": 1}

        try:
            df = _baixar_ipe(ano)
        except Exception as e:
            log.warning(f"eventos_ipe_cvm: falha ao baixar IPE {ano} — {e}")
            job.linhas_invalidas = 1
            return {"linhas_gravadas": 0, "linhas_invalidas": 1}

        if df.empty:
            return {"linhas_gravadas": 0, "linhas_invalidas": 0}

        col_cnpj = _achar_coluna(df, _CANDIDATOS_COLUNA["cnpj"])
        col_categoria = _achar_coluna(df, _CANDIDATOS_COLUNA["categoria"])
        col_data = _achar_coluna(df, _CANDIDATOS_COLUNA["data"])
        col_assunto = _achar_coluna(df, _CANDIDATOS_COLUNA["assunto"])

        if not col_cnpj or not col_categoria or not col_data:
            log.warning(f"eventos_ipe_cvm: colunas essenciais não reconhecidas — colunas do CSV: {list(df.columns)}")
            job.linhas_invalidas = 1
            return {"linhas_gravadas": 0, "linhas_invalidas": 1}

        df = df.copy()
        df["_categoria_norm"] = df[col_categoria].astype(str).str.strip().str.lower()
        df = df[df["_categoria_norm"].isin(_CATEGORIAS_ALVO.keys())]
        df["_cnpj_norm"] = df[col_cnpj].map(_normalizar_cnpj)
        df = df[df["_cnpj_norm"].isin(cnpj_ticker.keys())]

        agora = datetime.utcnow()
        por_ticker: dict[str, list[EventoCorporativo]] = {}
        invalidos = 0
        for _, row in df.iterrows():
            ticker = cnpj_ticker[row["_cnpj_norm"]]
            tipo = _CATEGORIAS_ALVO[row["_categoria_norm"]]
            try:
                data_evento = pd.to_datetime(row[col_data]).date()
            except (ValueError, TypeError):
                invalidos += 1
                continue
            descricao = str(row[col_assunto]) if col_assunto and pd.notna(row.get(col_assunto)) else tipo
            por_ticker.setdefault(ticker, []).append(EventoCorporativo(
                ticker=ticker,
                tipo=tipo,
                data_evento=data_evento,
                descricao=descricao[:500],
                fonte="cvm_ipe",
                fetched_at=agora,
            ))

        n = 0
        with get_session() as db:
            for ticker, linhas in por_ticker.items():
                db.query(EventoCorporativo).filter(
                    EventoCorporativo.ticker == ticker,
                    EventoCorporativo.fonte == "cvm_ipe",
                ).delete()
                db.add_all(linhas)
                n += len(linhas)
            db.commit()

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidos
        log.info(f"eventos_ipe_cvm: {n} eventos gravados ({len(por_ticker)} tickers), {invalidos} inválidos")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidos, "tickers_casados": len(por_ticker)}
