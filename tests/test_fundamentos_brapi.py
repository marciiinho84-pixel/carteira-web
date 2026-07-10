"""
tests/test_fundamentos_brapi.py — Fundamentos de peers via brapi
(Fase 3 da fatia "Ingestão de dados").

Casos:
  1) _extrair_brapi: achata defaultKeyStatistics+financialData, converte
     frações (<=1.0) para percentual só nos indicadores que são percentuais,
     não mexe em PL/PVP/EV_EBITDA (múltiplos, não percentuais).
  2) _buscar_ticker: results vazio → None.
  3) coletar_fundamentos_peers: grava fonte='brapi', append-only (2 coletas
     não sobrescrevem, geram 2×N linhas), ticker com erro conta como
     inválido sem derrubar os demais.

Rodar:
    pytest tests/test_fundamentos_brapi.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import fundamentos_brapi as fb
from carteira_clean_web.backend.db.models import Fundamento, JobRun


# ─── 1: _extrair_brapi ──────────────────────────────────────────────────────

def test_extrair_brapi_converte_fracao_para_percentual():
    resultado = {
        "defaultKeyStatistics": {"trailingPE": 8.5, "priceToBook": 1.2, "enterpriseToEbitda": 5.1},
        "financialData": {"returnOnEquity": 0.184, "profitMargins": 0.22, "ebitdaMargins": 0.31},
    }
    out = fb._extrair_brapi(resultado)
    assert out["PL"] == 8.5
    assert out["PVP"] == 1.2
    assert out["EV_EBITDA"] == 5.1
    assert out["ROE"] == 18.4
    assert out["MARGEM_LIQUIDA"] == 22.0
    assert out["MARGEM_EBITDA"] == 31.0
    assert out["DY"] is None  # não presente no fake


def test_extrair_brapi_nao_dobra_percentual_ja_grande():
    resultado = {
        "defaultKeyStatistics": {},
        "financialData": {"returnOnEquity": 18.4},  # já em percentual (>1.0)
    }
    out = fb._extrair_brapi(resultado)
    assert out["ROE"] == 18.4  # não multiplicado de novo


def test_extrair_brapi_ausente_e_none():
    assert fb._extrair_brapi({}) == {k: None for k in fb._CANDIDATOS}


# ─── 2: _buscar_ticker ───────────────────────────────────────────────────────

def test_buscar_ticker_sem_resultados_retorna_none():
    with patch(
        "carteira_clean_web.backend.engine.fundamentos_brapi.brapi_client.get",
        return_value={"results": []},
    ):
        assert fb._buscar_ticker("XPTO11") is None


def test_buscar_ticker_usa_primeiro_resultado():
    with patch(
        "carteira_clean_web.backend.engine.fundamentos_brapi.brapi_client.get",
        return_value={"results": [{"defaultKeyStatistics": {"trailingPE": 10.0}, "financialData": {}}]},
    ):
        out = fb._buscar_ticker("PETR4")
    assert out["PL"] == 10.0


# ─── 3: coletar_fundamentos_peers ────────────────────────────────────────────

@pytest.fixture
def patch_fb_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fb.db'}", connect_args={"check_same_thread": False})
    Fundamento.metadata.create_all(engine, tables=[Fundamento.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.fundamentos_brapi.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def test_coletar_fundamentos_peers_grava_fonte_brapi(patch_fb_session):
    Session = patch_fb_session
    with patch.object(fb, "_buscar_ticker", return_value={"PL": 8.5, "PVP": None}):
        resultado = fb.coletar_fundamentos_peers(["ITUB3"])

    assert resultado["linhas_gravadas"] == 2  # PL + PVP (mesmo com valor None)
    db = Session()
    rows = db.query(Fundamento).filter(Fundamento.ticker == "ITUB3").all()
    assert all(r.fonte == "brapi" for r in rows)
    db.close()


def test_coletar_fundamentos_peers_e_append_only(patch_fb_session):
    with patch.object(fb, "_buscar_ticker", return_value={"PL": 8.5}):
        fb.coletar_fundamentos_peers(["ITUB3"])
        fb.coletar_fundamentos_peers(["ITUB3"])  # 2ª coleta — não sobrescreve

    Session = patch_fb_session
    db = Session()
    rows = db.query(Fundamento).filter(Fundamento.ticker == "ITUB3").all()
    db.close()
    assert len(rows) == 2  # 1 linha por coleta — append-only, não upsert


def test_coletar_fundamentos_peers_erro_em_1_ticker_nao_derruba_outros(patch_fb_session):
    def _fake(ticker):
        if ticker == "QUEBRA11":
            raise ConnectionError("brapi fora do ar")
        return {"PL": 8.5}

    with patch.object(fb, "_buscar_ticker", side_effect=_fake):
        resultado = fb.coletar_fundamentos_peers(["ITUB3", "QUEBRA11"])

    assert resultado["linhas_invalidas"] == 1
    assert resultado["linhas_gravadas"] == 1
