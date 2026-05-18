"""
engine/io.py — Leitura dos dados a partir do SQLite.

Substitui openpyxl.load_workbook + ler_cad_ativos/ler_eventos/ler_historico_precos
do atualizar_carteira.py original. Retorna as mesmas estruturas de dados
(dict, list[dict], dict[ticker -> dict[date -> float]]) para que os demais
módulos do engine funcionem sem modificação.
"""

from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import Session

from carteira_clean_web.backend.db.models import Ativo, Evento, PrecoManual
from carteira_clean_web.backend.db.session import get_session


def ler_ativos(session: Session) -> dict:
    """Retorna {ticker: {campo: valor}} — equivalente ao ler_cad_ativos() original."""
    rows = session.query(Ativo).all()
    return {a.ticker: a.to_dict() for a in rows}


def ler_eventos(session: Session) -> list:
    """Retorna lista de dicts ordenada por (data, ativo, linha_excel).
    Mesma estrutura que ler_eventos() original, incluindo chave 'linha'."""
    rows = (
        session.query(Evento)
        .order_by(Evento.data, Evento.ativo, Evento.linha_excel)
        .all()
    )
    return [e.to_dict() for e in rows]


def ler_historico_precos(session: Session) -> dict:
    """Retorna {ticker: {date: float}} — equivalente ao ler_historico_precos() original."""
    rows = session.query(PrecoManual).all()
    precos = defaultdict(dict)
    for p in rows:
        precos[p.ticker][p.data] = p.valor
    return dict(precos)


def carregar_dados(db_path: Path = None) -> tuple[dict, list, dict]:
    """Conveniência: abre sessão, lê tudo, fecha. Retorna (ativos, eventos, precos_manuais)."""
    session = get_session(db_path)
    try:
        ativos = ler_ativos(session)
        eventos = ler_eventos(session)
        precos_manuais = ler_historico_precos(session)
        return ativos, eventos, precos_manuais
    finally:
        session.close()
