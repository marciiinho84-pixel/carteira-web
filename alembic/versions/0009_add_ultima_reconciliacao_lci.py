"""add ultima_reconciliacao_lci + auto-registrar LCI existentes

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-06

Adiciona coluna ultima_reconciliacao_lci (Date nullable) na tabela ativos
e auto-registra tickers LCI-*/LCA-* que ainda não tenham cadastro,
derivando a familia e classe a partir dos eventos COMPRA existentes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)

    # 1. Adicionar coluna (idempotente)
    cols = [c["name"] for c in insp.get_columns("ativos")]
    if "ultima_reconciliacao_lci" not in cols:
        op.add_column("ativos", sa.Column("ultima_reconciliacao_lci", sa.Date, nullable=True))

    # 2. Auto-registrar tickers LCI-*/LCA-* que vieram de importações mas não têm cadastro
    compras_lci = conn.execute(text(
        "SELECT DISTINCT ativo, data FROM eventos "
        "WHERE tipo = 'COMPRA' "
        "AND (ativo LIKE 'LCI-%' OR ativo LIKE 'LCA-%') "
        "ORDER BY ativo, data"
    )).fetchall()

    for ativo, data_compra in compras_lci:
        existente = conn.execute(
            text("SELECT id FROM ativos WHERE ticker = :t"), {"t": ativo}
        ).fetchone()

        if existente is None:
            conn.execute(text(
                "INSERT INTO ativos "
                "(ticker, classe, familia, composite, bloco_ips, ultima_reconciliacao_lci) "
                "VALUES (:ticker, 'RENDA_FIXA', 'Letra de Crédito', 'Gerida', 'RENDA_FIXA', :data)"
            ), {"ticker": ativo, "data": str(data_compra)[:10]})
        else:
            # Atualiza data se ainda nula
            conn.execute(text(
                "UPDATE ativos SET ultima_reconciliacao_lci = :data "
                "WHERE ticker = :t AND ultima_reconciliacao_lci IS NULL"
            ), {"data": str(data_compra)[:10], "t": ativo})


def downgrade():
    op.drop_column("ativos", "ultima_reconciliacao_lci")
