"""eventos_corporativos: novos tipos (proventos brapi + IPE CVM)

Fase 4 da fatia "Ingestão de dados": amplia o CheckConstraint de
eventos_corporativos.tipo para cobrir bonificação/desdobramento (brapi
stockDividends) e fato relevante/aviso aos acionistas/calendário de
eventos (IPE CVM).

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-10
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

_OLD_CHECK = "tipo IN ('EARNINGS_DATE','EX_DIVIDEND_DATE','DIVIDENDO','JCP','RESULTADO')"
_NEW_CHECK = (
    "tipo IN ('EARNINGS_DATE','EX_DIVIDEND_DATE','DIVIDENDO','JCP','RESULTADO',"
    "'BONIFICACAO','DESDOBRAMENTO','FATO_RELEVANTE','AVISO_ACIONISTAS','CALENDARIO_EVENTO')"
)


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_eventos_corp_tipo", "eventos_corporativos", type_="check")
        op.create_check_constraint("ck_eventos_corp_tipo", "eventos_corporativos", _NEW_CHECK)
    # SQLite: produção é sempre Postgres — no-op seguro (mesmo padrão de 0013).


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_eventos_corp_tipo", "eventos_corporativos", type_="check")
        op.create_check_constraint("ck_eventos_corp_tipo", "eventos_corporativos", _OLD_CHECK)
