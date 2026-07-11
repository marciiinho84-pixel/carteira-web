"""
tests/test_fundamentals_client_regra_null.py — regra geral "nunca gravar
NULL por cima de valor válido" no coletor yfinance da carteira (regressão
achada em produção: brapi sobrescrevia fundamentos yfinance com NULL —
mesma classe de bug corrigida em fundamentos_brapi.py, aqui é o espelho
pro coletor original).

Caso: salvar_fundamentos_db não grava linha pra indicador com valor None
(hoje: PVP disponível, ROIC indisponível → só PVP vira linha).

Rodar:
    pytest tests/test_fundamentals_client_regra_null.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.fundamentals_client import salvar_fundamentos_db
from carteira_clean_web.backend.db.models import Fundamento


@pytest.fixture
def patch_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fc.db'}", connect_args={"check_same_thread": False})
    Fundamento.metadata.create_all(engine, tables=[Fundamento.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.db.session.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def test_salvar_fundamentos_db_nao_grava_indicador_none(patch_session):
    Session = patch_session
    fake = {
        "PVP": 2.34, "PL": None, "ROE": None, "ROIC": None, "DY": None,
        "MARGEM_EBITDA": None, "DIV_LIQ_EBITDA": None, "MARGEM_LIQUIDA": None,
        "LPA": None, "VPA": None, "erro": None,
    }
    with patch(
        "carteira_clean_web.backend.engine.fundamentals_client.fetch_fundamentos_completos",
        return_value={"ITUB3": fake},
    ):
        resultado = salvar_fundamentos_db(["ITUB3"])

    assert resultado["linhas_inseridas"] == 1  # só PVP
    db = Session()
    rows = db.query(Fundamento).filter(Fundamento.ticker == "ITUB3").all()
    db.close()
    assert len(rows) == 1
    assert rows[0].indicador == "PVP"
    assert rows[0].valor == 2.34


def test_salvar_fundamentos_db_nao_apaga_valor_antigo_com_coleta_vazia(patch_session):
    Session = patch_session

    with patch(
        "carteira_clean_web.backend.engine.fundamentals_client.fetch_fundamentos_completos",
        return_value={"ITUB3": {"PVP": 2.34, "erro": None}},
    ):
        salvar_fundamentos_db(["ITUB3"])

    # 2ª coleta: yfinance falhou, tudo None — não deve mascarar o PVP anterior
    fake_vazio = {k: None for k in [
        "PL", "PVP", "ROE", "ROIC", "DY", "MARGEM_EBITDA",
        "DIV_LIQ_EBITDA", "MARGEM_LIQUIDA", "LPA", "VPA",
    ]}
    fake_vazio["erro"] = "Indisponível"
    with patch(
        "carteira_clean_web.backend.engine.fundamentals_client.fetch_fundamentos_completos",
        return_value={"ITUB3": fake_vazio},
    ):
        resultado = salvar_fundamentos_db(["ITUB3"])

    assert resultado["linhas_inseridas"] == 0
    db = Session()
    rows = db.query(Fundamento).filter(Fundamento.ticker == "ITUB3", Fundamento.indicador == "PVP").all()
    db.close()
    assert len(rows) == 1  # a linha antiga com valor real continua lá, intacta
    assert rows[0].valor == 2.34
