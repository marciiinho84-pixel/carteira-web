"""create metricas_comportamento

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-20

Tabela de cache de métricas comportamentais do investidor (Fatia 8).
Calculadas sob demanda via tool MCP; não tem cron próprio.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    from alembic import op as _op
    from sqlalchemy import inspect
    conn = _op.get_bind()
    insp = inspect(conn)
    if "metricas_comportamento" not in insp.get_table_names():
        op.create_table(
            "metricas_comportamento",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("metrica", sa.Text, nullable=False),
            sa.Column("bloco_ips", sa.Text, nullable=True),
            sa.Column("periodo", sa.Text, nullable=False),
            sa.Column("periodo_inicio", sa.Date, nullable=False),
            sa.Column("periodo_fim", sa.Date, nullable=False),
            sa.Column("valor_json", sa.Text, nullable=True),
            sa.Column("calculado_em", sa.DateTime, nullable=False),
        )
    # Índices: ignora se já existem
    try:
        op.create_index("ix_mc_metrica_periodo", "metricas_comportamento", ["metrica", "periodo"])
    except Exception:
        pass
    try:
        op.create_index("ix_mc_calculado", "metricas_comportamento", ["calculado_em"])
    except Exception:
        pass


def downgrade():
    op.drop_table("metricas_comportamento")
