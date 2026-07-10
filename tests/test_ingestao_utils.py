"""
tests/test_ingestao_utils.py — Fundação comum dos coletores de ingestão
(Fase 1 da fatia "Ingestão de dados").

Casos:
  1) retry_padrao: reencaminha ConnectionError até estourar stop_after_attempt(4).
  2) retry_padrao: NÃO reencaminha em HTTPError 404 (4xx) — falha na 1ª tentativa.
  3) retry_padrao: reencaminha em HTTPError 429 e 500 (retryable).
  4) upsert_df: insert novo + upsert em cima do mesmo (chaves) atualiza, não duplica.
  5) registrar_job_run: caminho de sucesso grava status='sucesso' + contagens.
  6) registrar_job_run: exceção no bloco grava status='erro' e repropaga.

Rodar:
    pytest tests/test_ingestao_utils.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
import requests
from sqlalchemy import Column, Float, Integer, MetaData, Table, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.ingestao_utils import (
    registrar_job_run,
    retry_padrao,
    upsert_df,
)
from carteira_clean_web.backend.db.models import JobRun


# ─── 1-3: retry_padrao ──────────────────────────────────────────────────────

def _http_error(status_code):
    resp = requests.Response()
    resp.status_code = status_code
    return requests.exceptions.HTTPError(response=resp)


def test_retry_padrao_reencaminha_connection_error_ate_estourar():
    chamadas = {"n": 0}

    @retry_padrao
    def flaky():
        chamadas["n"] += 1
        raise requests.exceptions.ConnectionError("sem rede")

    with pytest.raises(requests.exceptions.ConnectionError):
        flaky()
    assert chamadas["n"] == 4  # stop_after_attempt(4)


def test_retry_padrao_nao_reencaminha_4xx():
    chamadas = {"n": 0}

    @retry_padrao
    def flaky():
        chamadas["n"] += 1
        raise _http_error(404)

    with pytest.raises(requests.exceptions.HTTPError):
        flaky()
    assert chamadas["n"] == 1  # não é retryable — falha na 1ª tentativa


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_padrao_reencaminha_429_5xx(status):
    chamadas = {"n": 0}

    @retry_padrao
    def flaky():
        chamadas["n"] += 1
        if chamadas["n"] < 2:
            raise _http_error(status)
        return "ok"

    assert flaky() == "ok"
    assert chamadas["n"] == 2


# ─── 4: upsert_df ────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    tabela = Table(
        "pontos_teste",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("ticker", Text, nullable=False),
        Column("data", Text, nullable=False),
        Column("valor", Float, nullable=False),
        UniqueConstraint("ticker", "data", name="uq_ticker_data"),
    )
    metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session, tabela
    session.close()


def test_upsert_df_insere_novo(sqlite_session):
    session, tabela = sqlite_session
    df = pd.DataFrame([{"ticker": "PETR4", "data": "2026-01-02", "valor": 10.0}])
    n = upsert_df(session, tabela, ["ticker", "data"], df)
    assert n == 1
    linhas = session.execute(tabela.select()).fetchall()
    assert len(linhas) == 1
    assert linhas[0].valor == 10.0


def test_upsert_df_atualiza_sem_duplicar(sqlite_session):
    session, tabela = sqlite_session
    df1 = pd.DataFrame([{"ticker": "PETR4", "data": "2026-01-02", "valor": 10.0}])
    upsert_df(session, tabela, ["ticker", "data"], df1)

    df2 = pd.DataFrame([{"ticker": "PETR4", "data": "2026-01-02", "valor": 11.5}])
    upsert_df(session, tabela, ["ticker", "data"], df2)

    linhas = session.execute(tabela.select()).fetchall()
    assert len(linhas) == 1  # não duplicou
    assert linhas[0].valor == 11.5  # atualizou


def test_upsert_df_vazio_e_noop(sqlite_session):
    session, tabela = sqlite_session
    n = upsert_df(session, tabela, ["ticker", "data"], pd.DataFrame())
    assert n == 0


# ─── 5-6: registrar_job_run ──────────────────────────────────────────────────

@pytest.fixture
def patch_job_runs_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}", connect_args={"check_same_thread": False})
    JobRun.metadata.create_all(engine, tables=[JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def test_registrar_job_run_sucesso(patch_job_runs_session):
    Session = patch_job_runs_session
    with registrar_job_run("teste_job") as job:
        job.linhas_gravadas = 42
        job.linhas_invalidas = 3

    db = Session()
    run = db.query(JobRun).filter(JobRun.job == "teste_job").one()
    assert run.status == "sucesso"
    assert run.linhas_gravadas == 42
    assert run.linhas_invalidas == 3
    assert run.terminado_em is not None
    db.close()


def test_registrar_job_run_erro_repropaga_e_grava_status(patch_job_runs_session):
    Session = patch_job_runs_session
    with pytest.raises(ValueError):
        with registrar_job_run("teste_job_falho") as job:
            job.linhas_gravadas = 5
            raise ValueError("boom")

    db = Session()
    run = db.query(JobRun).filter(JobRun.job == "teste_job_falho").one()
    assert run.status == "erro"
    assert run.linhas_gravadas == 5
    assert "boom" in run.erro
    db.close()
