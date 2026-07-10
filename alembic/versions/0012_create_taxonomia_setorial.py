"""create taxonomia_setorial

Tabela ticker → setor (classificação brapi.dev), usada por contexto_setorial
e comparar_multiplos/analise_fundamentalista para achar peers do mesmo setor
sem depender do campo livre `ativos.setor` (curado manualmente, inconsistente).

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "taxonomia_setorial",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("setor_brapi", sa.Text, nullable=True),
        sa.Column("atualizado_em", sa.DateTime, nullable=False),
        sa.UniqueConstraint("ticker", name="uq_taxonomia_ticker"),
    )


def downgrade():
    op.drop_table("taxonomia_setorial")
