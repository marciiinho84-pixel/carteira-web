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


def _http_error_modulos_indisponiveis():
    import requests
    resp = requests.Response()
    resp.status_code = 403
    resp._content = b'{"error":true,"code":"MODULES_NOT_AVAILABLE","message":"..."}'
    return requests.exceptions.HTTPError(response=resp)


def test_buscar_ticker_cai_pro_quote_basico_quando_modulos_indisponiveis():
    """Validado ao vivo: plano gratuito da brapi só libera defaultKeyStatistics/
    financialData pra poucos tickers de demo — qualquer outro dá 403
    MODULES_NOT_AVAILABLE. Nesse caso, cai pra chamada sem `modules`."""
    chamadas = []

    def _get(path, params=None):
        chamadas.append(params)
        if params and "modules" in params:
            raise _http_error_modulos_indisponiveis()
        return {"results": [{"priceEarnings": 8.5, "earningsPerShare": 2.1}]}

    with patch("carteira_clean_web.backend.engine.fundamentos_brapi.brapi_client.get", side_effect=_get):
        out = fb._buscar_ticker("DIRR3")

    assert len(chamadas) == 2  # 1ª com modules (falhou), 2ª sem
    assert out["PL"] == 8.5
    assert out["LPA"] == 2.1
    assert out["PVP"] is None  # não disponível no fallback básico


def test_buscar_ticker_403_generico_nao_cai_no_fallback():
    """Um 403 que NÃO seja MODULES_NOT_AVAILABLE (ex.: token inválido) deve
    propagar normalmente — só o caso específico de módulo indisponível tem
    fallback."""
    resp = MagicMockResponse(403, b'{"error":true,"code":"INVALID_TOKEN"}')
    import requests

    def _get(path, params=None):
        raise requests.exceptions.HTTPError(response=resp)

    with patch("carteira_clean_web.backend.engine.fundamentos_brapi.brapi_client.get", side_effect=_get):
        try:
            fb._buscar_ticker("DIRR3")
            assert False, "deveria ter propagado o HTTPError"
        except requests.exceptions.HTTPError:
            pass


class MagicMockResponse:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self._content = content

    def json(self):
        import json
        return json.loads(self._content)


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
