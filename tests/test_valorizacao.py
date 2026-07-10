"""
tests/test_valorizacao.py — Golden master da unificação de valorização.

engine/valorizacao.py::valorizar_posicao foi extraído literalmente de
resultados.py::posicoes() (a fórmula canônica, "a tela"). Este teste
compara o resultado da função nova contra uma cópia congelada da fórmula
antiga (a mesma lógica que existia inline em ~9 lugares antes desta fatia)
— devem bater exatamente, para qualquer categoria de ticker.

Rodar:
    pytest tests/test_valorizacao.py -v
"""

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.posicoes import Posicao
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO
from carteira_clean_web.backend.engine.utils import preco_em
from carteira_clean_web.backend.engine.valorizacao import valorizar_posicao, determinar_preco_atual

D0 = date(2026, 1, 2)


def _formula_antiga(pos, tkr, ativos, precos_pub, precos_man, hoje):
    """Cópia congelada de resultados.py::posicoes() ANTES desta fatia —
    referência fixa, não deve mudar mesmo que valorizar_posicao mude."""
    info = ativos.get(tkr, {})
    familia = info.get("familia", "")

    _is_lci_lca = tkr.upper().startswith(("LCI-", "LCA-"))
    _is_agregado = familia in AGREGADO_PRIVADO or _is_lci_lca

    preco_atual = None
    if familia in COTIZADO_PUBLICO:
        preco_atual = preco_em(precos_pub.get(tkr, {}), hoje)
    if preco_atual is None:
        preco_atual = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)

    if _is_agregado:
        valor_atual = preco_atual if preco_atual else pos.custo_total
    else:
        valor_atual = pos.qtd * preco_atual if preco_atual else pos.custo_total

    return preco_atual, valor_atual


ATIVOS = {
    "PETR4": {"familia": "Ação BR", "composite": "Gerida"},
    "CAIXA LCI": {"familia": "Letra de Crédito", "composite": "Gerida"},
    "FUNDO_SEM_PRECO": {"familia": "Fundo CP", "composite": "Gerida"},
    # LCI-* sem familia cadastrada — testa o broadening por prefixo
}

CASOS = [
    # (ticker, qtd, custo_total, precos_pub, precos_man)
    ("PETR4", 100.0, 5000.0, {"PETR4": {D0: 51.0}}, {}),
    ("PETR4", 100.0, 5000.0, {}, {"PETR4": {D0: 49.0}}),
    ("PETR4", 100.0, 5000.0, {}, {}),
    ("CAIXA LCI", 0.0, 26000.0, {}, {"CAIXA LCI": {D0: 28360.95}}),
    ("CAIXA LCI", 0.0, 26000.0, {}, {}),
    ("LCI-TESTE", 0.0, 1000.0, {}, {"LCI-TESTE": {D0: 1050.0}}),
    ("FUNDO_SEM_PRECO", 0.0, 500.0, {}, {}),
    ("PETR4", 0.0, 0.0, {"PETR4": {D0: 51.0}}, {}),
]


@pytest.mark.parametrize("tkr,qtd,custo_total,precos_pub,precos_man", CASOS)
def test_valorizar_posicao_bate_com_formula_antiga(tkr, qtd, custo_total, precos_pub, precos_man):
    pos = Posicao(qtd=qtd, custo_total=custo_total)

    preco_esperado, valor_esperado = _formula_antiga(pos, tkr, ATIVOS, precos_pub, precos_man, D0)
    resultado = valorizar_posicao(pos, tkr, ATIVOS, precos_pub, precos_man, D0)

    assert resultado["preco_atual"] == preco_esperado
    assert resultado["valor_atual"] == valor_esperado


def test_broadening_lci_prefixo_sem_familia_cadastrada():
    pos = Posicao(qtd=0.0, custo_total=1000.0)
    resultado = valorizar_posicao(pos, "LCA-OUTRO", ATIVOS, {}, {"LCA-OUTRO": {D0: 1080.0}}, D0)
    assert resultado["is_agregado"] is True
    assert resultado["valor_atual"] == 1080.0


def test_determinar_preco_atual_isolado_bate_com_precos_publicos():
    precos_pub = {"PETR4": {D0: 51.0}}
    assert determinar_preco_atual("PETR4", "Ação BR", precos_pub, {}, D0) == 51.0


def test_determinar_preco_atual_fallback_manual():
    precos_man = {"PETR4": {D0: 49.0}}
    assert determinar_preco_atual("PETR4", "Ação BR", {}, precos_man, D0) == 49.0


def test_determinar_preco_atual_none_quando_sem_dado():
    assert determinar_preco_atual("PETR4", "Ação BR", {}, {}, D0) is None
