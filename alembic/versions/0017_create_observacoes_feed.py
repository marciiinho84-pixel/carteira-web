"""create observacoes_feed e varredura_estado

Feed de fatos novos e relevantes da Sala de Comando (seção "Orquestra"),
substituindo o replay de mensagens de chat. `varredura_estado` guarda a
última classificação conhecida por (categoria, chave) para o motor de
varredura detectar transição de estado (rating técnico, zona de valuation,
banda IPS, regime macro) entre uma rodada de cron e a seguinte.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "observacoes_feed",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("categoria", sa.Text, nullable=False),
        sa.Column("ativo", sa.Text, nullable=True),
        sa.Column("referencia_id", sa.Integer, nullable=True),
        sa.Column("conteudo", sa.Text, nullable=False),
        sa.Column("fundamentos_json", sa.Text, nullable=True),
        sa.Column("criado_em", sa.DateTime, nullable=False),
        sa.Column("visualizado_em", sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "categoria IN ('ALERTA','TESE','IPS','TECNICO','FUNDAMENTALISTA','NOTICIA','MACRO')",
            name="ck_observacoes_feed_categoria",
        ),
    )
    op.create_index("ix_observacoes_feed_visto", "observacoes_feed", ["visualizado_em"])
    op.create_index("ix_observacoes_feed_categoria_ativo", "observacoes_feed", ["categoria", "ativo"])

    op.create_table(
        "varredura_estado",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("categoria", sa.Text, nullable=False),
        sa.Column("chave", sa.Text, nullable=False),
        sa.Column("valor", sa.Text, nullable=False),
        sa.Column("atualizado_em", sa.DateTime, nullable=False),
        sa.UniqueConstraint("categoria", "chave", name="uq_varredura_estado_categoria_chave"),
    )


def downgrade():
    op.drop_table("varredura_estado")
    op.drop_index("ix_observacoes_feed_categoria_ativo", table_name="observacoes_feed")
    op.drop_index("ix_observacoes_feed_visto", table_name="observacoes_feed")
    op.drop_table("observacoes_feed")
