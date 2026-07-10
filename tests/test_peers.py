"""
tests/test_peers.py — Universo de peers (Fase 3 da fatia "Ingestão de dados").

Casos:
  1) definir_universo_peers: carteira ∪ top-N por setor, sem duplicar
     ticker que já está na carteira; falha de 1 setor não derruba os outros.
  2) carregar_universo_peers: leitura pós-coleta.
  3) peers_do_mesmo_setor: agrupa por índice mapeado (mesmo índice —
     tickers com setor_brapi textualmente diferente mas mesmo índice
     ainda contam como peers), exclui o próprio ticker, [] sem taxonomia.

Rodar:
    pytest tests/test_peers.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import peers
from carteira_clean_web.backend.db.models import UniversoPeer, JobRun, TaxonomiaSetorial


@pytest.fixture
def patch_peers_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'peers.db'}", connect_args={"check_same_thread": False})
    UniversoPeer.metadata.create_all(engine, tables=[UniversoPeer.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.peers.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def _lista(stocks):
    return {"stocks": stocks}


def test_definir_universo_peers_uniao_sem_duplicar(patch_peers_session):
    Session = patch_peers_session
    taxonomia_map = {"ITUB3": "Finance", "PETR4": "Energy"}
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.carregar_taxonomia_completa",
        return_value=taxonomia_map,
    ), patch(
        "carteira_clean_web.backend.engine.peers.brapi_client.get",
        side_effect=lambda path, params: _lista(
            [{"stock": "ITUB3"}, {"stock": "BBDC4"}, {"stock": "SANB11"}]
            if params.get("sector") == "Finance"
            else [{"stock": "PRIO3"}, {"stock": "PETR4"}]
        ),
    ):
        resultado = peers.definir_universo_peers(["ITUB3", "PETR4"])

    assert resultado["linhas_invalidas"] == 0
    db = Session()
    linhas = {r.ticker: r.motivo for r in db.query(UniversoPeer).all()}
    db.close()
    assert linhas["ITUB3"] == "carteira"       # carteira vence sobre peer_setor
    assert linhas["PETR4"] == "carteira"
    assert linhas["BBDC4"] == "peer_setor:Finance"
    assert linhas["SANB11"] == "peer_setor:Finance"
    assert linhas["PRIO3"] == "peer_setor:Energy"
    assert len(linhas) == 5  # sem duplicar ITUB3/PETR4 que voltaram na lista de peers


def test_definir_universo_peers_falha_de_um_setor_nao_derruba_outros(patch_peers_session):
    def _get(path, params):
        if params.get("sector") == "Finance":
            raise ConnectionError("brapi fora do ar")
        return _lista([{"stock": "PRIO3"}])

    with patch(
        "carteira_clean_web.backend.engine.taxonomia.carregar_taxonomia_completa",
        return_value={"ITUB3": "Finance", "PETR4": "Energy"},
    ), patch("carteira_clean_web.backend.engine.peers.brapi_client.get", side_effect=_get):
        resultado = peers.definir_universo_peers(["ITUB3", "PETR4"])

    assert resultado["linhas_invalidas"] == 1
    assert "PRIO3" in peers.carregar_universo_peers()


def test_carregar_universo_peers(patch_peers_session):
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.carregar_taxonomia_completa",
        return_value={},
    ):
        peers.definir_universo_peers(["ITUB3"])
    assert peers.carregar_universo_peers() == ["ITUB3"]


def test_peers_do_mesmo_setor_agrupa_por_indice_mapeado():
    mapa = {
        "ITUB3": "Financial Services",
        "BBDC4": "Finance",       # texto diferente, mesmo índice (IFNC)
        "PETR4": "Energy",        # índice diferente (IMAT)
        "SEMSETOR11": None,
    }
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.carregar_taxonomia_completa",
        return_value=mapa,
    ):
        resultado = peers.peers_do_mesmo_setor("ITUB3")
    assert set(resultado) == {"BBDC4"}
    assert "ITUB3" not in resultado


def test_peers_do_mesmo_setor_sem_taxonomia_retorna_vazio():
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.carregar_taxonomia_completa",
        return_value={"XPTO11": None},
    ):
        assert peers.peers_do_mesmo_setor("XPTO11") == []
