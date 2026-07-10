"""
tests/test_estado_abertura.py — Estado de abertura (eventos pré-DATA_INICIO).

Bug original: CAIXA LCI tinha 2 COMPRA reais em 2025 (antes de DATA_INICIO),
sem SALDO_INICIAL. calc_evolucao_diaria só percorria bdate_range(DATA_INICIO,
hoje) e posicoes era um defaultdict só populado quando um evento tocava o
ticker — a posição ficava invisível (contribuindo R$0) até seu primeiro
evento DENTRO da janela, e "aparecia" de uma vez, lido como retorno de TWR.

Correção: replay de todo o histórico anterior a DATA_INICIO constrói o
ESTADO DE ABERTURA das posições (qtd/custo_total). Regra (GIPS): afeta só
a posição, nunca o caixa — saldo_caixa de abertura é sempre 0.0, eventos
pré-janela nunca aparecem como fluxo/retorno na série visível.

Rodar:
    pytest tests/test_estado_abertura.py -v
"""

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.twr import calc_evolucao_diaria, calc_twr_e_benchmarks

D_PRE1 = date(2025, 9, 19)   # evento pré-janela 1
D_PRE2 = date(2025, 11, 26)  # evento pré-janela 2
D0 = date(2026, 1, 2)        # sexta — DATA_INICIO
D1 = date(2026, 1, 5)        # segunda
D_FIM = date(2026, 1, 9)     # sexta


def _tol(a, b, tol=0.01):
    return abs(a - b) <= tol


ATIVOS = {
    "CAIXA LCI": {"familia": "Letra de Crédito", "composite": "Gerida"},
    "PETR4": {"familia": "Ação BR", "composite": "Gerida"},
    "CAIXA FIC FUNC": {"familia": "Fundo CP", "composite": "Gerida"},
}


# ── Teste 1: AGREGADO_PRIVADO com evento pré-janela aparece desde o dia 1 ──

def test_agregado_privado_com_evento_pre_janela_aparece_desde_dia1():
    eventos = [
        {"data": D_PRE1, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 10000.0, "obs": "CDI:94.0", "linha": 1},
        {"data": D_PRE2, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 16000.0, "obs": "CDI:92.75", "linha": 2},
    ]
    # Curva de preço contínua desde antes da janela até D_FIM (como a curva
    # CDI real, que sempre teve dado — o bug não era falta de preço).
    precos_man = {"CAIXA LCI": {D0: 26585.87, D1: 26599.54, D_FIM: 26654.27}}

    df = calc_evolucao_diaria(eventos, ATIVOS, {}, precos_man, D_FIM)

    row_d0 = df[df["data"] == D0].iloc[0]
    assert _tol(row_d0["patrimonio_gerida"], 26585.87), (
        f"CAIXA LCI deveria aparecer com valor da curva já no 1º dia da série, "
        f"patrimonio_gerida foi {row_d0['patrimonio_gerida']} (esperado 26585.87)"
    )


# ── Teste 2: evento pré-janela nunca vira fluxo/retorno visível ────────────

def test_evento_pre_janela_nao_vira_fluxo_nem_retorno():
    eventos = [
        {"data": D_PRE1, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 10000.0, "obs": "CDI:94.0", "linha": 1},
        {"data": D_PRE2, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 16000.0, "obs": "CDI:92.75", "linha": 2},
    ]
    precos_man = {"CAIXA LCI": {D0: 26585.87, D1: 26599.54, D_FIM: 26654.27}}

    df = calc_evolucao_diaria(eventos, ATIVOS, {}, precos_man, D_FIM)
    df = calc_twr_e_benchmarks(df, eventos, [], ATIVOS)

    row_d0 = df[df["data"] == D0].iloc[0]
    assert _tol(row_d0["fluxo_gerida"], 0.0), "eventos pré-janela nunca podem virar fluxo_gerida"
    assert _tol(row_d0["twr_gerida"], 0.0), "primeiro dia da série sempre tem twr_gerida=0 (sem retorno anterior)"

    # Entre D0 e D1 a curva sobe suavemente (26585.87 -> 26599.54) — isso É
    # retorno legítimo (movimento de mercado dentro da janela), diferente do
    # "salto" que o bug original produzia.
    row_d1 = df[df["data"] == D1].iloc[0]
    ret_d1 = row_d1["twr_gerida"] - row_d0["twr_gerida"]
    assert ret_d1 > 0, "variação suave da curva dentro da janela deve continuar contando como retorno"
    assert ret_d1 < 0.01, f"retorno do dia deveria ser pequeno (~0,05%), foi {ret_d1*100:.2f}%"


# ── Teste 3: eventos pré-janela nunca afetam saldo_caixa (regra corrigida) ──

def test_evento_pre_janela_nao_afeta_saldo_caixa():
    eventos = [
        {"data": D_PRE1, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 10000.0, "obs": "CDI:94.0", "linha": 1},
        {"data": D_PRE2, "ativo": "CAIXA LCI", "tipo": "COMPRA",
         "qtd": None, "valor": 16000.0, "obs": "CDI:92.75", "linha": 2},
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": "", "linha": 3},
    ]
    precos_man = {"CAIXA LCI": {D0: 26585.87, D1: 26599.54, D_FIM: 26654.27}}

    df = calc_evolucao_diaria(eventos, ATIVOS, {}, precos_man, D_FIM)

    for _, row in df.iterrows():
        assert _tol(row["caixa"], 0.0), (
            f"saldo_caixa não deveria ser afetado por eventos pré-janela (COMPRA "
            f"debitaria -26000 se a regra estivesse errada), foi {row['caixa']} em {row['data']}"
        )


# ── Teste 4: posição de ativo COTIZADO_PUBLICO/COTIZADO_PRIVADO com evento
#    pré-janela constrói o estado de abertura corretamente (qtd/custo) ──────

def test_qtd_custo_abertura_de_ativo_com_evento_pre_janela():
    eventos = [
        {"data": D_PRE1, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 50.0, "valor": 2500.0, "obs": "", "linha": 1},
        {"data": D_PRE2, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 50.0, "valor": 2600.0, "obs": "", "linha": 2},
    ]
    precos_pub = {"PETR4": {D0: 51.0, D1: 51.0, D_FIM: 51.0}}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)

    row_d0 = df[df["data"] == D0].iloc[0]
    # qtd de abertura = 100 (50+50), custo_total = 5100 (2500+2600);
    # valorizado a 51/ação = 100*51 = 5100 no dia 1 da série.
    assert _tol(row_d0["patrimonio_gerida"], 5100.0), (
        f"posição com histórico pré-janela deveria valer 100 ações x R$51 = 5100 "
        f"já no 1º dia, foi {row_d0['patrimonio_gerida']}"
    )
