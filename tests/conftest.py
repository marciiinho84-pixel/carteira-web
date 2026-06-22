"""
Fixtures compartilhadas para testes que usam precos.py / benchmarks.

Cria engine SQLite temporário com o mesmo schema da produção
e patcha get_session para que as funções de precos.py usem o SQLite.
As queries usam subqueries correlacionadas (compatíveis com SQLite + PostgreSQL).
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch


_DDL_COTACOES = """
    CREATE TABLE IF NOT EXISTS cotacoes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker     TEXT NOT NULL,
        date       TEXT NOT NULL,
        preco      REAL NOT NULL,
        fetched_at TEXT NOT NULL,
        source     TEXT NOT NULL DEFAULT 'yfinance'
    )
"""

_DDL_BENCHMARKS = """
    CREATE TABLE IF NOT EXISTS benchmarks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        nome       TEXT NOT NULL,
        date       TEXT NOT NULL,
        valor      REAL NOT NULL,
        fetched_at TEXT NOT NULL,
        source     TEXT NOT NULL DEFAULT 'yfinance'
    )
"""


@pytest.fixture
def sqlite_engine(tmp_path):
    """Engine SQLite com tabelas cotacoes + benchmarks."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as conn:
        conn.execute(text(_DDL_COTACOES))
        conn.execute(text(_DDL_BENCHMARKS))
        conn.commit()
    return engine


@pytest.fixture
def patch_session(sqlite_engine):
    """Patcha get_session → sessions do SQLite de teste."""
    Session = sessionmaker(bind=sqlite_engine)
    with patch(
        "carteira_clean_web.backend.db.session.get_session",
        side_effect=lambda: Session(),
    ):
        yield sqlite_engine
