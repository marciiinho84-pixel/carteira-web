"""add index on cotacoes.source (preços derivados LCI/CVM/Tesouro)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-10

Documenta os novos valores de `source` usados em cotacoes a partir da
fatia "preços derivados persistidos": 'curva_lci' (saldo diário de LCI/LCA
projetado por CDI), 'cvm' (cota de fundos via CVM), 'tesouro_direto' (PU do
Tesouro Direto) — além dos já existentes 'yfinance' e 'seed'. Nenhum dado
novo é obrigatório; a coluna `source` já existe desde 0001_create_cotacoes.
Só adiciona um índice para acelerar leituras filtradas por source.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)

    indices = [ix["name"] for ix in insp.get_indexes("cotacoes")]
    if "ix_cotacoes_source" not in indices:
        op.create_index("ix_cotacoes_source", "cotacoes", ["source"])


def downgrade():
    op.drop_index("ix_cotacoes_source", table_name="cotacoes")
