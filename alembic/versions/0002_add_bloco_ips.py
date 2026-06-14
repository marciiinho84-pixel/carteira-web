"""add bloco_ips column to ativos

Adiciona coluna bloco_ips (TEXT, nullable) à tabela ativos para classificação
dos ativos nos blocos estratégicos da IPS v1.0.

Valores possíveis:
  SWING_TRADE  — Ações BR e ETFs de índices domésticos (benchmark IBOV)
  GROWTH       — BDRs/ETFs de teses estruturais de longo prazo (benchmark Nasdaq BRL)
  DEFENSIVOS   — Metais preciosos e ativos descorrelacionados (benchmark Ouro BRL)
  RENDA_FIXA   — Renda fixa, pós-fixados, IPCA+ (benchmark CDI)
  FORA_IPS     — FUNCEF, caixa operacional e ativos fora do perímetro gerido

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    if not inspector.has_table("ativos"):
        # Banco novo: ativos será criada pelo app (create_all) com bloco_ips já no model.
        return
    cols = [c["name"] for c in inspector.get_columns("ativos")]
    if "bloco_ips" in cols:
        return  # idempotente
    with op.batch_alter_table("ativos") as batch_op:
        batch_op.add_column(
            sa.Column("bloco_ips", sa.Text(), nullable=True)
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    if not inspector.has_table("ativos"):
        return
    cols = [c["name"] for c in inspector.get_columns("ativos")]
    if "bloco_ips" not in cols:
        return
    with op.batch_alter_table("ativos") as batch_op:
        batch_op.drop_column("bloco_ips")
