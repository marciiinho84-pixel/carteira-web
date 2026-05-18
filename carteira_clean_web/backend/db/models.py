"""
SQLAlchemy models — tabelas-fonte da Carteira Clean.

Três tabelas espelham as 3 abas-fonte do Excel:
  - ativos        → CAD_ATIVOS
  - eventos       → EVENTOS (event log, single source of truth)
  - precos_manuais → HISTORICO_PRECOS
"""

from datetime import date
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Date, Text,
    UniqueConstraint, CheckConstraint, Index,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Ativo(Base):
    """Cadastro mestre de ativos — espelho de CAD_ATIVOS."""
    __tablename__ = "ativos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(20), nullable=False, unique=True)
    classe = Column(String(50))
    familia = Column(String(50))
    setor = Column(String(100))
    indexador = Column(String(50))
    benchmark = Column(String(50))
    liquidez = Column(String(50))
    risco = Column(String(50))
    composite = Column(String(20), nullable=False, default="Gerida")
    observacao = Column(Text)

    __table_args__ = (
        CheckConstraint("composite IN ('Gerida', 'FUNCEF')", name="ck_composite"),
    )

    def to_dict(self):
        return {
            "ticker": self.ticker,
            "classe": self.classe,
            "familia": self.familia,
            "setor": self.setor,
            "indexador": self.indexador,
            "benchmark": self.benchmark,
            "liquidez": self.liquidez,
            "risco": self.risco,
            "composite": self.composite,
            "observacao": self.observacao,
        }


class Evento(Base):
    """Event log — single source of truth. Nunca modificado automaticamente."""
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # linha_excel preserva a ordem original da planilha (usada para ordenação)
    linha_excel = Column(Integer, nullable=False)
    data = Column(Date, nullable=False)
    ativo = Column(String(20), nullable=False)
    tipo = Column(String(30), nullable=False)
    qtd = Column(Float)
    preco = Column(Float)
    valor = Column(Float, nullable=False, default=0.0)
    obs = Column(Text, default="")

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('SALDO_INICIAL','COMPRA','VENDA','DIVIDENDO','JCP',"
            "'RENDIMENTO','AMORTIZACAO','BONIFICACAO','CONTRIBUICAO',"
            "'APORTE_EXTERNO','RESGATE_EXTERNO','VENCIMENTO')",
            name="ck_tipo_evento",
        ),
        Index("ix_eventos_data", "data"),
        Index("ix_eventos_ativo", "ativo"),
    )

    def to_dict(self):
        return {
            "linha": self.linha_excel,
            "data": self.data,
            "ativo": self.ativo,
            "tipo": self.tipo,
            "qtd": self.qtd,
            "preco": self.preco,
            "valor": self.valor or 0,
            "obs": self.obs or "",
        }


class PrecoManual(Base):
    """Preços manuais para ativos sem cotação pública — espelho de HISTORICO_PRECOS."""
    __tablename__ = "precos_manuais"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    ticker = Column(String(20), nullable=False)
    valor = Column(Float, nullable=False)
    fonte = Column(String(100))

    __table_args__ = (
        UniqueConstraint("data", "ticker", name="uq_preco_data_ticker"),
        Index("ix_precos_ticker_data", "ticker", "data"),
    )
