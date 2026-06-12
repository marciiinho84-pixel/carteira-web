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

import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.precos import _gravar_benchmarks

NOW = datetime.now().isoformat(timespec="seconds")
D1  = date(2026, 6, 10)
D2  = date(2026, 6, 11)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _criar_db(rows: list = None) -> str:
    """Cria DB temporário com tabela benchmarks; rows = [(nome, date_str, valor, fetched_at, source)]."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.execute("""
        CREATE TABLE benchmarks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nome       TEXT NOT NULL,
            date       TEXT NOT NULL,
            valor      REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'yfinance'
        )
    """)
    if rows:
        con.executemany(
            "INSERT INTO benchmarks (nome, date, valor, fetched_at, source) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    con.commit()
    con.close()
    return tmp.name


def _contar(db: str, nome: str) -> int:
    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM benchmarks WHERE nome=?", (nome,)).fetchone()[0]
    con.close()
    return n


def _chamar(serie: dict, nome: str, db: str, source: str = "yfinance") -> None:
    with patch.dict("os.environ", {"DB_PATH": db}):
        _gravar_benchmarks(nome, serie, source)


# ── Teste A: inédito → insere ─────────────────────────────────────────────

def test_A_inedito_insere():
    """(NASDAQ, D1) ainda não existe na tabela → deve inserir."""
    db = _criar_db()
    assert _contar(db, "NASDAQ") == 0

    _chamar({D1: 29446.18}, "NASDAQ", db)

    n = _contar(db, "NASDAQ")
    print(f"\n[A] antes=0  depois={n}")
    assert n == 1


# ── Teste B: mesmo valor exato → NÃO insere ──────────────────────────────

def test_B_mesmo_valor_nao_insere():
    """CDI mesmo valor repetido → NÃO insere (delta=0)."""
    valor = 0.000527
    db = _criar_db([("CDI", str(D1), valor, NOW, "bcb")])
    assert _contar(db, "CDI") == 1

    _chamar({D1: valor}, "CDI", db, source="bcb")

    n = _contar(db, "CDI")
    print(f"\n[B] antes=1  depois={n}  (delta=0)")
    assert n == 1


# ── Teste B2: ruído float < 1e-5 relativo → NÃO insere ───────────────────

def test_B2a_ruido_escala_ibov_nao_insere():
    """IBOV ~130 000: delta=0.001 → relativo=7.7e-9 << 1e-5 → NÃO insere."""
    valor_base = 130_000.0
    ruido      = 0.001                    # 7.7e-9 relativo
    db = _criar_db([("IBOV", str(D1), valor_base, NOW, "yfinance")])

    _chamar({D1: valor_base + ruido}, "IBOV", db)

    n = _contar(db, "IBOV")
    rel = abs(ruido) / abs(valor_base)
    print(f"\n[B2a] IBOV  delta={ruido}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel < 1e-5, "pré-condição: ruído deve ser < 1e-5 relativo"
    assert n == 1


def test_B2b_ruido_escala_cdi_nao_insere():
    """CDI ~5e-5: delta=1e-10 → relativo=2e-6 << 1e-5 → NÃO insere."""
    valor_base = 5.27e-5
    ruido      = 1e-10                    # 2e-6 relativo
    db = _criar_db([("CDI", str(D1), valor_base, NOW, "bcb")])

    _chamar({D1: valor_base + ruido}, "CDI", db, source="bcb")

    n = _contar(db, "CDI")
    rel = abs(ruido) / abs(valor_base)
    print(f"\n[B2b] CDI   delta={ruido:.2e}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel < 1e-5, "pré-condição: ruído deve ser < 1e-5 relativo"
    assert n == 1


# ── Teste C: diferença real > 1e-5 relativo → insere ─────────────────────

def test_C_diferenca_real_insere():
    """IBOV com mudança real de 0.5% (>> 1e-5) → insere nova linha."""
    valor_base = 130_000.0
    delta      = 650.0                    # 0.5% → relativo=5e-3 >> 1e-5
    db = _criar_db([("IBOV", str(D1), valor_base, NOW, "yfinance")])

    _chamar({D1: valor_base + delta}, "IBOV", db)

    n = _contar(db, "IBOV")
    rel = abs(delta) / abs(valor_base)
    print(f"\n[C] IBOV   delta={delta}  relativo={rel:.2e}  antes=1  depois={n}")
    assert rel > 1e-5, "pré-condição: delta deve ser > 1e-5 relativo"
    assert n == 2


# ── Teste D: falha na gravação → não quebra coleta ────────────────────────

def test_D_falha_gravacao_nao_quebra():
    """DB inexistente → _gravar_benchmarks loga e retorna silenciosamente."""
    serie = {D1: 29000.0, D2: 29100.0}

    # Aponta para caminho inválido — deve falhar na conexão
    with patch.dict("os.environ", {"DB_PATH": "/tmp/nao_existe_jamais_xyz.db"}):
        try:
            _gravar_benchmarks("NASDAQ", serie, "yfinance")
            resultado = "sem_excecao"
        except Exception as e:
            resultado = f"excecao: {e}"

    print(f"\n[D] resultado={resultado}  (esperado: sem_excecao ou tabela não existe)")
    # A função trata a ausência de tabela com OperationalError silenciado
    # Se o DB foi criado vazio (sqlite cria arquivo), OperationalError é silenciado
    assert resultado == "sem_excecao"
