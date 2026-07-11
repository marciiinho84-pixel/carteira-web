"""
tests/test_noticias_rss.py — Notícias via Google News RSS (Fase 5 da fatia
"Ingestão de dados").

Casos:
  1) _montar_query: usa nome da empresa quando disponível, só ticker senão.
  2) _extrair_fonte: entry.source.title, fallback pro sufixo " - Fonte" do
     título, None se nenhum dos dois.
  3) coletar_noticias_ticker: dedupe por título dentro do próprio feed.
  4) coletar_noticias: UPSERT (ticker+titulo) não duplica em 2ª coleta;
     ticker com erro não derruba os demais.
  5) ler_noticias: filtra por janela de dias e por lista de tickers.

Rodar:
    pytest tests/test_noticias_rss.py -v
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import noticias_rss as nr
from carteira_clean_web.backend.db.models import Noticia, JobRun


class _FakeFeed:
    def __init__(self, entries):
        self.entries = entries


# ─── 1-2: helpers ────────────────────────────────────────────────────────────

def test_montar_query_com_nome():
    assert nr._montar_query("ITUB3", "Itaú Unibanco") == '"Itaú Unibanco" OR ITUB3 when:2d'


def test_montar_query_sem_nome():
    assert nr._montar_query("ITUB3", None) == "ITUB3 when:2d"


def test_extrair_fonte_de_source_dict():
    entry = {"title": "Manchete", "source": {"title": "Valor Econômico"}}
    assert nr._extrair_fonte(entry) == "Valor Econômico"


def test_extrair_fonte_fallback_sufixo_titulo():
    entry = {"title": "Itaú anuncia resultado - InfoMoney"}
    assert nr._extrair_fonte(entry) == "InfoMoney"


def test_extrair_fonte_none_sem_pistas():
    entry = {"title": "Manchete sem fonte"}
    assert nr._extrair_fonte(entry) is None


# ─── 3: coletar_noticias_ticker (dedupe) ─────────────────────────────────────

def test_coletar_noticias_ticker_dedupe_por_titulo():
    parsed = time.strptime("2026-07-10", "%Y-%m-%d")
    entries = [
        {"title": "Mesma manchete", "link": "http://a", "published_parsed": parsed},
        {"title": "Mesma manchete", "link": "http://b", "published_parsed": parsed},  # duplicada
        {"title": "Outra manchete", "link": "http://c", "published_parsed": parsed},
    ]
    with patch.object(nr.taxonomia, "nome_empresa", return_value=None), \
         patch.object(nr, "_buscar_feed", return_value=_FakeFeed(entries)):
        out = nr.coletar_noticias_ticker("ITUB3")
    assert len(out) == 2
    assert {o["titulo"] for o in out} == {"Mesma manchete", "Outra manchete"}


# ─── 4-5: coletar_noticias + ler_noticias ────────────────────────────────────

@pytest.fixture
def patch_nr_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'nr.db'}", connect_args={"check_same_thread": False})
    Noticia.metadata.create_all(engine, tables=[Noticia.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.noticias_rss.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def test_coletar_noticias_upsert_nao_duplica(patch_nr_session):
    Session = patch_nr_session
    parsed = time.strptime("2026-07-10", "%Y-%m-%d")
    entries = [{"title": "Manchete única", "link": "http://a", "published_parsed": parsed}]
    with patch.object(nr.taxonomia, "nome_empresa", return_value=None), \
         patch.object(nr, "_buscar_feed", return_value=_FakeFeed(entries)):
        nr.coletar_noticias(["ITUB3"])
        nr.coletar_noticias(["ITUB3"])  # 2ª coleta — mesma notícia, não duplica

    db = Session()
    rows = db.query(Noticia).filter(Noticia.ticker == "ITUB3").all()
    db.close()
    assert len(rows) == 1


def test_coletar_noticias_erro_em_1_ticker_nao_derruba_outros(patch_nr_session):
    def _fake_buscar_feed(url):
        if "QUEBRA" in url:
            raise ConnectionError("RSS fora do ar")
        return _FakeFeed([{"title": "OK", "link": "http://a", "published_parsed": time.strptime("2026-07-10", "%Y-%m-%d")}])

    with patch.object(nr.taxonomia, "nome_empresa", return_value=None), \
         patch.object(nr, "_buscar_feed", side_effect=_fake_buscar_feed):
        resultado = nr.coletar_noticias(["ITUB3", "QUEBRA11"])

    assert resultado["linhas_invalidas"] == 1
    assert resultado["linhas_gravadas"] == 1


def test_ler_noticias_filtra_por_janela_e_tickers(patch_nr_session):
    Session = patch_nr_session
    agora = datetime.utcnow()
    db = Session()
    db.add(Noticia(ticker="ITUB3", titulo="Recente", fonte="X", url="http://a",
                    publicado_em=agora - timedelta(days=1), coletado_em=agora))
    db.add(Noticia(ticker="ITUB3", titulo="Antiga", fonte="X", url="http://b",
                    publicado_em=agora - timedelta(days=30), coletado_em=agora))
    db.add(Noticia(ticker="PETR4", titulo="De outro ticker", fonte="X", url="http://c",
                    publicado_em=agora - timedelta(days=1), coletado_em=agora))
    db.commit()
    db.close()

    resultado = nr.ler_noticias(tickers=["ITUB3"], dias=7)
    assert {r["titulo"] for r in resultado} == {"Recente"}
