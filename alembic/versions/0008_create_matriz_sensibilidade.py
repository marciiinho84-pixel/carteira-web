"""create matriz_sensibilidade + seed data

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-20

Tabela estática de sensibilidade macro→setor (Fatia 13).
Populada com seed data no upgrade; editável via DB ou futura tela de Config.
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_SEED = [
    # SELIC ↓
    ("SELIC_META", "QUEDA", "Construção Civil",    "POSITIVO", 3, "Financiamento imobiliário mais barato estimula demanda"),
    ("SELIC_META", "QUEDA", "Bancos Tradicionais", "NEGATIVO", 2, "Compressão de spread — margem financeira reduz"),
    ("SELIC_META", "QUEDA", "Energia Elétrica",    "POSITIVO", 2, "DY relativo melhora vs renda fixa; valuation cresce"),
    ("SELIC_META", "QUEDA", "Saneamento",          "POSITIVO", 2, "Utilities com dividendos tornam-se mais atrativos"),
    ("SELIC_META", "QUEDA", "Varejo",              "POSITIVO", 2, "Crédito ao consumidor mais barato estimula consumo"),
    # SELIC ↑
    ("SELIC_META", "ALTA",  "Construção Civil",    "NEGATIVO", 3, "Financiamento imobiliário mais caro reduz demanda"),
    ("SELIC_META", "ALTA",  "Bancos Tradicionais", "POSITIVO", 2, "Spread aumenta; margem financeira cresce"),
    ("SELIC_META", "ALTA",  "Energia Elétrica",    "NEGATIVO", 2, "DY relativo piora vs renda fixa; valuation comprime"),
    # USD ↑
    ("USD_BRL",    "ALTA",  "Petróleo & Gás",      "POSITIVO", 3, "Receita em USD; queda do BRL eleva receita convertida"),
    ("USD_BRL",    "ALTA",  "Agronegócio",         "POSITIVO", 3, "Exportadoras beneficiam-se da receita em USD"),
    ("USD_BRL",    "ALTA",  "Varejo",              "NEGATIVO", 2, "Produtos importados encarecem; pressão nos custos"),
    # USD ↓
    ("USD_BRL",    "QUEDA", "Petróleo & Gás",      "NEGATIVO", 2, "Apreciação do BRL reduz receita convertida"),
    # IPCA ↑
    ("IPCA",       "ALTA",  "Varejo",              "NEGATIVO", 2, "Inflação corrói poder de compra e eleva custos"),
    ("IPCA",       "ALTA",  "Energia Elétrica",    "POSITIVO", 1, "Tarifas indexadas à inflação protegem receita"),
    ("IPCA",       "ALTA",  "Saneamento",          "POSITIVO", 1, "Contratos indexados protegem receita real"),
]


def upgrade():
    from alembic import op as _op
    from sqlalchemy import inspect
    conn = _op.get_bind()
    insp = inspect(conn)

    if "matriz_sensibilidade" not in insp.get_table_names():
        op.create_table(
            "matriz_sensibilidade",
            sa.Column("id",         sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("indicador",  sa.Text, nullable=False),
            sa.Column("variacao",   sa.Text, nullable=False),
            sa.Column("setor",      sa.Text, nullable=False),
            sa.Column("direcao",    sa.Text, nullable=False),
            sa.Column("peso",       sa.Integer, nullable=False, server_default="2"),
            sa.Column("logica",     sa.Text, nullable=True),
            sa.Column("criado_em",  sa.DateTime, nullable=False),
        )
        try:
            op.create_index("ix_matriz_ind_setor", "matriz_sensibilidade", ["indicador", "setor"])
        except Exception:
            pass

        # Seed data — alembic faz commit ao sair do context.begin_transaction()
        now = datetime.utcnow()
        conn.execute(
            sa.text(
                "INSERT INTO matriz_sensibilidade "
                "(indicador, variacao, setor, direcao, peso, logica, criado_em) "
                "VALUES (:ind, :var, :set, :dir, :pes, :log, :now)"
            ),
            [{"ind": r[0], "var": r[1], "set": r[2], "dir": r[3], "pes": r[4],
              "log": r[5], "now": now}
             for r in _SEED],
        )


def downgrade():
    op.drop_table("matriz_sensibilidade")
