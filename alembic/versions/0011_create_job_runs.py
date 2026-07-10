"""create job_runs

Tabela de log de execução dos coletores de ingestão (fatia "Ingestão de
dados" — taxonomia setorial, peers/fundamentos brapi, eventos corporativos,
notícias). Cada coleta agendada grava 1 linha aqui: início, fim, status,
linhas gravadas/inválidas e erro (se houver).

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("job", sa.Text, nullable=False),
        sa.Column("iniciado_em", sa.DateTime, nullable=False),
        sa.Column("terminado_em", sa.DateTime, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="rodando"),
        sa.Column("linhas_gravadas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("linhas_invalidas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("erro", sa.Text, nullable=True),
        sa.CheckConstraint("status IN ('rodando','sucesso','erro')", name="ck_job_runs_status"),
    )
    op.create_index("ix_job_runs_job_iniciado", "job_runs", ["job", "iniciado_em"])


def downgrade():
    op.drop_index("ix_job_runs_job_iniciado", table_name="job_runs")
    op.drop_table("job_runs")
