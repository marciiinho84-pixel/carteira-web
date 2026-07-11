"""create taxonomia_override

Correção manual de setor por ticker — sobrepõe o setor_brapi coletado
quando a classificação automática está errada (ex.: ALOS3/MDNE3 vindo
como "Finance" da brapi).

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "taxonomia_override",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("setor_correto", sa.Text, nullable=False),
        sa.Column("motivo", sa.Text, nullable=True),
        sa.Column("criado_em", sa.DateTime, nullable=False),
        sa.UniqueConstraint("ticker", name="uq_taxonomia_override_ticker"),
    )


def downgrade():
    op.drop_table("taxonomia_override")
