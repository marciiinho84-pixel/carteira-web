"""
tests/test_comparacao_precos.py — Passo 2 Fase A: comparação yfinance vs tabela cotacoes.

Casos:
  A) mesmo preço (diff <= 0.01) → 1 OK, 0 divergentes
  B) preço diferente (diff > 0.01) → 0 OK, 1 DIVERGENTE com detalhes
  C) ticker no yfinance, ausente na tabela → 1 AUSENTE_TAB
  D) ticker na tabela, ausente no yfinance → 1 AUSENTE_YF

Rodar:
    pytest tests/test_comparacao_precos.py -v -s
"""

import logging
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

from carteira_clean_web.backend.engine.run import _comparar_yf_vs_tabela

NOW = datetime.now().isoformat(timespec="seconds")
DATE_A = date(2026, 6, 8)


def _criar_db(rows: list) -> str:
    """Cria DB temporário com tabela cotacoes e retorna o path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.execute("""
        CREATE TABLE cotacoes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker    TEXT    NOT NULL,
            date      TEXT    NOT NULL,
            preco     REAL    NOT NULL,
            fetched_at TEXT   NOT NULL,
            source    TEXT    NOT NULL DEFAULT 'yfinance'
        )
    """)
    if rows:
        con.executemany(
            "INSERT INTO cotacoes (ticker, date, preco, fetched_at, source) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    con.commit()
    con.close()
    return tmp.name


# ── Teste A: mesmo preço → 1 OK ─────────────────────────────────────────────

def test_A_mesmo_preco(caplog):
    """Preço idêntico em ambos: 1 OK, 0 divergentes, 0 ausentes."""
    db = _criar_db([("PETR4", "2026-06-08", 35.00, NOW, "yfinance")])
    precos_yf = {"PETR4": {DATE_A: 35.00}}

    with caplog.at_level(logging.WARNING):
        _comparar_yf_vs_tabela(precos_yf, db_path=db)

    relatorio = "\n".join(caplog.messages)
    print("\n[Teste A — mesmo preço]\n" + relatorio)

    assert "OK (diff <= 0.01)   : 1" in relatorio
    assert "DIVERGENTES         : 0" in relatorio
    assert "AUSENTES NA TABELA  : 0" in relatorio
    assert "AUSENTES NO YFINANCE: 0" in relatorio


# ── Teste B: preço diferente > 0.01 → 1 DIVERGENTE ─────────────────────────

def test_B_preco_divergente(caplog):
    """Diff = 5.00 > 0.01: 0 OK, 1 DIVERGENTE com ticker/data/valores."""
    db = _criar_db([("VALE3", "2026-06-08", 60.00, NOW, "yfinance")])
    precos_yf = {"VALE3": {DATE_A: 65.00}}

    with caplog.at_level(logging.WARNING):
        _comparar_yf_vs_tabela(precos_yf, db_path=db)

    relatorio = "\n".join(caplog.messages)
    print("\n[Teste B — preço divergente]\n" + relatorio)

    assert "OK (diff <= 0.01)   : 0" in relatorio
    assert "DIVERGENTES         : 1" in relatorio
    assert "DIVERGENTE  VALE3" in relatorio
    assert "yf=65.0000" in relatorio
    assert "tab=60.0000" in relatorio
    assert "diff=5.0000" in relatorio


# ── Teste C: ausente na tabela → 1 AUSENTE_TAB ──────────────────────────────

def test_C_ausente_na_tabela(caplog):
    """Tabela vazia: yfinance tem MGLU3, tabela não tem → 1 AUSENTE_TAB."""
    db = _criar_db([])
    precos_yf = {"MGLU3": {DATE_A: 12.50}}

    with caplog.at_level(logging.WARNING):
        _comparar_yf_vs_tabela(precos_yf, db_path=db)

    relatorio = "\n".join(caplog.messages)
    print("\n[Teste C — ausente na tabela]\n" + relatorio)

    assert "AUSENTES NA TABELA  : 1" in relatorio
    assert "AUSENTE_TAB  MGLU3" in relatorio


# ── Teste D: ausente no yfinance → 1 AUSENTE_YF ─────────────────────────────

def test_D_ausente_no_yfinance(caplog):
    """BBAS3 na tabela, yfinance retornou vazio → 1 AUSENTE_YF."""
    db = _criar_db([("BBAS3", "2026-06-08", 27.00, NOW, "yfinance")])
    precos_yf = {}

    with caplog.at_level(logging.WARNING):
        _comparar_yf_vs_tabela(precos_yf, db_path=db)

    relatorio = "\n".join(caplog.messages)
    print("\n[Teste D — ausente no yfinance]\n" + relatorio)

    assert "AUSENTES NO YFINANCE: 1" in relatorio
    assert "AUSENTE_YF   BBAS3" in relatorio
