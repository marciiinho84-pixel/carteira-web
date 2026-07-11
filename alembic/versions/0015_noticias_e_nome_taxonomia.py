"""noticias + nome em taxonomia_setorial

Fase 5 da fatia "Ingestão de dados": tabela noticias (Google News RSS,
UPSERT por ticker+titulo) e coluna taxonomia_setorial.nome (nome da empresa,
capturado de graça no mesmo /api/quote/list já usado pra setor — usado na
query do RSS: "{nome_empresa}" OR {ticker}).

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("taxonomia_setorial", sa.Column("nome", sa.Text, nullable=True))

    op.create_table(
        "noticias",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ticker", sa.Text, nullable=False),
        sa.Column("titulo", sa.Text, nullable=False),
        sa.Column("fonte", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("publicado_em", sa.DateTime, nullable=True),
        sa.Column("coletado_em", sa.DateTime, nullable=False),
        sa.UniqueConstraint("ticker", "titulo", name="uq_noticias_ticker_titulo"),
    )
    op.create_index("ix_noticias_ticker_publicado", "noticias", ["ticker", "publicado_em"])


def downgrade():
    op.drop_index("ix_noticias_ticker_publicado", table_name="noticias")
    op.drop_table("noticias")
    op.drop_column("taxonomia_setorial", "nome")
