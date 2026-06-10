"""
tests/test_var_dia.py — Fix do d_minus_1 re-ancorado por ticker.

Bug: d_minus_1 era calculado UMA VEZ antes do loop, ancorado ao calendário hoje.
Quando hoje não tem preço e preco_atual veio de lookback para ontem, d_minus_1
caía no mesmo dia que preco_atual → diferença = 0 → var_dia=0% (falso).

Fix: para cada ticker, data_real = max(dt in serie | dt ≤ hoje);
     d_minus_1 = dia útil anterior a data_real (não a hoje).

Casos:
  A) hoje tem preço → comportamento inalterado (sem regressão)
  B) hoje sem preço (lookback) → var_dia real, não mais 0%  ← BUG CORRIGIDO
  C) sem nenhum preço → var_dia=None, sem erro
  D) fim de semana (hoje=domingo) → preco_atual=sexta, d_minus_1=quinta, var_dia real

Rodar:
    pytest tests/test_var_dia.py -v -s
"""

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.api.routers.resultados import posicoes
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

FAMILIA_PUB = next(iter(COTIZADO_PUBLICO))   # ex: "Ação BR"

# 42.39 e 43.33 são os preços reais de WEGE3 (06-10 e 06-09 na VM)
PRECO_D0 = 42.39
PRECO_D1 = 43.33
VAR_ESPERADA = (PRECO_D0 - PRECO_D1) / PRECO_D1   # ≈ -0.021694


def _posicao(qtd=100.0, custo_total=4000.0, custo_medio=40.0):
    return SimpleNamespace(qtd=qtd, custo_total=custo_total, custo_medio=custo_medio)


def _estado(precos_pub, hoje):
    return {
        "posicoes": {"WEGE3": _posicao()},
        "ativos": {"WEGE3": {"familia": FAMILIA_PUB, "classe": "RV", "composite": "Gerida"}},
        "precos_publicos": {"WEGE3": precos_pub},
        "precos_manuais": {},
        "hoje": hoje,
        "df_evo": pd.DataFrame(),
        "proventos": {},
    }


def _chamar_posicoes(precos_pub, hoje):
    with patch("carteira_clean_web.backend.api.routers.resultados.engine_cache") as mc:
        mc.esta_calculado.return_value = True
        mc.get_estado.return_value = _estado(precos_pub, hoje)
        resultado = posicoes()
    return next(r for r in resultado if r.ticker == "WEGE3")


# ── Teste A: hoje tem preço — sem regressão ──────────────────────────────────

def test_A_hoje_tem_preco_sem_regressao():
    """hoje=quarta (2026-06-10): preço disponível para hoje mesmo.

    data_real = 2026-06-10; d_minus_1 = 2026-06-09 → var_dia = -2.17%.
    Comportamento idêntico ao anterior (sem regressão).
    """
    hoje = date(2026, 6, 10)   # quarta-feira
    precos = {
        date(2026, 6, 10): PRECO_D0,   # hit direto
        date(2026, 6, 9):  PRECO_D1,
    }
    wege = _chamar_posicoes(precos, hoje)

    print(f"\n[A] preco_atual={wege.preco_atual:.4f}  var_dia_pct={wege.var_dia_pct:.6f}")

    assert wege.preco_atual == pytest.approx(PRECO_D0, abs=1e-4)
    assert wege.var_dia_pct == pytest.approx(VAR_ESPERADA, abs=1e-4)


# ── Teste B: hoje sem preço (lookback) — bug corrigido ──────────────────────

def test_B_hoje_sem_preco_lookback_var_dia_real():
    """hoje=quinta (2026-06-11): NÃO há preço para hoje; lookback cai em 2026-06-10.

    ANTES do fix:
      d_minus_1 = bdate(end=06-11) = 2026-06-10
      preco_atual = lookback(06-11) = 42.39 (de 06-10)
      p_d1 = preco_em(06-10) = 42.39 (MESMO dia) → var_dia = 0% (BUG)

    DEPOIS do fix:
      data_real = max(dt ≤ 06-11) = 2026-06-10
      d_minus_1 = bdate(end=06-10) = 2026-06-09
      p_d1 = 43.33 → var_dia ≈ -2.17% (CORRETO)
    """
    hoje = date(2026, 6, 11)   # quinta-feira — SEM preço para hoje
    precos = {
        date(2026, 6, 10): PRECO_D0,   # lookback cai aqui
        date(2026, 6, 9):  PRECO_D1,
    }
    wege = _chamar_posicoes(precos, hoje)

    print(f"\n[B] preco_atual={wege.preco_atual:.4f}  var_dia_pct={wege.var_dia_pct:.6f}")
    print(f"    (bug antigo retornaria 0.0; fix retorna {VAR_ESPERADA:.6f})")

    assert wege.preco_atual == pytest.approx(PRECO_D0, abs=1e-4)
    assert wege.var_dia_pct != pytest.approx(0.0, abs=1e-6), "BUG: var_dia ainda é zero!"
    assert wege.var_dia_pct == pytest.approx(VAR_ESPERADA, abs=1e-4)


# ── Teste C: sem nenhum preço — var_dia=None, sem erro ──────────────────────

def test_C_sem_precos_var_dia_none():
    """precos_publicos={}: preco_atual=None → var_dia=None, var_dia_pct=None, sem exceção."""
    hoje = date(2026, 6, 10)
    wege = _chamar_posicoes({}, hoje)

    print(f"\n[C] preco_atual={wege.preco_atual}  var_dia={wege.var_dia}  var_dia_pct={wege.var_dia_pct}")

    assert wege.preco_atual is None
    assert wege.var_dia is None
    assert wege.var_dia_pct is None


# ── Teste D: fim de semana — d_minus_1 = quinta (não sexta) ─────────────────

def test_D_fim_de_semana_d_minus_1_correto():
    """hoje=domingo (2026-06-14): lookback vai para sexta (06-12).

    data_real = 2026-06-12 (sexta); d_minus_1 = bdate(end=06-12) = 2026-06-11 (quinta).
    p_d1 = preço de quinta → var_dia = variação sexta vs quinta ≈ -2.17%.
    """
    hoje = date(2026, 6, 14)   # domingo
    precos = {
        date(2026, 6, 12): PRECO_D0,   # sexta — lookback cai aqui
        date(2026, 6, 11): PRECO_D1,   # quinta — deve ser o d_minus_1
    }
    wege = _chamar_posicoes(precos, hoje)

    print(f"\n[D] preco_atual={wege.preco_atual:.4f}  var_dia_pct={wege.var_dia_pct:.6f}")
    print(f"    (data_real=06-12/sexta, d_minus_1=06-11/quinta, var_dia=sexta vs quinta)")

    assert wege.preco_atual == pytest.approx(PRECO_D0, abs=1e-4)
    assert wege.var_dia_pct == pytest.approx(VAR_ESPERADA, abs=1e-4)
