"""
tests/test_proventos_brapi.py — Proventos via brapi dividends=true
(Fase 4.1 da fatia "Ingestão de dados").

Casos:
  1) _extrair_cash_dividends: label com "JUROS"/"JCP" vira JCP, resto DIVIDENDO.
  2) _extrair_stock_dividends: label com "SPLIT" vira DESDOBRAMENTO, resto BONIFICACAO.
  3) coletar_proventos: idempotente (2ª coleta não duplica), erro em 1
     ticker não derruba os demais, só apaga linhas fonte='brapi' do próprio
     ticker (não mexe em linhas yfinance do mesmo ticker).

Rodar:
    pytest tests/test_proventos_brapi.py -v
"""
import sys
from pathlib import Path
from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import proventos_brapi as pb
from carteira_clean_web.backend.db.models import EventoCorporativo, JobRun


# ─── 1-2: extração ───────────────────────────────────────────────────────────

def test_extrair_cash_dividends_classifica_jcp_vs_dividendo():
    dados = {"cashDividends": [
        {"paymentDate": "2026-06-10", "label": "JUROS SOBRE CAPITAL PROPRIO"},
        {"paymentDate": "2026-05-10", "label": "DIVIDEND"},
        {"paymentDate": None, "label": "SEM DATA — deve ser ignorado"},
    ]}
    out = pb._extrair_cash_dividends(dados)
    assert len(out) == 2
    assert out[0] == {"data_evento": date(2026, 6, 10), "tipo": "JCP", "descricao": "JUROS SOBRE CAPITAL PROPRIO"}
    assert out[1]["tipo"] == "DIVIDENDO"


def test_extrair_stock_dividends_classifica_split_vs_bonificacao():
    dados = {"stockDividends": [
        {"approvedOn": "2026-03-01", "label": "STOCK SPLIT 2:1"},
        {"approvedOn": "2026-02-01", "label": "BONUS SHARES"},
    ]}
    out = pb._extrair_stock_dividends(dados)
    assert out[0]["tipo"] == "DESDOBRAMENTO"
    assert out[1]["tipo"] == "BONIFICACAO"


# ─── 3: coletar_proventos ────────────────────────────────────────────────────

@pytest.fixture
def patch_pb_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'pb.db'}", connect_args={"check_same_thread": False})
    EventoCorporativo.metadata.create_all(engine, tables=[EventoCorporativo.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.proventos_brapi.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def test_coletar_proventos_idempotente(patch_pb_session):
    Session = patch_pb_session
    resp = {"results": [{"dividendsData": {"cashDividends": [{"paymentDate": "2026-06-10", "label": "DIVIDEND"}]}}]}
    with patch("carteira_clean_web.backend.engine.proventos_brapi.brapi_client.get", return_value=resp):
        pb.coletar_proventos(["ITUB3"])
        pb.coletar_proventos(["ITUB3"])  # 2ª coleta — não deve duplicar

    db = Session()
    rows = db.query(EventoCorporativo).filter(EventoCorporativo.ticker == "ITUB3").all()
    db.close()
    assert len(rows) == 1
    assert rows[0].fonte == "brapi"


def test_coletar_proventos_nao_apaga_linhas_yfinance(patch_pb_session):
    Session = patch_pb_session
    db = Session()
    db.add(EventoCorporativo(
        ticker="ITUB3", tipo="EARNINGS_DATE", data_evento=date(2026, 8, 1),
        descricao="x", fonte="yfinance", fetched_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()

    resp = {"results": [{"dividendsData": {"cashDividends": [{"paymentDate": "2026-06-10", "label": "DIVIDEND"}]}}]}
    with patch("carteira_clean_web.backend.engine.proventos_brapi.brapi_client.get", return_value=resp):
        pb.coletar_proventos(["ITUB3"])

    db = Session()
    fontes = {r.fonte for r in db.query(EventoCorporativo).filter(EventoCorporativo.ticker == "ITUB3").all()}
    db.close()
    assert fontes == {"yfinance", "brapi"}  # yfinance preservado, brapi adicionado


def test_coletar_proventos_erro_em_1_ticker_nao_derruba_outros(patch_pb_session):
    def _get(path, params):
        if "QUEBRA11" in path:
            raise ConnectionError("brapi fora do ar")
        return {"results": [{"dividendsData": {"cashDividends": [{"paymentDate": "2026-06-10", "label": "DIVIDEND"}]}}]}

    with patch("carteira_clean_web.backend.engine.proventos_brapi.brapi_client.get", side_effect=_get):
        resultado = pb.coletar_proventos(["ITUB3", "QUEBRA11"])

    assert resultado["linhas_invalidas"] == 1
    assert resultado["linhas_gravadas"] == 1
