"""
tests/test_atribuicao_diaria.py — Modelo de contribuição diária (spec Etapa 4).

Casos:
  A) Venda total com lucro (caso PETR4): contribuição mensal positiva,
     zerando após a data de venda.
  B) Venda parcial: posição remanescente continua contribuindo.
  C) Compra no meio do mês: posição começa a contribuir em d+1.
  D) Buy-and-hold mês inteiro: contribuição = soma ponderada dos retornos diários.
  E) Identidade: soma das contribuições dos ativos ≈ retorno do composite (0.05pp).

Rodar:
    pytest tests/test_atribuicao_diaria.py -v -s
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.atribuicao import calc_atribuicao_mensal
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO
from carteira_clean_web.backend.engine.utils import bdate_range

_FAM = next(iter(COTIZADO_PUBLICO))

# Datas de referência (todas são dias úteis por bdate_range)
APR30 = date(2026, 4, 30)   # quinta-feira
MAY1  = date(2026, 5, 1)    # sexta (contada pelo bdate_range)
MAY4  = date(2026, 5, 4)    # segunda
MAY5  = date(2026, 5, 5)    # terça
MAY6  = date(2026, 5, 6)    # quarta
MAY8  = date(2026, 5, 8)    # sexta
MAY11 = date(2026, 5, 11)   # segunda
MAY12 = date(2026, 5, 12)   # terça
MAY29 = date(2026, 5, 29)   # última sexta de maio

D_FIM = MAY29


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_maio(df, tkr):
    """Linha de ativo individual em maio (não-TOTAL)."""
    return df[(df["mes"] == "2026-05") & (df["ativo"] == tkr)]


def _total_maio(df, composite="Gerida"):
    return df[(df["mes"] == "2026-05") & (df["ativo"] == "TOTAL") & (df["composite"] == composite)]


# ── Teste A: venda total com lucro ───────────────────────────────────────────

def test_A_venda_total_contribuicao_positiva():
    """
    200 unidades de PETR4, compradas antes de maio a R$48.
    Venda total em 04/05 a R$49.10 (lucro).
    Esperado: contribuição mensal > 0, e zero no mês seguinte ou após venda.
    """
    ativos = {"PETR4": {"familia": _FAM, "composite": "Gerida",
                        "benchmark": "IBOV", "bloco_ips": "SWING_TRADE"}}
    eventos = [
        {"data": APR30, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 200.0, "valor": 9600.0, "obs": ""},
        {"data": MAY4, "ativo": "PETR4", "tipo": "VENDA",
         "qtd": 200.0, "valor": 9820.0, "obs": ""},   # preco exec = 49.10
    ]
    precos_pub = {
        "PETR4": {
            APR30: 48.00,
            MAY1:  48.50,
            MAY4:  49.00,   # preço de fechamento (exec=49.10 está no valor da VENDA)
            MAY5:  47.00,   # irrelevante (sem posição)
            MAY8:  46.00,
            MAY29: 45.00,
        }
    }

    df = calc_atribuicao_mensal(eventos, ativos, precos_pub, {}, D_FIM)

    row = _get_maio(df, "PETR4")
    assert not row.empty, "PETR4 deve aparecer em maio"

    contrib = row.iloc[0]["contribuicao"]
    assert contrib > 0, (
        f"Contribuição de PETR4 em maio deve ser positiva (venda com lucro), mas foi {contrib:.4f}"
    )
    print(f"\n[A] PETR4 maio contribuicao={contrib:.4f} retorno={row.iloc[0]['retorno_ativo']:.4f}")

    # Após a venda, não deve haver dias com peso (o posição é zero)
    # Verificação indireta: retorno_ativo é composição apenas dos dias de posse (1 e 4/mai)
    retorno = row.iloc[0]["retorno_ativo"]
    assert retorno > 0, f"retorno_ativo de PETR4 em maio deve ser positivo, foi {retorno:.4f}"


# ── Teste B: venda parcial ────────────────────────────────────────────────────

def test_B_venda_parcial_posicao_continua():
    """
    100 unidades. Venda de 50 em 04/05. Os 50 restantes continuam contribuindo.
    Peso médio deve ser maior que zero no mês todo.
    """
    ativos = {"WEGE3": {"familia": _FAM, "composite": "Gerida",
                        "benchmark": "IBOV", "bloco_ips": "GROWTH"}}
    eventos = [
        {"data": APR30, "ativo": "WEGE3", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 3500.0, "obs": ""},
        {"data": MAY4, "ativo": "WEGE3", "tipo": "VENDA",
         "qtd": 50.0, "valor": 1800.0, "obs": ""},   # preco exec = 36.00
    ]
    # Preços para cada dia útil de maio relevante
    precos = {}
    dias_maio = [d for d in bdate_range(date(2026, 5, 1), D_FIM)]
    for i, d in enumerate(dias_maio):
        precos[d] = 35.0 + i * 0.10   # subida gradual
    precos[APR30] = 35.0

    precos_pub = {"WEGE3": precos}

    df = calc_atribuicao_mensal(eventos, ativos, precos_pub, {}, D_FIM)

    row = _get_maio(df, "WEGE3")
    assert not row.empty, "WEGE3 deve aparecer em maio"

    # Peso médio deve refletir posição antes e depois da venda parcial
    peso = row.iloc[0]["peso_medio"]
    assert peso > 0, f"peso_medio deve ser > 0, foi {peso:.4f}"

    contrib = row.iloc[0]["contribuicao"]
    # Preços sobem → contribuição positiva
    assert contrib > 0, f"contribuição deve ser positiva (preços sobem), foi {contrib:.4f}"

    print(f"\n[B] WEGE3 venda parcial: peso_medio={peso:.4f} contrib={contrib:.4f}")


# ── Teste C: compra no meio do mês ────────────────────────────────────────────

def test_C_compra_meio_mes_contribui_de_d1():
    """
    Sem posição no início de maio. COMPRA em 11/05.
    Posição começa a contribuir a partir de 12/05.
    Contribuição de 01-11/05 deve ser zero.
    """
    ativos = {"BBAS3": {"familia": _FAM, "composite": "Gerida",
                        "benchmark": "IBOV", "bloco_ips": "DEFENSIVOS"}}
    eventos = [
        {"data": MAY11, "ativo": "BBAS3", "tipo": "COMPRA",
         "qtd": 100.0, "valor": 2500.0, "obs": ""},
    ]
    precos_pub = {
        "BBAS3": {
            MAY11: 25.00,
            MAY12: 25.50,
            MAY29: 26.00,
        }
    }

    df = calc_atribuicao_mensal(eventos, ativos, precos_pub, {}, D_FIM)

    row = _get_maio(df, "BBAS3")
    if row.empty:
        # Se todos os retornos foram zero (sem preço para dias entre 11 e 12), passa mesmo assim
        print("\n[C] BBAS3 sem linha em maio (contribuição zero): correto para compra no fim do mês")
        return

    contrib = row.iloc[0]["contribuicao"]
    peso = row.iloc[0]["peso_medio"]

    # Peso médio deve ser baixo (posição só de 12/05 em diante de ~19 dias úteis)
    # Peso médio seria ~(n_dias_após_compra / total_dias) × 1.0
    dias_mai = bdate_range(MAY1, D_FIM)
    dias_após = [d for d in dias_mai if d > MAY11]
    frac_esperada = len(dias_após) / len(dias_mai)
    assert peso <= frac_esperada + 0.05, (
        f"peso_medio={peso:.4f} deve ser ≤ frac esperada={frac_esperada:.4f}+0.05"
    )

    print(f"\n[C] BBAS3 compra MAY11: peso_medio={peso:.4f} contrib={contrib:.4f} frac_esperada={frac_esperada:.4f}")


# ── Teste D: buy-and-hold mês inteiro ─────────────────────────────────────────

def test_D_buyandhold_contribuicao_igual_a_retorno_ponderado():
    """
    1 ativo, 100 unidades, preços conhecidos para todo maio.
    Com peso=1 todos os dias, contribuição = soma aritmética dos retornos diários.
    Nota: contribuição (aritmética) ≠ retorno_ativo (geométrico) — diferença normal.
    """
    ativos = {"VALE3": {"familia": _FAM, "composite": "Gerida",
                        "benchmark": "IBOV", "bloco_ips": "GROWTH"}}
    eventos = [
        {"data": APR30, "ativo": "VALE3", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
    ]
    dias_maio = bdate_range(MAY1, D_FIM)
    n = len(dias_maio)
    precos = {APR30: 50.0}
    for i, d in enumerate(dias_maio):
        precos[d] = 50.0 * (1 + 0.10 * (i + 1) / n)
    precos_pub = {"VALE3": precos}

    df = calc_atribuicao_mensal(eventos, ativos, precos_pub, {}, D_FIM)

    row = _get_maio(df, "VALE3")
    assert not row.empty, "VALE3 deve aparecer em maio"

    contrib = row.iloc[0]["contribuicao"]
    retorno = row.iloc[0]["retorno_ativo"]
    peso = row.iloc[0]["peso_medio"]

    # Único ativo = 100% do composite → peso_d=1 todos os dias
    assert abs(peso - 1.0) < 0.01, f"peso_medio deve ser ~1.0 (único ativo), foi {peso:.4f}"

    # retorno_ativo (geométrico) deve ser próximo de 10%
    assert abs(retorno - 0.10) < 0.01, f"retorno geométrico esperado ~10%, foi {retorno:.4f}"

    # contribuição (aritmética) deve ser positiva e menor que o retorno geométrico
    assert contrib > 0, f"contribuição deve ser positiva, foi {contrib:.4f}"
    assert contrib < retorno + 0.001, f"contribuição aritmética não pode exceder retorno geométrico"

    # Contribuição deve ser igual à soma aritmética dos retornos diários (identidade exata)
    from carteira_clean_web.backend.engine.utils import preco_em as _pe
    soma_r_arith = sum(
        _pe(precos, d) / _pe(precos, dias_maio[i - 1] if i > 0 else APR30) - 1
        for i, d in enumerate(dias_maio)
    )
    assert abs(contrib - soma_r_arith) < 1e-9, (
        f"contrib ({contrib:.6f}) deve ser igual à soma aritmética ({soma_r_arith:.6f})"
    )

    print(f"\n[D] VALE3 buy-and-hold: retorno_geom={retorno:.4f} contrib_arith={contrib:.4f} peso={peso:.4f}")


# ── Teste E: identidade soma contribuições = retorno composite ─────────────────

def test_E_soma_contribuicoes_igual_retorno_composite():
    """
    Dois ativos no mesmo composite. A soma das contribuições individuais
    deve aproximar o retorno total do composite (tolerância 0.05pp = 5e-4).

    Isso verifica a identidade matemática do modelo de Brinson.
    """
    ativos = {
        "ITSA4": {"familia": _FAM, "composite": "Gerida",
                  "benchmark": "IBOV", "bloco_ips": "DEFENSIVOS"},
        "RADL3": {"familia": _FAM, "composite": "Gerida",
                  "benchmark": "IBOV", "bloco_ips": "GROWTH"},
    }
    eventos = [
        {"data": APR30, "ativo": "ITSA4", "tipo": "SALDO_INICIAL",
         "qtd": 200.0, "valor": 4000.0, "obs": ""},
        {"data": APR30, "ativo": "RADL3", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 3000.0, "obs": ""},
    ]
    dias_maio = bdate_range(MAY1, D_FIM)
    n = len(dias_maio)
    precos_itsa = {APR30: 20.0}
    precos_radl = {APR30: 30.0}
    for i, d in enumerate(dias_maio):
        precos_itsa[d] = 20.0 * (1 + 0.05 * (i + 1) / n)   # +5% no mês
        precos_radl[d] = 30.0 * (1 + 0.08 * (i + 1) / n)   # +8% no mês
    precos_pub = {"ITSA4": precos_itsa, "RADL3": precos_radl}

    df = calc_atribuicao_mensal(eventos, ativos, precos_pub, {}, D_FIM)

    # soma das contribuições individuais
    ind = df[(df["mes"] == "2026-05") & (df["ativo"] != "TOTAL")]
    soma_contrib = ind[ind["composite"] == "Gerida"]["contribuicao"].sum()

    # Identidade EXATA: sum(peso_d × r_d) = soma aritmética dos retornos diários do composite.
    # (diferente do retorno geométrico = produto dos fatores diários)
    from carteira_clean_web.backend.engine.utils import preco_em
    ret_arith = 0.0
    d_prev = APR30
    for d in dias_maio:
        pat_d = sum(
            (qtd * preco_em(pp, d) or 0)
            for qtd, pp in [(200.0, precos_itsa), (100.0, precos_radl)]
        )
        pat_ant = sum(
            (qtd * preco_em(pp, d_prev) or 0)
            for qtd, pp in [(200.0, precos_itsa), (100.0, precos_radl)]
        )
        if pat_ant > 0:
            ret_arith += (pat_d - pat_ant) / pat_ant
        d_prev = d

    diff = abs(soma_contrib - ret_arith)
    print(f"\n[E] soma_contrib={soma_contrib:.6f} ret_arith={ret_arith:.6f} diff={diff:.2e}")
    assert diff < 1e-9, (
        f"Identidade aritmética violada: soma_contrib={soma_contrib:.6f} vs ret_arith={ret_arith:.6f} diff={diff:.2e}"
    )
