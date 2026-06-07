"""create cotacoes append-only table + seed from pkl

Cria tabela append-only de cotações históricas. Cada (ticker, date) pode ter
múltiplas linhas (fetched_at diferente); a leitura usa MAX(fetched_at).
Seed popula com precos_publicos do cache_engine.pkl se disponível.

Revision ID: 0001
Revises:
Create Date: 2026-06-07
"""
from __future__ import annotations

import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    if not inspector.has_table("cotacoes"):
        op.create_table(
            "cotacoes",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("ticker", sa.Text(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("preco", sa.Float(), nullable=False),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.Text(), nullable=False,
                      server_default=sa.text("'yfinance'")),
        )
        op.create_index(
            "ix_cotacoes_ticker_date",
            "cotacoes",
            ["ticker", "date"],
            unique=False,
        )

    _seed_from_pkl(conn)


def downgrade() -> None:
    op.drop_index("ix_cotacoes_ticker_date", table_name="cotacoes")
    op.drop_table("cotacoes")


# ── Seed ─────────────────────────────────────────────────────────────────────

def _localizar_pkl() -> Path | None:
    """Tenta os mesmos caminhos que cache.py usa."""
    cache_dir = os.environ.get("CACHE_DIR")
    if cache_dir:
        p = Path(cache_dir) / "cache_engine.pkl"
        if p.exists():
            return p

    # Caminho default: carteira_clean_web/cache_engine.pkl (relativo à raiz do projeto)
    # alembic/versions/ → parents[2] = raiz do projeto
    default = Path(__file__).resolve().parents[2] / "carteira_clean_web" / "cache_engine.pkl"
    if default.exists():
        return default

    return None


def _seed_from_pkl(conn) -> None:
    """Insere precos_publicos do pkl em cotacoes (source='seed').

    Idempotente por design: se a tabela já tiver dados de seed, insere mesmo
    assim (append-only — duplicatas vão conviver; a leitura usa MAX(fetched_at)).
    Se o pkl não existir, pula sem falhar.
    """
    pkl_path = _localizar_pkl()
    if pkl_path is None:
        print("[seed] cache_engine.pkl não encontrado — seed pulado")
        return

    try:
        payload = pickle.loads(pkl_path.read_bytes())
        estado = payload.get("estado", {})
        precos_publicos = estado.get("precos_publicos", {})
    except Exception as e:
        print(f"[seed] Não foi possível ler o pkl ({e}) — seed pulado")
        return

    if not precos_publicos:
        print("[seed] precos_publicos vazio no pkl — seed pulado")
        return

    now = datetime.now()
    rows = []
    for ticker, serie in precos_publicos.items():
        for dt, preco in serie.items():
            # Normaliza date para string ISO (SQLite armazena TEXT)
            dt_str = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            rows.append({
                "ticker": ticker,
                "date": dt_str,
                "preco": float(preco),
                "fetched_at": now.isoformat(),
                "source": "seed",
            })

    if not rows:
        print("[seed] Nenhuma linha a inserir — seed pulado")
        return

    conn.execute(
        sa.text(
            "INSERT INTO cotacoes (ticker, date, preco, fetched_at, source) "
            "VALUES (:ticker, :date, :preco, :fetched_at, :source)"
        ),
        rows,
    )
    print(
        f"[seed] {len(rows)} linhas inseridas em cotacoes "
        f"({len(precos_publicos)} tickers, source='seed')"
    )
