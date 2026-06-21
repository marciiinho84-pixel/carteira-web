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
    cnpj_cvm = Column(String(20), nullable=True)
    bloco_ips = Column(Text, nullable=True)

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
            "cnpj_cvm": self.cnpj_cvm,
            "bloco_ips": self.bloco_ips,
        }


class WatchlistItem(Base):
    """Watchlist — ativos monitorados ainda não comprados."""
    __tablename__ = "watchlist"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(String(20), nullable=False)
    preco_alvo  = Column(Float, nullable=False)
    stop_loss   = Column(Float, nullable=True)
    motivo      = Column(Text, nullable=True)
    data_adicao = Column(Date, nullable=False, default=date.today)
    ativo       = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_watchlist_ticker_ativo", "ticker", "ativo"),
    )


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


class AgendaEvento(Base):
    """Agenda de eventos corporativos — ex-dividendo, balanços, etc."""
    __tablename__ = "agenda_eventos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    ativo = Column(String(20), nullable=False)
    tipo = Column(String(30), nullable=False)   # EX_DIV | BALANCO | DIVIDENDO | PROVENTOS | OUTRO
    descricao = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agenda_data", "data"),
        Index("ix_agenda_ativo", "ativo"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "data": str(self.data),
            "ativo": self.ativo,
            "tipo": self.tipo,
            "descricao": self.descricao or "",
        }


class ImportacaoEvento(Base):
    """Associa importações aos eventos gravados no DB."""
    __tablename__ = "importacao_evento"

    importacao_id = Column(Integer, ForeignKey("importacoes.id", ondelete="CASCADE"), primary_key=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), primary_key=True)


# ─── Assistente: threads, mensagens, memórias ─────────────────────

class Conversa(Base):
    """Thread de conversa com o assistente."""
    __tablename__ = "conversas"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    titulo           = Column(Text, nullable=False, default="Nova conversa")
    criada_em        = Column(DateTime, nullable=False, default=datetime.utcnow)
    atualizada_em    = Column(DateTime, nullable=False, default=datetime.utcnow)
    ativa            = Column(Integer, nullable=False, default=1)
    total_msgs       = Column(Integer, nullable=False, default=0)
    total_tokens     = Column(Integer, nullable=False, default=0)
    custo_usd        = Column(Float, nullable=False, default=0.0)
    ultima_extracao  = Column(DateTime, nullable=True)
    resumo_historico = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_conversas_ativa", "ativa"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "titulo": self.titulo or "Nova conversa",
            "criada_em": self.criada_em.isoformat() if self.criada_em else None,
            "atualizada_em": self.atualizada_em.isoformat() if self.atualizada_em else None,
            "ativa": self.ativa,
            "total_msgs": self.total_msgs or 0,
            "total_tokens": self.total_tokens or 0,
            "custo_usd": self.custo_usd or 0.0,
            "ultima_extracao": self.ultima_extracao.isoformat() if self.ultima_extracao else None,
            "resumo_historico": self.resumo_historico,
        }


class Mensagem(Base):
    """Mensagem de uma conversa (user / assistant / tool)."""
    __tablename__ = "mensagens"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    conversa_id         = Column(Integer, ForeignKey("conversas.id", ondelete="CASCADE"), nullable=False)
    role                = Column(String(20), nullable=False)
    content             = Column(Text, nullable=False, default="")
    tool_calls          = Column(Text, nullable=True)
    tokens_in           = Column(Integer, nullable=False, default=0)
    tokens_out          = Column(Integer, nullable=False, default=0)
    custo_usd           = Column(Float, nullable=False, default=0.0)
    criada_em           = Column(DateTime, nullable=False, default=datetime.utcnow)
    incluida_no_resumo  = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant','tool','system')", name="ck_mensagem_role"),
        Index("ix_mensagens_conversa", "conversa_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "conversa_id": self.conversa_id,
            "role": self.role,
            "content": self.content or "",
            "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in or 0,
            "tokens_out": self.tokens_out or 0,
            "custo_usd": self.custo_usd or 0.0,
            "criada_em": self.criada_em.isoformat() if self.criada_em else None,
            "incluida_no_resumo": self.incluida_no_resumo or 0,
        }


class Tese(Base):
    """Tese de investimento com critério de invalidação (Fatia 4)."""
    __tablename__ = "teses"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    ticker                  = Column(Text, nullable=False)
    bloco_ips               = Column(Text, nullable=True)
    racional                = Column(Text, nullable=False)
    cenario_esperado        = Column(Text, nullable=True)
    criterio_invalidacao    = Column(Text, nullable=True)
    nivel_invalidacao       = Column(Text, nullable=False, default="VERDE")
    data_criacao            = Column(Date, nullable=False)
    data_atualizacao        = Column(Date, nullable=True)
    status                  = Column(Text, nullable=False, default="ATIVA")
    observacao_encerramento = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("nivel_invalidacao IN ('VERDE','AMARELO','VERMELHO')", name="ck_tese_nivel"),
        CheckConstraint("status IN ('ATIVA','INVALIDADA','ENCERRADA')", name="ck_tese_status"),
        Index("ix_teses_ticker", "ticker"),
        Index("ix_teses_status", "status"),
    )

    def to_dict(self):
        return {
            "id": self.id, "ticker": self.ticker, "bloco_ips": self.bloco_ips,
            "racional": self.racional, "cenario_esperado": self.cenario_esperado,
            "criterio_invalidacao": self.criterio_invalidacao,
            "nivel_invalidacao": self.nivel_invalidacao,
            "data_criacao": str(self.data_criacao) if self.data_criacao else None,
            "data_atualizacao": str(self.data_atualizacao) if self.data_atualizacao else None,
            "status": self.status,
            "observacao_encerramento": self.observacao_encerramento,
        }


class DiarioDecisao(Base):
    """Diário de decisão estruturado com convicção e link a teses (Fatia 5)."""
    __tablename__ = "diario_decisoes"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    data_decisao     = Column(Date, nullable=False)
    ticker           = Column(Text, nullable=False)
    acao             = Column(Text, nullable=False)
    racional         = Column(Text, nullable=False)
    cenario_esperado = Column(Text, nullable=True)
    conviccao        = Column(Integer, nullable=False, default=3)
    preco_entrada    = Column(Float, nullable=True)
    tese_id          = Column(Integer, ForeignKey("teses.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "acao IN ('COMPRA','VENDA','AUMENTO','REDUCAO','MANTER','WATCHLIST')",
            name="ck_diario_acao",
        ),
        CheckConstraint("conviccao BETWEEN 1 AND 5", name="ck_diario_conviccao"),
        Index("ix_diario_ticker", "ticker"),
        Index("ix_diario_data", "data_decisao"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "data_decisao": str(self.data_decisao) if self.data_decisao else None,
            "ticker": self.ticker, "acao": self.acao, "racional": self.racional,
            "cenario_esperado": self.cenario_esperado, "conviccao": self.conviccao,
            "preco_entrada": self.preco_entrada, "tese_id": self.tese_id,
        }


class RegraAporte(Base):
    """Regra de aporte mensal (Fatia 7). Apenas 1 ativa por vez."""
    __tablename__ = "regra_aportes"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    valor_mensal_alvo    = Column(Float, nullable=False)
    tipo                 = Column(Text, nullable=False, default="PROGRAMADO")
    criterio_oportunismo = Column(Text, nullable=True)
    data_criacao         = Column(Date, nullable=False)
    ativo                = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("tipo IN ('PROGRAMADO','OPORTUNISTICO','MISTO')", name="ck_regra_tipo"),
    )

    def to_dict(self):
        return {
            "id": self.id, "valor_mensal_alvo": self.valor_mensal_alvo,
            "tipo": self.tipo, "criterio_oportunismo": self.criterio_oportunismo,
            "data_criacao": str(self.data_criacao) if self.data_criacao else None,
            "ativo": bool(self.ativo),
        }


class Fundamento(Base):
    """Indicadores fundamentalistas por ativo — append-only, mesmo padrão de cotacoes.

    Múltiplas linhas por (ticker, indicador) são permitidas; a leitura
    usa MAX(fetched_at) para o valor mais recente.
    """
    __tablename__ = "fundamentos"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    ticker         = Column(Text, nullable=False)
    data_referencia = Column(Date, nullable=False)
    indicador      = Column(Text, nullable=False)
    valor          = Column(Float, nullable=True)
    fonte          = Column(Text, nullable=False, server_default="yfinance")
    fetched_at     = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "indicador IN ('PL','PVP','ROE','ROIC','DY',"
            "'MARGEM_EBITDA','DIV_LIQ_EBITDA','MARGEM_LIQUIDA','LPA','VPA')",
            name="ck_fundamentos_indicador",
        ),
        Index("ix_fundamentos_ticker_indicador", "ticker", "indicador"),
        Index("ix_fundamentos_ticker_data", "ticker", "data_referencia"),
    )


class MacroIndicador(Base):
    """Indicadores macro persistidos — append-only. Leitura via MAX(fetched_at)."""
    __tablename__ = "macro_indicadores"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    indicador      = Column(Text, nullable=False)
    data_referencia = Column(Date, nullable=False)
    valor          = Column(Float, nullable=True)
    fonte          = Column(Text, nullable=True)
    fetched_at     = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "indicador IN ('SELIC_META','SELIC_DIARIA','IPCA','USD_BRL','IPCA_FOCUS')",
            name="ck_macro_indicador",
        ),
        Index("ix_macro_indicador_data", "indicador", "data_referencia"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "indicador": self.indicador,
            "data_referencia": self.data_referencia.isoformat() if self.data_referencia else None,
            "valor": self.valor,
            "fonte": self.fonte,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class EventoCorporativo(Base):
    """Eventos corporativos (earnings, dividendos) — append-only."""
    __tablename__ = "eventos_corporativos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticker      = Column(Text, nullable=False)
    tipo        = Column(Text, nullable=False)
    data_evento = Column(Date, nullable=False)
    descricao   = Column(Text, nullable=True)
    fonte       = Column(Text, nullable=True)
    fetched_at  = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('EARNINGS_DATE','EX_DIVIDEND_DATE','DIVIDENDO','JCP','RESULTADO')",
            name="ck_eventos_corp_tipo",
        ),
        Index("ix_eventos_corp_ticker_data", "ticker", "data_evento"),
        Index("ix_eventos_corp_data", "data_evento"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "ticker": self.ticker,
            "tipo": self.tipo,
            "data_evento": self.data_evento.isoformat() if self.data_evento else None,
            "descricao": self.descricao,
            "fonte": self.fonte,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class MetricaComportamento(Base):
    """Cache de métricas comportamentais calculadas sob demanda (Fatia 8)."""
    __tablename__ = "metricas_comportamento"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    metrica        = Column(Text, nullable=False)
    bloco_ips      = Column(Text, nullable=True)
    periodo        = Column(Text, nullable=False)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fim    = Column(Date, nullable=False)
    valor_json     = Column(Text, nullable=True)
    calculado_em   = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_mc_metrica_periodo", "metrica", "periodo"),
        Index("ix_mc_calculado", "calculado_em"),
    )


class Cotacao(Base):
    """Histórico de cotações públicas — append-only log, sem UPDATE/DELETE.

    Múltiplas linhas por (ticker, date) são permitidas (cada fetch gera
    nova linha). A leitura usa MAX(fetched_at) para obter o valor vigente.
    """
    __tablename__ = "cotacoes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    preco = Column(Float, nullable=False)
    fetched_at = Column(DateTime, nullable=False)
    source = Column(Text, nullable=False, server_default="yfinance")

    __table_args__ = (
        Index("ix_cotacoes_ticker_date", "ticker", "date"),
    )


class MatrizSensibilidade(Base):
    """Sensibilidade macro→setor para a tool impacto_macro (Fatia 13)."""
    __tablename__ = "matriz_sensibilidade"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    indicador  = Column(Text, nullable=False)
    variacao   = Column(Text, nullable=False)
    setor      = Column(Text, nullable=False)
    direcao    = Column(Text, nullable=False)
    peso       = Column(Integer, nullable=False, default=2)
    logica     = Column(Text, nullable=True)
    criado_em  = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_matriz_ind_setor", "indicador", "setor"),
    )


class MemoriaAssistente(Base):
    """Memória de longo prazo extraída ou criada manualmente."""
    __tablename__ = "memorias_assistente"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    tipo        = Column(String(20), nullable=False)
    conteudo    = Column(Text, nullable=False)
    conversa_id = Column(Integer, ForeignKey("conversas.id", ondelete="SET NULL"), nullable=True)
    fonte       = Column(String(20), nullable=False, default="manual")
    criada_em   = Column(DateTime, nullable=False, default=datetime.utcnow)
    ativa       = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('estrategia','preferencia','decisao','meta','fato')",
            name="ck_memoria_tipo",
        ),
        CheckConstraint("fonte IN ('extraida','manual')", name="ck_memoria_fonte"),
        Index("ix_memorias_ativa", "ativa"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "conteudo": self.conteudo,
            "conversa_id": self.conversa_id,
            "fonte": self.fonte,
            "criada_em": self.criada_em.isoformat() if self.criada_em else None,
            "ativa": self.ativa,
        }
