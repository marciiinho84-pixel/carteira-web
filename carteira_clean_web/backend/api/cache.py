"""
cache.py — Estado compartilhado do engine na memória.

Armazena o último resultado calculado pelo engine.
Recalcular é síncrono no MVP; após POST/PATCH/DELETE em /eventos,
o endpoint chama `recalcular()` automaticamente.

O estado é um singleton (módulo-level) — sem banco de cache,
sem Redis, sem complexidade desnecessária no MVP.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

_estado: dict = {}
_calculado_em: Optional[datetime] = None
_erro: Optional[str] = None


def get_estado() -> dict:
    return _estado


def get_calculado_em() -> Optional[datetime]:
    return _calculado_em


def get_erro() -> Optional[str]:
    return _erro


def recalcular(db_path: Path = None, no_api: bool = False) -> dict:
    """Executa o engine completo e armazena o resultado no cache."""
    global _estado, _calculado_em, _erro
    try:
        from carteira_clean_web.backend.engine.run import run
        resultado = run(db_path=db_path, no_api=no_api)
        _estado = resultado
        _calculado_em = datetime.now()
        _erro = None
        return resultado
    except Exception as e:
        _erro = str(e)
        raise


def esta_calculado() -> bool:
    return bool(_estado)
