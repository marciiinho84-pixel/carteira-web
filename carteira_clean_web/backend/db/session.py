"""Fábrica de sessão SQLAlchemy. Lê o caminho do banco de DB_PATH ou do default."""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# parents[2] = carteira_clean_web/ — onde o banco foi criado pela migração
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "carteira.db"
# DB_PATH permite override via variável de ambiente (usado no Docker)
_DB_ENV = os.environ.get("DB_PATH")
_DEFAULT_DB = Path(_DB_ENV) if _DB_ENV else _DEFAULT_DB


def get_engine(db_path: Path = None):
    path = db_path or _DEFAULT_DB
    return create_engine(f"sqlite:///{path}", echo=False)


def get_session(db_path: Path = None) -> Session:
    engine = get_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
