"""Fábrica de sessão SQLAlchemy.

Prioridade de configuração:
  1. DATABASE_URL (PostgreSQL: postgresql+psycopg2://user:pass@host/db)
  2. DB_PATH       (SQLite via env var: /data/carteira.db)
  3. Default local (carteira_clean_web/carteira.db)
"""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

_DATABASE_URL: str | None = os.environ.get("DATABASE_URL")
_DB_PATH_ENV: str | None = os.environ.get("DB_PATH")
_DEFAULT_SQLITE = Path(__file__).resolve().parents[2] / "carteira.db"

if _DATABASE_URL:
    _ENGINE = create_engine(
        _DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
elif _DB_PATH_ENV:
    _ENGINE = create_engine(
        f"sqlite:///{_DB_PATH_ENV}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    _ENGINE = create_engine(
        f"sqlite:///{_DEFAULT_SQLITE}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

_SessionLocal = sessionmaker(bind=_ENGINE, autocommit=False, autoflush=False)


def get_engine(db_path: Path | None = None):
    """Retorna engine global ou temporário para db_path (testes)."""
    if db_path is not None:
        return create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )
    return _ENGINE


def get_session(db_path: Path | None = None) -> Session:
    if db_path is not None:
        return sessionmaker(bind=get_engine(db_path))()
    return _SessionLocal()
