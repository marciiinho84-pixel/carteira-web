"""create disciplinas tables: teses, diario_decisoes, regra_aportes

Fatias 4, 5 e 7 das disciplinas de gestão.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    existing = inspector.get_table_names()

    if "teses" not in existing:
        op.create_table(
            "teses",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("ticker", sa.Text(), nullable=False),
            sa.Column("bloco_ips", sa.Text(), nullable=True),
            sa.Column("racional", sa.Text(), nullable=False),
            sa.Column("cenario_esperado", sa.Text(), nullable=True),
            sa.Column("criterio_invalidacao", sa.Text(), nullable=True),
            sa.Column("nivel_invalidacao", sa.Text(), nullable=False, server_default=sa.text("'VERDE'")),
            sa.Column("data_criacao", sa.Date(), nullable=False),
            sa.Column("data_atualizacao", sa.Date(), nullable=True),
            sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'ATIVA'")),
            sa.Column("observacao_encerramento", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "nivel_invalidacao IN ('VERDE','AMARELO','VERMELHO')",
                name="ck_tese_nivel",
            ),
            sa.CheckConstraint(
                "status IN ('ATIVA','INVALIDADA','ENCERRADA')",
                name="ck_tese_status",
            ),
        )
        op.create_index("ix_teses_ticker", "teses", ["ticker"])
        op.create_index("ix_teses_status", "teses", ["status"])

    if "diario_decisoes" not in existing:
        op.create_table(
            "diario_decisoes",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("data_decisao", sa.Date(), nullable=False),
            sa.Column("ticker", sa.Text(), nullable=False),
            sa.Column("acao", sa.Text(), nullable=False),
            sa.Column("racional", sa.Text(), nullable=False),
            sa.Column("cenario_esperado", sa.Text(), nullable=True),
            sa.Column("conviccao", sa.Integer(), nullable=False, server_default=sa.text("3")),
            sa.Column("preco_entrada", sa.Float(), nullable=True),
            sa.Column("tese_id", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "acao IN ('COMPRA','VENDA','AUMENTO','REDUCAO','MANTER','WATCHLIST')",
                name="ck_diario_acao",
            ),
            sa.CheckConstraint(
                "conviccao BETWEEN 1 AND 5",
                name="ck_diario_conviccao",
            ),
        )
        op.create_index("ix_diario_ticker", "diario_decisoes", ["ticker"])
        op.create_index("ix_diario_data", "diario_decisoes", ["data_decisao"])

    if "regra_aportes" not in existing:
        op.create_table(
            "regra_aportes",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("valor_mensal_alvo", sa.Float(), nullable=False),
            sa.Column("tipo", sa.Text(), nullable=False, server_default=sa.text("'PROGRAMADO'")),
            sa.Column("criterio_oportunismo", sa.Text(), nullable=True),
            sa.Column("data_criacao", sa.Date(), nullable=False),
            sa.Column("ativo", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.CheckConstraint(
                "tipo IN ('PROGRAMADO','OPORTUNISTICO','MISTO')",
                name="ck_regra_tipo",
            ),
        )


def downgrade() -> None:
    op.drop_table("regra_aportes")
    op.drop_index("ix_diario_data", table_name="diario_decisoes")
    op.drop_index("ix_diario_ticker", table_name="diario_decisoes")
    op.drop_table("diario_decisoes")
    op.drop_index("ix_teses_status", table_name="teses")
    op.drop_index("ix_teses_ticker", table_name="teses")
    op.drop_table("teses")
