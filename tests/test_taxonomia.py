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
from carteira_clean_web.backend.db.models import TaxonomiaSetorial, TaxonomiaOverride, JobRun


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
    TaxonomiaSetorial.metadata.create_all(
        engine, tables=[TaxonomiaSetorial.__table__, JobRun.__table__, TaxonomiaOverride.__table__]
    )
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


# ─── 4: override manual de setor ────────────────────────────────────────────

def test_adicionar_override_e_carregar(patch_taxonomia_session):
    taxonomia.adicionar_override("ALOS3", "Shopping Centers / Imobiliário", "brapi classificou como Finance")
    assert taxonomia.carregar_overrides() == {"ALOS3": "Shopping Centers / Imobiliário"}


def test_adicionar_override_atualiza_existente(patch_taxonomia_session):
    taxonomia.adicionar_override("ALOS3", "Setor errado", "primeira tentativa")
    taxonomia.adicionar_override("ALOS3", "Shopping Centers / Imobiliário", "correção")
    overrides = taxonomia.carregar_overrides()
    assert overrides == {"ALOS3": "Shopping Centers / Imobiliário"}  # não duplicou


def test_carregar_setores_efetivos_override_tem_prioridade(patch_taxonomia_session):
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.brapi_client.get",
        return_value=_pagina([{"stock": "ALOS3", "sector": "Finance"}, {"stock": "BBDC4", "sector": "Finance"}], False),
    ):
        taxonomia.coletar_taxonomia_setorial()

    taxonomia.adicionar_override("ALOS3", "Shopping Centers / Imobiliário")

    efetivos = taxonomia.carregar_setores_efetivos()
    assert efetivos["ALOS3"] == "Shopping Centers / Imobiliário"  # override venceu
    assert efetivos["BBDC4"] == "Finance"  # sem override, mantém o setor_brapi


def test_carregar_taxonomia_completa_nao_e_afetada_por_override(patch_taxonomia_session):
    """carregar_taxonomia_completa() precisa continuar retornando o setor
    bruto da brapi (usado por definir_universo_peers pra montar a query de
    descoberta de peers, que precisa do vocabulário original da brapi)."""
    with patch(
        "carteira_clean_web.backend.engine.taxonomia.brapi_client.get",
        return_value=_pagina([{"stock": "ALOS3", "sector": "Finance"}], False),
    ):
        taxonomia.coletar_taxonomia_setorial()

    taxonomia.adicionar_override("ALOS3", "Shopping Centers / Imobiliário")

    assert taxonomia.carregar_taxonomia_completa() == {"ALOS3": "Finance"}


@pytest.mark.parametrize("setor_correto,indice_esperado", [
    ("Shopping Centers / Imobiliário", "IDX_IMOB"),
    ("Construção Civil", "IDX_IMOB"),
])
def test_override_em_portugues_mapeia_para_indice(setor_correto, indice_esperado):
    assert taxonomia.mapear_setor_para_indice(setor_correto) == indice_esperado
