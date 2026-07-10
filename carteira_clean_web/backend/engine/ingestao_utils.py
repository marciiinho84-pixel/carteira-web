"""
engine/ingestao_utils.py — Padrões comuns para os coletores de ingestão
(taxonomia setorial, peers/fundamentos brapi, eventos corporativos, notícias).

Fornece:
  - retry_padrao: decorator de retry (tenacity) para chamadas HTTP externas.
  - upsert_df: INSERT ... ON CONFLICT DO UPDATE em lote a partir de um DataFrame.
  - log_json: logger que emite uma linha JSON por evento.
  - registrar_job_run: context manager que grava início/fim/status em job_runs.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from datetime import datetime

import pandas as pd
import requests
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

from carteira_clean_web.backend.db.models import JobRun
from carteira_clean_web.backend.db.session import get_session


# ─── Retry padrão ──────────────────────────────────────────────────────────
def _e_retryable(exc: BaseException) -> bool:
    """Retry só em falha de rede/timeout ou HTTP 429/5xx — nunca em 4xx
    (4xx é erro do request, tentar de novo não muda o resultado)."""
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        resp = exc.response
        return resp is not None and (resp.status_code == 429 or resp.status_code >= 500)
    return False


retry_padrao = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 2),
    retry=retry_if_exception(_e_retryable),
    reraise=True,
)


# ─── Logger estruturado JSON ───────────────────────────────────────────────
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(nome: str) -> logging.Logger:
    """Logger que emite 1 linha JSON por evento (stdout — coletado pelo docker logs)."""
    logger = logging.getLogger(nome)
    if not any(isinstance(h.formatter, _JsonFormatter) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)
    return logger


# ─── Upsert em lote ─────────────────────────────────────────────────────────
def upsert_df(session: Session, tabela, chaves: list[str], df: pd.DataFrame, lote: int = 500) -> int:
    """UPSERT em lote: INSERT ... ON CONFLICT (chaves) DO UPDATE.

    tabela: SQLAlchemy Table (ex.: Model.__table__) — precisa ter
    UniqueConstraint/índice único cobrindo exatamente `chaves` no schema real,
    senão o ON CONFLICT não casa e o banco levanta erro.
    Retorna o número de linhas enviadas (não o número de linhas alteradas).
    """
    if df.empty:
        return 0

    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
    else:
        raise NotImplementedError(f"upsert_df: dialect '{dialect}' não suportado")

    registros = df.to_dict("records")
    colunas_update = [c for c in df.columns if c not in chaves]

    for i in range(0, len(registros), lote):
        pedaco = registros[i : i + lote]
        stmt = _insert(tabela).values(pedaco)
        if colunas_update:
            set_ = {c: getattr(stmt.excluded, c) for c in colunas_update}
            stmt = stmt.on_conflict_do_update(index_elements=chaves, set_=set_)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=chaves)
        session.execute(stmt)
    session.commit()
    return len(registros)


# ─── Registro em job_runs ───────────────────────────────────────────────────
class _JobRunHandle:
    """Alça mutável devolvida por registrar_job_run — o coletor preenche
    linhas_gravadas/linhas_invalidas antes do bloco `with` terminar."""

    def __init__(self):
        self.linhas_gravadas = 0
        self.linhas_invalidas = 0


@contextmanager
def registrar_job_run(nome_job: str):
    """Context manager: cria 1 linha em job_runs no início, atualiza no fim.

    Uso:
        with registrar_job_run("taxonomia_setorial") as job:
            ... coleta ...
            job.linhas_gravadas = n

    Se o bloco levantar exceção, status vira 'erro' e a exceção é
    repropagada (não é engolida).
    """
    handle = _JobRunHandle()
    with get_session() as db:
        run = JobRun(job=nome_job, iniciado_em=datetime.utcnow(), status="rodando")
        db.add(run)
        db.commit()
        run_id = run.id

    try:
        yield handle
    except Exception as e:
        with get_session() as db:
            run = db.get(JobRun, run_id)
            run.status = "erro"
            run.terminado_em = datetime.utcnow()
            run.linhas_gravadas = handle.linhas_gravadas
            run.linhas_invalidas = handle.linhas_invalidas
            run.erro = str(e)[:2000]
            db.commit()
        raise
    else:
        with get_session() as db:
            run = db.get(JobRun, run_id)
            run.status = "sucesso"
            run.terminado_em = datetime.utcnow()
            run.linhas_gravadas = handle.linhas_gravadas
            run.linhas_invalidas = handle.linhas_invalidas
            db.commit()
