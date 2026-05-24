"""
SQLAlchemy models — tabelas-fonte da Carteira Clean.

Três tabelas espelham as 3 abas-fonte do Excel:
  - ativos        → CAD_ATIVOS
  - eventos       → EVENTOS (event log, single source of truth)
  - precos_manuais → HISTORICO_PRECOS
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, Boolean,
    UniqueConstraint, CheckConstraint, Index, ForeignKey,
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
    data_vencimento = Column(Date, nullable=True)

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
            "data_vencimento": self.data_vencimento,
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
            "'APORTE_EXTERNO','RESGATE_EXTERNO','VENCIMENTO','RESGATE','APORTE')",
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


class Decisao(Base):
    """Diário de decisões de investimento."""
    __tablename__ = "decisoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_decisao = Column(Date, nullable=False)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="SET NULL"), nullable=True)
    ativo = Column(String(20), nullable=False)
    acao = Column(String(10), nullable=False)
    tese = Column(Text, nullable=False)
    expectativa_retorno_pct = Column(Float, nullable=True)
    horizonte = Column(String(10), nullable=True)
    revisao_em = Column(Date, nullable=True)
    resultado_revisao = Column(Text, nullable=True)
    notas = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("acao IN ('COMPRA','VENDA','MANTER','OBSERVAR')", name="ck_acao"),
        CheckConstraint("horizonte IN ('curto','medio','longo') OR horizonte IS NULL",
                        name="ck_horizonte"),
        Index("ix_decisoes_ativo", "ativo"),
        Index("ix_decisoes_revisao", "revisao_em"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "data_decisao": str(self.data_decisao) if self.data_decisao else None,
            "evento_id": self.evento_id,
            "ativo": self.ativo,
            "acao": self.acao,
            "tese": self.tese,
            "expectativa_retorno_pct": self.expectativa_retorno_pct,
            "horizonte": self.horizonte,
            "revisao_em": str(self.revisao_em) if self.revisao_em else None,
            "resultado_revisao": self.resultado_revisao,
            "notas": self.notas,
        }


class Importacao(Base):
    """Registro de cada importação de extrato via Claude API."""
    __tablename__ = "importacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data_upload = Column(DateTime, default=datetime.utcnow)
    arquivo_nome = Column(Text, nullable=False)
    arquivo_path = Column(Text)
    arquivo_hash = Column(Text)
    formato = Column(String(10))           # pdf|jpeg|png|xlsx|csv
    tipo_documento = Column(String(50))    # b3_custodia|b3_movimentacoes|auto|...
    tipo_identificado_ia = Column(String(50), nullable=True)   # tipo que o Claude identificou
    confianca_ia = Column(String(10), nullable=True)           # alta|media|baixa
    justificativa_ia = Column(Text, nullable=True)             # explicação da classificação
    modo_teste = Column(Boolean, default=False)                # dry_run — não grava no DB
    raw_json_ia = Column(Text, nullable=True)                  # resposta bruta do Claude
    status = Column(String(20), default="UPLOADED")  # UPLOADED|PROCESSING|PREVIEW|CONFIRMED|CANCELLED|ERROR
    total_eventos_extraidos = Column(Integer, default=0)
    total_eventos_gravados = Column(Integer, default=0)
    total_eventos_duplicados = Column(Integer, default=0)
    eventos_extraidos_json = Column(Text)
    erro_mensagem = Column(Text, nullable=True)
    custo_api_usd = Column(Float, default=0.0)
    data_confirmacao = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED','PROCESSING','PREVIEW','CONFIRMED','CANCELLED','ERROR')",
            name="ck_importacao_status",
        ),
        Index("ix_importacoes_status", "status"),
        Index("ix_importacoes_data", "data_upload"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "data_upload": self.data_upload.isoformat() if self.data_upload else None,
            "arquivo_nome": self.arquivo_nome,
            "arquivo_path": self.arquivo_path,
            "arquivo_hash": self.arquivo_hash,
            "formato": self.formato,
            "tipo_documento": self.tipo_documento,
            "tipo_identificado_ia": self.tipo_identificado_ia,
            "confianca_ia": self.confianca_ia,
            "justificativa_ia": self.justificativa_ia,
            "status": self.status,
            "total_eventos_extraidos": self.total_eventos_extraidos,
            "total_eventos_gravados": self.total_eventos_gravados,
            "total_eventos_duplicados": self.total_eventos_duplicados,
            "custo_api_usd": self.custo_api_usd,
            "erro_mensagem": self.erro_mensagem,
            "data_confirmacao": self.data_confirmacao.isoformat() if self.data_confirmacao else None,
        }


class ImportacaoEvento(Base):
    """Associa importações aos eventos gravados no DB."""
    __tablename__ = "importacao_evento"

    importacao_id = Column(Integer, ForeignKey("importacoes.id", ondelete="CASCADE"), primary_key=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), primary_key=True)
