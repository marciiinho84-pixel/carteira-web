"""
tests/test_gravar_benchmarks.py — Etapa 2b: gravação na tabela benchmarks.

Casos:
  A ) (NASDAQ, data nova) inédito → insere
  B ) Mesmo valor exato repetido  → NÃO insere
  B2) Ruído float < 1e-5 relativo → NÃO insere
      B2a: escala IBOV   (~130 000) — delta 0.001 / 130000 ≈ 7.7e-9
      B2b: escala CDI    (~5e-5)    — delta 1e-10 / 5e-5   = 2e-6
  C ) Diferença real > 1e-5 relativo → insere
  D ) Falha simulada na gravação → coleta/recalculo seguem sem quebrar

Rodar:
    pytest tests/test_gravar_benchmarks.py -v -s
"""

import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from carteira_clean_web.backend.engine.precos import _gravar_benchmarks

NOW = datetime.now().isoformat(timespec="seconds")
D1  = date(2026, 6, 10)
D2  = date(2026, 6, 11)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _seed(engine, rows: list) -> None:
    """Insere linhas [(nome, date_str, valor, fetched_at, source)] na tabela benchmarks."""
    with engine.connect() as conn:
        for row in rows:
            conn.execute(
                text("INSERT INTO benchmarks (nome, date, valor, fetched_at, source) "
                     "VALUES (:nome, :date, :valor, :fetched_at, :source)"),
                {"nome": row[0], "date": row[1], "valor": row[2],
                 "fetched_at": row[3], "source": row[4]},
            )
        conn.commit()


def _contar(engine, nome: str) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT COUNT(*) FROM benchmarks WHERE nome=:nome"),
            {"nome": nome},
        ).scalar()


# ── Teste A: inédito → insere ─────────────────────────────────────────────

def test_A_inedito_insere(patch_session):
    engine = patch_session
    assert _contar(engine, "NASDAQ") == 0

    _gravar_benchmarks("NASDAQ", {D1: 29446.18}, "yfinance")

    n = _contar(engine, "NASDAQ")
    print(f"\n[A] antes=0  depois={n}")
    assert n == 1


# ── Teste B: mesmo valor exato → NÃO insere ──────────────────────────────

def test_B_mesmo_valor_nao_insere(patch_session):
    engine = patch_session
    valor = 0.000527
    _seed(engine, [("CDI", str(D1), valor, NOW, "bcb")])
    assert _contar(engine, "CDI") == 1

    _gravar_benchmarks("CDI", {D1: valor}, "bcb")

    n = _contar(engine, "CDI")
    print(f"\n[B] antes=1  depois={n}  (delta=0)")
    assert n == 1


# ── Teste B2: ruído float < 1e-5 relativo → NÃO insere ───────────────────

def test_B2a_ruido_escala_ibov_nao_insere(patch_session):
    engine = patch_session
    valor_base = 130_000.0
    ruido      = 0.001
    _seed(engine, [("IBOV", str(D1), valor_base, NOW, "yfinance")])

    _gravar_benchmarks("IBOV", {D1: valor_base + ruido}, "yfinance")

    n = _contar(engine, "IBOV")
    rel = abs(ruido) / abs(valor_base)
    print(f"\n[B2a] IBOV  delta={ruido}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel < 1e-5
    assert n == 1


def test_B2b_ruido_escala_cdi_nao_insere(patch_session):
    engine = patch_session
    valor_base = 5.27e-5
    ruido      = 1e-10
    _seed(engine, [("CDI", str(D1), valor_base, NOW, "bcb")])

    _gravar_benchmarks("CDI", {D1: valor_base + ruido}, "bcb")

    n = _contar(engine, "CDI")
    rel = abs(ruido) / abs(valor_base)
    print(f"\n[B2b] CDI   delta={ruido:.2e}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel < 1e-5
    assert n == 1


# ── Teste C: diferença real > 1e-5 relativo → insere ─────────────────────

def test_C_diferenca_real_insere(patch_session):
    engine = patch_session
    valor_base = 130_000.0
    delta      = 650.0
    _seed(engine, [("IBOV", str(D1), valor_base, NOW, "yfinance")])

    _gravar_benchmarks("IBOV", {D1: valor_base + delta}, "yfinance")

    n = _contar(engine, "IBOV")
    rel = abs(delta) / abs(valor_base)
    print(f"\n[C] IBOV   delta={delta}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel > 1e-5
    assert n == 2


# ── Teste D: falha na gravação → não quebra coleta ────────────────────────

def test_D_falha_gravacao_nao_quebra():
    """get_session lança exceção → _gravar_benchmarks silencia e retorna."""
    serie = {D1: 29000.0, D2: 29100.0}

    with patch(
        "carteira_clean_web.backend.db.session.get_session",
        side_effect=RuntimeError("conexão recusada"),
    ):
        try:
            _gravar_benchmarks("NASDAQ", serie, "yfinance")
            resultado = "sem_excecao"
        except Exception as e:
            resultado = f"excecao: {e}"

    print(f"\n[D] resultado={resultado}  (esperado: sem_excecao)")
    assert resultado == "sem_excecao"
