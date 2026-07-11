"""
tests/test_contexto_setorial.py — fn_contexto_setorial resolvendo setor via
taxonomia_setorial (brapi), não mais pelo campo livre ativos.setor
(Fase 2 da fatia "Ingestão de dados").

Casos:
  1) setor="todos": agrupa carteira pelos índices resolvidos via taxonomia
     e inclui ativos sem taxonomia no bucket residual "outros_sem_taxonomia".
  2) setor="Bancos" (nome amigável) resolve para IDX_IFNC e retorna os
     ativos daquele índice, não vazio.
  3) setor="IFNC" (código do índice) funciona igual.
  4) Cache vazio → erro claro, sem exceção.

Rodar:
    pytest tests/test_contexto_setorial.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.posicoes import Posicao
from carteira_clean_web.backend.mcp.tools import portfolio


def _estado_fake():
    return {
        "posicoes": {
            "ITUB3": Posicao(qtd=100, custo_total=3000),
            "PETR4": Posicao(qtd=50, custo_total=2000),
            # qtd>0 só p/ passar no filtro de posição ativa da tool (mesmo
            # filtro de hoje, não alterado nesta fatia); custo_total é o que
            # importaria de verdade para um AGREGADO_PRIVADO real.
            "CAIXA LCI": Posicao(qtd=1, custo_total=26000),  # sem taxonomia (não listado)
        },
        "ativos": {
            "ITUB3": {"setor": "Bancos Tradicionais"},
            "PETR4": {"setor": "Petróleo & Gás"},
            "CAIXA LCI": {"setor": None},
        },
    }


@pytest.fixture
def mocks():
    with patch.object(portfolio.engine_cache, "esta_calculado", return_value=True), \
         patch.object(portfolio.engine_cache, "get_estado", return_value=_estado_fake()), \
         patch(
             "carteira_clean_web.backend.engine.taxonomia.carregar_setores_efetivos",
             return_value={"ITUB3": "Financial Services", "PETR4": "Energy"},
         ), \
         patch(
             "carteira_clean_web.backend.engine.precos.carregar_indices_setoriais_da_tabela",
             return_value={"IDX_IFNC": {}, "IDX_IMAT": {}},
         ), \
         patch("carteira_clean_web.backend.engine.macro_client.ler_macro", return_value={}):
        yield


def test_contexto_setorial_todos_agrupa_por_indice(mocks):
    resultado = portfolio.fn_contexto_setorial("todos")
    setores = {s["indice"]: s for s in resultado["setores"]}
    assert "IFNC" in setores
    assert setores["IFNC"]["ativos_carteira"] == ["ITUB3"]
    assert "IMAT" in setores
    assert setores["IMAT"]["ativos_carteira"] == ["PETR4"]
    # CAIXA LCI não tem taxonomia (não listado em bolsa) → bucket residual
    residuais = {o["ticker"] for o in resultado["outros_sem_taxonomia"]}
    assert "CAIXA LCI" in residuais


def test_contexto_setorial_nome_amigavel_bancos(mocks):
    resultado = portfolio.fn_contexto_setorial("Bancos")
    assert len(resultado["setores"]) == 1
    assert resultado["setores"][0]["indice"] == "IFNC"
    assert resultado["setores"][0]["ativos_carteira"] == ["ITUB3"]


def test_contexto_setorial_codigo_indice(mocks):
    resultado = portfolio.fn_contexto_setorial("IFNC")
    assert len(resultado["setores"]) == 1
    assert resultado["setores"][0]["indice"] == "IFNC"


def test_contexto_setorial_cache_vazio():
    with patch.object(portfolio.engine_cache, "esta_calculado", return_value=False), \
         patch.object(portfolio.engine_cache, "carregar_disco"):
        resultado = portfolio.fn_contexto_setorial("todos")
    assert "erro" in resultado
