"""
tests/test_carteira_rv_liquidacao.py — Painel "Caixa e Liquidações (D+2)"
(GET /api/v1/carteira-rv), corrigindo dupla contagem achada em auditoria.

O caixa derivado credita/debita no dia do TRADE, não no dia da liquidação
— D+2/D+1 é só o aspecto legal/custodial. "Entrando"/"saindo" já estão
dentro de caixa_atual; somar de novo pra achar "saldo_projetado" duplicava
o valor de qualquer venda/compra ainda em liquidação.

Caso real que motivou a auditoria: VENDA D1EL34 R$2.300 em 09/07 (D+2 →
13/07). No dia da venda, caixa_atual pulou de X pra X+2.300 (creditado na
hora) — mas o painel ainda somava os mesmos R$2.300 como "entrando",
inflando o saldo projetado em +R$2.300 até a liquidação vencer.

Casos:
  1) saldo_projetado (topo) = caixa_atual - entrando_5d (não soma
     entrando de novo, não soma/subtrai saindo).
  2) saldo_projetado por linha (running) só cresce quando uma VENDA
     pendente liquida; COMPRA pendente não muda o disponível (o dinheiro
     já saiu de verdade no trade).
  3) reprodução do caso real: só a VENDA pendente, saldo_projetado do
     topo é exatamente caixa_atual - valor_da_venda (não caixa_atual +
     valor, como o bug antigo fazia).

Rodar:
    pytest tests/test_carteira_rv_liquidacao.py -v
"""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.api.routers import resultados
from carteira_clean_web.backend.engine.posicoes import Posicao


def _estado_fake(eventos, hoje, caixa_atual=1000.0):
    df_evo = pd.DataFrame([{"data": hoje, "caixa": caixa_atual}])
    return {
        "posicoes": {},
        "ativos": {
            "D1EL34": {"familia": "BDR", "composite": "Gerida"},
            "PETR4": {"familia": "Ação BR", "composite": "Gerida"},
        },
        "eventos": eventos,
        "precos_publicos": {},
        "precos_manuais": {},
        "hoje": hoje,
        "df_evo": df_evo,
    }


def _mock_cache(estado):
    return patch.multiple(
        resultados.engine_cache,
        esta_calculado=lambda: True,
        get_estado=lambda: estado,
    )


def test_saldo_projetado_nao_duplica_venda_pendente():
    """Reprodução do caso real: VENDA D1EL34 R$2.300, D+2 ainda não venceu.
    caixa_atual já reflete os +2.300 (creditados no trade) — saldo_projetado
    deve DESCONTAR esse valor (não disponível pra saque), não somar de novo."""
    hoje = date(2026, 7, 10)  # venda em 09/07, D+2 = 13/07 — ainda pendente
    eventos = [{
        "data": date(2026, 7, 9), "ativo": "D1EL34", "tipo": "VENDA",
        "qtd": 1.0, "preco": 2300.0, "valor": 2300.0, "obs": "", "linha": 1,
    }]
    estado = _estado_fake(eventos, hoje, caixa_atual=4136.76)

    with _mock_cache(estado):
        resultado = resultados.carteira_rv()

    assert resultado.entrando_5d == 2300.0
    assert resultado.saindo_5d == 0.0
    # ANTES do fix: 4136.76 + 2300 - 0 = 6436.76 (duplicava). Correto: desconta.
    assert resultado.saldo_projetado == pytest.approx(4136.76 - 2300.0)
    assert resultado.saldo_projetado == pytest.approx(1836.76)


def test_saldo_projetado_compra_pendente_nao_e_somada_de_volta():
    """COMPRA pendente: o dinheiro já saiu de verdade no trade (já fora de
    caixa_atual) — não deve ser subtraído de novo nem somado de volta."""
    hoje = date(2026, 7, 10)
    eventos = [{
        "data": date(2026, 7, 9), "ativo": "PETR4", "tipo": "COMPRA",
        "qtd": 10.0, "preco": 40.0, "valor": 400.0, "obs": "", "linha": 1,
    }]
    estado = _estado_fake(eventos, hoje, caixa_atual=1000.0)

    with _mock_cache(estado):
        resultado = resultados.carteira_rv()

    assert resultado.saindo_5d == 400.0
    assert resultado.entrando_5d == 0.0
    # Só desconta entrando (0) — compra pendente não mexe no disponível.
    assert resultado.saldo_projetado == pytest.approx(1000.0)


def test_saldo_projetado_por_linha_so_libera_quando_venda_liquida():
    """Running por linha: uma VENDA pendente que liquida libera o caixa
    (soma); uma COMPRA pendente na sequência não muda o disponível."""
    hoje = date(2026, 7, 10)
    eventos = [
        {"data": date(2026, 7, 9), "ativo": "D1EL34", "tipo": "VENDA",
         "qtd": 1.0, "preco": 2300.0, "valor": 2300.0, "obs": "", "linha": 1},
        {"data": date(2026, 7, 10), "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 10.0, "preco": 40.0, "valor": 400.0, "obs": "", "linha": 2},
    ]
    estado = _estado_fake(eventos, hoje, caixa_atual=4136.76)

    with _mock_cache(estado):
        resultado = resultados.carteira_rv()

    linhas = sorted(resultado.pendentes, key=lambda p: p["liquidacao"])
    disponivel_hoje = 4136.76 - 2300.0  # só a venda entra em entrando_5d
    # 1ª linha a liquidar é a venda (D+2 de 09/07 = 13/07) — libera 2300
    venda_linha = next(p for p in linhas if p["ativo"] == "D1EL34")
    assert venda_linha["saldo_projetado"] == pytest.approx(disponivel_hoje + 2300.0)
    # compra não muda o disponível na sua própria liquidação
    compra_linha = next(p for p in linhas if p["ativo"] == "PETR4")
    assert compra_linha["saldo_projetado"] == venda_linha["saldo_projetado"]


def test_sem_pendencias_saldo_projetado_igual_caixa_atual():
    estado = _estado_fake([], date(2026, 7, 10), caixa_atual=500.0)
    with _mock_cache(estado):
        resultado = resultados.carteira_rv()
    assert resultado.entrando_5d == 0.0
    assert resultado.saindo_5d == 0.0
    assert resultado.saldo_projetado == pytest.approx(500.0)
