"""create fundamentos append-only table

Tabela append-only de indicadores fundamentalistas por ativo.
Mesmo padrão de cotacoes/benchmarks: cada (ticker, indicador) pode ter
múltiplas linhas (fetched_at diferente); a leitura usa MAX(fetched_at).

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDICADORES = (
    "PL", "PVP", "ROE", "ROIC", "DY",
    "MARGEM_EBITDA", "DIV_LIQ_EBITDA", "MARGEM_LIQUIDA", "LPA", "VPA",
)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)

    if inspector.has_table("fundamentos"):
        return

    indicadores_check = "','".join(_INDICADORES)
    op.create_table(
        "fundamentos",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("data_referencia", sa.Date(), nullable=False),
        sa.Column("indicador", sa.Text(), nullable=False),
        sa.Column("valor", sa.Float(), nullable=True),
        sa.Column(
            "fonte",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'yfinance'"),
        ),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            f"indicador IN ('{indicadores_check}')",
            name="ck_fundamentos_indicador",
        ),
    )
    op.create_index(
        "ix_fundamentos_ticker_indicador",
        "fundamentos",
        ["ticker", "indicador"],
        unique=False,
    )
    op.create_index(
        "ix_fundamentos_ticker_data",
        "fundamentos",
        ["ticker", "data_referencia"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fundamentos_ticker_data", table_name="fundamentos")
    op.drop_index("ix_fundamentos_ticker_indicador", table_name="fundamentos")
    op.drop_table("fundamentos")
