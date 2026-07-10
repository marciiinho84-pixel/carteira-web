"""peers e EV/EBITDA

Fase 3 da fatia "Ingestão de dados": cria universo_peers (ticker→setor
usado para dirigir a coleta de fundamentos de peers via brapi) e adiciona
'EV_EBITDA' ao CheckConstraint de fundamentos.indicador (extração brapi
inclui EV/EBITDA, que não existia no conjunto de 10 indicadores yfinance).

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_OLD_CHECK = (
    "indicador IN ('PL','PVP','ROE','ROIC','DY',"
    "'MARGEM_EBITDA','DIV_LIQ_EBITDA','MARGEM_LIQUIDA','LPA','VPA')"
)
_NEW_CHECK = (
    "indicador IN ('PL','PVP','ROE','ROIC','DY',"
    "'MARGEM_EBITDA','DIV_LIQ_EBITDA','MARGEM_LIQUIDA','LPA','VPA','EV_EBITDA')"
)


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_fundamentos_indicador", "fundamentos", type_="check")
        op.create_check_constraint("ck_fundamentos_indicador", "fundamentos", _NEW_CHECK)
    # SQLite não suporta ALTER de CHECK constraint fora de modo batch com
    # recriação de tabela; produção é sempre Postgres — no-op aqui é seguro.

    op.create_table(
        "universo_peers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("setor", sa.Text, nullable=True),
        sa.Column("motivo", sa.Text, nullable=False),
        sa.Column("adicionado_em", sa.DateTime, nullable=False),
        sa.UniqueConstraint("ticker", name="uq_universo_peers_ticker"),
    )


def downgrade():
    op.drop_table("universo_peers")
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_fundamentos_indicador", "fundamentos", type_="check")
        op.create_check_constraint("ck_fundamentos_indicador", "fundamentos", _OLD_CHECK)
