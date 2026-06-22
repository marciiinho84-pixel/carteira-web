"""
tests/test_benchmarks_fase_b.py — Fase B (corte de produção): calc_twr_e_benchmarks
lê todos os 7 benchmarks diretamente da tabela benchmarks.

Casos:
  A) Todos 7 benchmarks presentes na tabela → colunas corretas e valores plausíveis.
  B) NASDAQ ausente da tabela → nasdaq_brl_acum = 0.0 em todas as linhas (sem fallback).
  C) no_api=True simulado: baixar_benchmarks não inseriu dados novos, mas tabela já tem
     histórico → engine lê normalmente e cdi_acum/ibov_acum não ficam vazios.

Rodar:
    pytest tests/test_benchmarks_fase_b.py -v -s
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from carteira_clean_web.backend.engine.twr import calc_twr_e_benchmarks

D1 = date(2026, 1, 2)
D2 = date(2026, 1, 3)
D3 = date(2026, 1, 6)
NOW = "2026-01-07T10:00:00"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _seed(engine, rows: list) -> None:
    with engine.connect() as conn:
        for row in rows:
            conn.execute(
                text("INSERT INTO benchmarks (nome, date, valor, fetched_at, source) "
                     "VALUES (:nome, :date, :valor, :fetched_at, :source)"),
                {"nome": row[0], "date": row[1], "valor": row[2],
                 "fetched_at": row[3], "source": row[4]},
            )
        conn.commit()


def _df_evo() -> pd.DataFrame:
    return pd.DataFrame([
        {"data": D1, "patrimonio_gerida": 100_000.0, "patrimonio_funcef": 50_000.0,
         "patrimonio_total": 150_000.0, "patrimonio_rv": 30_000.0},
        {"data": D2, "patrimonio_gerida": 101_000.0, "patrimonio_funcef": 50_000.0,
         "patrimonio_total": 151_000.0, "patrimonio_rv": 31_000.0},
        {"data": D3, "patrimonio_gerida": 102_000.0, "patrimonio_funcef": 50_000.0,
         "patrimonio_total": 152_000.0, "patrimonio_rv": 32_000.0},
    ])


# ── Teste A: todos 7 benchmarks da tabela ───────────────────────────────────

def test_A_todos_7_benchmarks_lidos_da_tabela(patch_session):
    engine = patch_session
    _seed(engine, [
        ("CDI",    str(D1), 0.000527,   NOW, "bcb"),
        ("CDI",    str(D2), 0.000528,   NOW, "bcb"),
        ("CDI",    str(D3), 0.000529,   NOW, "bcb"),
        ("IPCA",   str(D1), 0.0044,     NOW, "bcb"),
        ("IPCA",   str(D2), 0.0044,     NOW, "bcb"),
        ("IBOV",   str(D1), 128_000.0,  NOW, "yfinance"),
        ("IBOV",   str(D2), 129_000.0,  NOW, "yfinance"),
        ("IBOV",   str(D3), 130_000.0,  NOW, "yfinance"),
        ("SP500",  str(D1), 5_800.0,    NOW, "yfinance"),
        ("SP500",  str(D2), 5_820.0,    NOW, "yfinance"),
        ("USDBRL", str(D1), 5.80,       NOW, "yfinance"),
        ("USDBRL", str(D2), 5.82,       NOW, "yfinance"),
        ("USDBRL", str(D3), 5.83,       NOW, "yfinance"),
        ("NASDAQ", str(D1), 21_000.0,   NOW, "yfinance"),
        ("NASDAQ", str(D2), 21_200.0,   NOW, "yfinance"),
        ("OURO",   str(D1), 39.5,       NOW, "yfinance"),
        ("OURO",   str(D2), 40.0,       NOW, "yfinance"),
    ])

    result = calc_twr_e_benchmarks(_df_evo(), [], [], {})

    print(f"\n[A] cdi={result['cdi_acum'].iloc[-1]:.6f}  "
          f"ibov={result['ibov_acum'].iloc[-1]:.4f}  "
          f"nasdaq={result['nasdaq_brl_acum'].iloc[-1]:.4f}  "
          f"ouro={result['ouro_brl_acum'].iloc[-1]:.4f}")

    assert "cdi_acum"        in result.columns
    assert "ipca_acum"       in result.columns
    assert "ibov_acum"       in result.columns
    assert "sp500_brl_acum"  in result.columns
    assert "nasdaq_brl_acum" in result.columns
    assert "ouro_brl_acum"   in result.columns

    assert result["cdi_acum"].iloc[-1] > 0
    assert result["ibov_acum"].iloc[-1] > 0
    assert result["nasdaq_brl_acum"].iloc[-1] > 0


# ── Teste B: benchmark ausente → zero sem fallback ──────────────────────────

def test_B_benchmark_ausente_tabela_zero_sem_fallback(patch_session):
    engine = patch_session
    _seed(engine, [
        ("USDBRL", str(D1), 5.8, NOW, "yfinance"),
        ("USDBRL", str(D2), 5.8, NOW, "yfinance"),
        ("USDBRL", str(D3), 5.8, NOW, "yfinance"),
        # NASDAQ intencionalmente ausente
    ])

    result = calc_twr_e_benchmarks(_df_evo(), [], [], {})

    print(f"\n[B] nasdaq_brl_acum={result['nasdaq_brl_acum'].tolist()}")

    assert (result["nasdaq_brl_acum"] == 0.0).all(), (
        "Sem NASDAQ na tabela, nasdaq_brl_acum deve ser 0.0 em todas as linhas"
    )


# ── Teste C: no_api=True simulado — tabela já tem dados históricos ────────────

def test_C_no_api_true_tabela_ja_tem_historico(patch_session):
    """
    Simula no_api=True: baixar_benchmarks não foi chamado,
    mas a tabela já tem histórico. Engine lê normalmente.
    """
    engine = patch_session
    _seed(engine, [
        ("CDI",  str(D1), 0.000527, NOW, "bcb"),
        ("CDI",  str(D2), 0.000528, NOW, "bcb"),
        ("CDI",  str(D3), 0.000529, NOW, "bcb"),
        ("IBOV", str(D1), 128_000.0, NOW, "yfinance"),
        ("IBOV", str(D2), 129_000.0, NOW, "yfinance"),
        ("IBOV", str(D3), 130_000.0, NOW, "yfinance"),
    ])

    result = calc_twr_e_benchmarks(_df_evo(), [], [], {})

    print(f"\n[C] cdi={result['cdi_acum'].iloc[-1]:.6f}  "
          f"ibov={result['ibov_acum'].iloc[-1]:.4f}")

    assert result["cdi_acum"].iloc[-1] > 0
    assert result["ibov_acum"].iloc[-1] > 0
