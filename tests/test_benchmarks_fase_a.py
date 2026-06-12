"""
tests/test_benchmarks_fase_a.py — Fase A: comparação tabela vs pkl (validação em paralelo).

Casos:
  A) OK: tabela == pkl (diff relativo ≤ 1e-5) → ok=N, div=0
  B) DIVERGENTE: tabela ≠ pkl (diff relativo > 1e-5) → divergentes=1
  C) AUSENTE_TAB: valor no pkl, ausente na tabela → ausentes_tab=1
  D) AUSENTE_PKL: valor na tabela, ausente no pkl → ausentes_pkl=1

Rodar:
    pytest tests/test_benchmarks_fase_a.py -v -s
"""

import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.precos import carregar_benchmarks_da_tabela
from carteira_clean_web.backend.engine.twr import _comparar_benchmarks

NOW = datetime.now().isoformat(timespec="seconds")
D1  = date(2026, 1, 2)
D2  = date(2026, 1, 3)
D3  = date(2026, 1, 6)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _criar_db(rows: list) -> str:
    """Cria DB temporário com tabela benchmarks. rows = (nome, date_str, valor, fetched_at, source)."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.execute("""
        CREATE TABLE benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL, date TEXT NOT NULL,
            valor REAL NOT NULL, fetched_at TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'yfinance'
        )
    """)
    if rows:
        con.executemany(
            "INSERT INTO benchmarks (nome, date, valor, fetched_at, source) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    con.commit()
    con.close()
    return tmp.name


def _carregar(db: str) -> dict:
    with patch.dict("os.environ", {"DB_PATH": db}):
        return carregar_benchmarks_da_tabela()


# ── Teste A: OK — tabela ≡ pkl ───────────────────────────────────────────────

def test_A_ok_tabela_igual_pkl():
    """CDI idêntico em tabela e pkl → ok=3, divergentes=0, ausentes=0."""
    CDI = {D1: 0.000527, D2: 0.000528, D3: 0.000529}
    IBOV = {D1: 128_000.0}
    db = _criar_db([
        ("CDI",  str(D1), 0.000527, NOW, "bcb"),
        ("CDI",  str(D2), 0.000528, NOW, "bcb"),
        ("CDI",  str(D3), 0.000529, NOW, "bcb"),
        ("IBOV", str(D1), 128_000.0, NOW, "yfinance"),
    ])
    tabela = _carregar(db)
    pkl = {"CDI": CDI, "IBOV": IBOV}

    stats = _comparar_benchmarks(pkl, tabela)

    print(f"\n[A] ok={stats['ok']}  div={stats['divergentes']}  "
          f"aus_tab={stats['ausentes_tab']}  aus_pkl={stats['ausentes_pkl']}")

    assert stats["ok"] == 4
    assert stats["divergentes"] == 0
    assert stats["ausentes_tab"] == 0
    assert stats["ausentes_pkl"] == 0


# ── Teste B: DIVERGENTE — diff relativo > 1e-5 ───────────────────────────────

def test_B_divergente_detectado():
    """IBOV: pkl=128_000, tabela=128_100 → rel≈7.8e-4 >> 1e-5 → divergentes=1."""
    pkl_val = 128_000.0
    tab_val = 128_100.0                       # +100 pts = +0.078%
    rel_esperado = abs(pkl_val - tab_val) / abs(pkl_val)

    db = _criar_db([("IBOV", str(D1), tab_val, NOW, "yfinance")])
    tabela = _carregar(db)
    pkl = {"IBOV": {D1: pkl_val}}

    stats = _comparar_benchmarks(pkl, tabela)
    det = stats["detalhes"]

    print(f"\n[B] ok={stats['ok']}  div={stats['divergentes']}  "
          f"rel={rel_esperado:.2e}  detalhe={det[0] if det else None}")

    assert stats["divergentes"] == 1
    assert stats["ok"] == 0
    assert det[0][0] == "DIVERGENTE"
    assert det[0][1] == "IBOV"
    assert det[0][5] == pytest.approx(rel_esperado, rel=1e-3)


# ── Teste C: AUSENTE_TAB — no pkl, fora da tabela ────────────────────────────

def test_C_ausente_tabela():
    """SP500 presente no pkl mas ausente na tabela → ausentes_tab=1."""
    db = _criar_db([])                         # tabela vazia
    tabela = _carregar(db)                     # {}
    pkl = {"SP500": {D1: 5_800.0, D2: 5_820.0}}

    stats = _comparar_benchmarks(pkl, tabela)

    print(f"\n[C] ok={stats['ok']}  aus_tab={stats['ausentes_tab']}  "
          f"aus_pkl={stats['ausentes_pkl']}  div={stats['divergentes']}")
    for cat, nome, dt, v_p, v_t, rel in stats["detalhes"]:
        print(f"    {cat} {nome} {dt}  pkl={v_p}  tab={v_t}")

    assert stats["ausentes_tab"] == 2           # D1 e D2 de SP500
    assert stats["divergentes"] == 0
    assert stats["ausentes_pkl"] == 0
    assert all(d[0] == "AUSENTE_TAB" for d in stats["detalhes"])


# ── Teste D: AUSENTE_PKL — na tabela, fora do pkl ────────────────────────────

def test_D_ausente_pkl():
    """IPCA presente na tabela mas pkl não tem IPCA → ausentes_pkl=1."""
    db = _criar_db([("IPCA", str(D1), 0.0044, NOW, "bcb")])
    tabela = _carregar(db)                     # IPCA presente
    pkl = {}                                   # pkl sem IPCA

    stats = _comparar_benchmarks(pkl, tabela)

    print(f"\n[D] ok={stats['ok']}  aus_pkl={stats['ausentes_pkl']}  "
          f"aus_tab={stats['ausentes_tab']}  div={stats['divergentes']}")
    for cat, nome, dt, v_p, v_t, rel in stats["detalhes"]:
        print(f"    {cat} {nome} {dt}  pkl={v_p}  tab={v_t}")

    assert stats["ausentes_pkl"] == 1
    assert stats["divergentes"] == 0
    assert stats["ausentes_tab"] == 0
    assert stats["detalhes"][0][0] == "AUSENTE_PKL"
    assert stats["detalhes"][0][1] == "IPCA"
