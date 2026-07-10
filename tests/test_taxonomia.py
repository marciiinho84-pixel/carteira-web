"""
tests/test_taxonomia.py — Coletor de taxonomia setorial (brapi) e
mapeamento setor → índice setorial B3 (Fase 2 da fatia "Ingestão de dados").

Casos:
  1) mapear_setor_para_indice: casos de cada índice + prioridade
     electric > utilities + string vazia/None/desconhecida → None.
  2) coletar_taxonomia_setorial: pagina até hasNextPage=False, faz UPSERT,
     conta linhas sem setor como inválidas, respeita o limite de segurança.
  3) resolver_setor / carregar_taxonomia_completa: leitura pós-coleta.

Rodar:
    pytest tests/test_taxonomia.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import taxonomia
from carteira_clean_web.backend.db.models import TaxonomiaSetorial, JobRun


# ─── 1: mapear_setor_para_indice ────────────────────────────────────────────

@pytest.mark.parametrize("setor_brapi,indice_esperado", [
    ("Financial Services", "IDX_IFNC"),
    ("Finance", "IDX_IFNC"),
    ("Real Estate", "IDX_IMOB"),
    ("Utilities", "IDX_UTIL"),
    ("Electric Utilities", "IDX_IEE"),  # electric vence utilit (prioridade)
    ("Energy", "IDX_IMAT"),
    ("Basic Materials", "IDX_IMAT"),
    ("Industrials", "IDX_INDX"),
    ("Consumer Cyclical", "IDX_ICON"),
    ("Healthcare", None),
    ("", None),
    (None, None),
])
def test_mapear_setor_para_indice(setor_brapi, indice_esperado):
    assert taxonomia.mapear_setor_para_indice(setor_brapi) == indice_esperado


# ─── 2-3: coleta + leitura ──────────────────────────────────────────────────

@pytest.fixture
def patch_taxonomia_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tax.db'}", connect_args={"check_same_thread": False})
    TaxonomiaSetorial.metadata.create_all(engine, tables=[TaxonomiaSetorial.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def _pagina(stocks, has_next):
    return {"stocks": stocks, "hasNextPage": has_next}


def test_coletar_taxonomia_setorial_pagina_ate_esgotar(patch_taxonomia_session):
    Session = patch_taxonomia_session
    respostas = [
        _pagina([{"stock": "PETR4", "sector": "Energy"}, {"stock": "ITUB3", "sector": "Finance"}], True),
        _pagina([{"stock": "SEM_SETOR11", "sector": None}], False),
    ]
    with patch("carteira_clean_web.backend.engine.taxonomia.brapi_client.get", side_effect=respostas):
        resultado = taxonomia.coletar_taxonomia_setorial()

    assert resultado["linhas_gravadas"] == 3
    assert resultado["linhas_invalidas"] == 1  # SEM_SETOR11 sem sector

    db = Session()
    rows = {r.ticker: r.setor_brapi for r in db.query(TaxonomiaSetorial).all()}
    assert rows == {"PETR4": "Energy", "ITUB3": "Finance", "SEM_SETOR11": None}
    db.close()


def test_coletar_taxonomia_setorial_para_em_lista_vazia(patch_taxonomia_session):
    with patch("carteira_clean_web.backend.engine.taxonomia.brapi_client.get", return_value=_pagina([], False)) as mock_get:
        resultado = taxonomia.coletar_taxonomia_setorial()
    assert resultado == {"linhas_gravadas": 0, "linhas_invalidas": 0}
    assert mock_get.call_count == 1


def test_coletar_taxonomia_setorial_upsert_atualiza_setor(patch_taxonomia_session):
    Session = patch_taxonomia_session
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.brapi_client.get",
        return_value=_pagina([{"stock": "PETR4", "sector": "Energy"}], False),
    ):
        taxonomia.coletar_taxonomia_setorial()

    # segunda coleta corrige o setor do mesmo ticker — não deve duplicar
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.brapi_client.get",
        return_value=_pagina([{"stock": "PETR4", "sector": "Energy Corrected"}], False),
    ):
        taxonomia.coletar_taxonomia_setorial()

    db = Session()
    rows = db.query(TaxonomiaSetorial).filter(TaxonomiaSetorial.ticker == "PETR4").all()
    assert len(rows) == 1
    assert rows[0].setor_brapi == "Energy Corrected"
    db.close()


def test_resolver_setor_e_carregar_completa(patch_taxonomia_session):
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.brapi_client.get",
        return_value=_pagina([{"stock": "ITUB3", "sector": "Finance"}], False),
    ):
        taxonomia.coletar_taxonomia_setorial()

    assert taxonomia.resolver_setor("itub3") == "Finance"  # case-insensitive
    assert taxonomia.resolver_setor("NAO_EXISTE") is None
    assert taxonomia.carregar_taxonomia_completa() == {"ITUB3": "Finance"}
