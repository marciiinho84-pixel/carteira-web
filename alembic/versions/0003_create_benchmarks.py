"""create benchmarks append-only table + seed from pkl

Cria tabela append-only de benchmarks históricos. Mesmo padrão da tabela
cotacoes: cada (nome, date) pode ter múltiplas linhas (fetched_at diferente);
a leitura usa MAX(fetched_at).

Seed popula com estado["benchmarks"] do cache_engine.pkl se disponível:
  CDI, IBOV, SP500, USDBRL, IPCA — os 5 benchmarks já existentes.
  NASDAQ e OURO ainda não existem nesta fase (Migration 0003b).

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12
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

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    if not inspector.has_table("benchmarks"):
        op.create_table(
            "benchmarks",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("nome", sa.Text(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("valor", sa.Float(), nullable=False),
            sa.Column("fetched_at", sa.DateTime(), nullable=False),
            sa.Column(
                "source",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'yfinance'"),
            ),
        )
        op.create_index(
            "ix_benchmarks_nome_date",
            "benchmarks",
            ["nome", "date"],
            unique=False,
        )

    _seed_from_pkl(conn)


def downgrade() -> None:
    op.drop_index("ix_benchmarks_nome_date", table_name="benchmarks")
    op.drop_table("benchmarks")


# ── Seed ─────────────────────────────────────────────────────────────────────

def _localizar_pkl() -> Path | None:
    cache_dir = os.environ.get("CACHE_DIR")
    if cache_dir:
        p = Path(cache_dir) / "cache_engine.pkl"
        if p.exists():
            return p
    # alembic/versions/ → parents[2] = raiz do projeto
    candidates = [
        Path(__file__).resolve().parents[2] / "carteira_clean_web" / "cache_engine.pkl",
        Path(__file__).resolve().parents[2] / "data" / "cache" / "cache_engine.pkl",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _seed_from_pkl(conn) -> None:
    """Insere benchmarks do pkl em benchmarks (source='seed').

    Idempotente por design: se a tabela já tiver dados de seed, insere mesmo
    assim (append-only). A leitura usa MAX(fetched_at), então duplicatas são
    inócuas. Se o pkl não existir, pula sem falhar.
    """
    pkl_path = _localizar_pkl()
    if pkl_path is None:
        print("[seed-benchmarks] cache_engine.pkl não encontrado — seed pulado")
        return

    try:
        payload = pickle.loads(pkl_path.read_bytes())
        estado = payload.get("estado", {})
        benchmarks = estado.get("benchmarks", {})
    except Exception as e:
        print(f"[seed-benchmarks] Não foi possível ler o pkl ({e}) — seed pulado")
        return

    if not benchmarks:
        print("[seed-benchmarks] benchmarks vazio no pkl — seed pulado")
        return

    # Apenas os 5 benchmarks existentes nesta fase
    NOMES_FASE_A = {"CDI", "IBOV", "SP500", "USDBRL", "IPCA"}

    now = datetime.now()
    rows = []
    for nome, serie in benchmarks.items():
        if nome not in NOMES_FASE_A:
            continue
        for dt, valor in serie.items():
            dt_str = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
            rows.append({
                "nome":       nome,
                "date":       dt_str,
                "valor":      float(valor),
                "fetched_at": now.isoformat(),
                "source":     "seed",
            })

    if not rows:
        print("[seed-benchmarks] Nenhuma linha a inserir — seed pulado")
        return

    conn.execute(
        sa.text(
            "INSERT INTO benchmarks (nome, date, valor, fetched_at, source) "
            "VALUES (:nome, :date, :valor, :fetched_at, :source)"
        ),
        rows,
    )
    nomes = sorted({r["nome"] for r in rows})
    print(
        f"[seed-benchmarks] {len(rows)} linhas inseridas em benchmarks "
        f"(nomes: {nomes}, source='seed')"
    )
