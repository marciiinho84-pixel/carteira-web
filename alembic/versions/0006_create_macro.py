"""create macro tables: macro_indicadores + eventos_corporativos

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    existing = inspect(op.get_bind()).get_table_names()

    if "macro_indicadores" not in existing:
        op.create_table(
            "macro_indicadores",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("indicador", sa.Text, nullable=False),
            sa.Column("data_referencia", sa.Date, nullable=False),
            sa.Column("valor", sa.Float, nullable=True),
            sa.Column("fonte", sa.Text, nullable=True),
            sa.Column("fetched_at", sa.DateTime, nullable=False),
            sa.CheckConstraint(
                "indicador IN ('SELIC_META','SELIC_DIARIA','IPCA','USD_BRL','IPCA_FOCUS')",
                name="ck_macro_indicador",
            ),
        )
        op.create_index(
            "ix_macro_indicador_data",
            "macro_indicadores",
            ["indicador", "data_referencia"],
        )

    if "eventos_corporativos" not in existing:
        op.create_table(
            "eventos_corporativos",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("ticker", sa.Text, nullable=False),
            sa.Column("tipo", sa.Text, nullable=False),
            sa.Column("data_evento", sa.Date, nullable=False),
            sa.Column("descricao", sa.Text, nullable=True),
            sa.Column("fonte", sa.Text, nullable=True),
            sa.Column("fetched_at", sa.DateTime, nullable=False),
            sa.CheckConstraint(
                "tipo IN ('EARNINGS_DATE','EX_DIVIDEND_DATE','DIVIDENDO','JCP','RESULTADO')",
                name="ck_eventos_corp_tipo",
            ),
        )
        op.create_index(
            "ix_eventos_corp_ticker_data",
            "eventos_corporativos",
            ["ticker", "data_evento"],
        )
        op.create_index(
            "ix_eventos_corp_data",
            "eventos_corporativos",
            ["data_evento"],
        )


def downgrade():
    op.drop_table("eventos_corporativos")
    op.drop_table("macro_indicadores")
