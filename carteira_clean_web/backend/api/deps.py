"""Dependências compartilhadas (sessão SQLAlchemy via FastAPI Depends)."""

from carteira_clean_web.backend.db.session import get_engine
from sqlalchemy.orm import sessionmaker, Session


def get_db():
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
