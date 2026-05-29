"""
Schemas Pydantic para request/response da API.
Todos os tipos espelham as estruturas do engine — sem lógica própria.
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, field_validator


# ─── Ativos ──────────────────────────────────────────────────────

class AtivoOut(BaseModel):
    ticker: str
    classe: Optional[str] = None
    familia: Optional[str] = None
    setor: Optional[str] = None
    indexador: Optional[str] = None
    benchmark: Optional[str] = None
    liquidez: Optional[str] = None
    risco: Optional[str] = None
    composite: str
    observacao: Optional[str] = None
    data_vencimento: Optional[date] = None


class AtivoCreate(BaseModel):
    ticker: str
    classe: Optional[str] = None
    familia: Optional[str] = None
    setor: Optional[str] = None
    indexador: Optional[str] = None
    benchmark: Optional[str] = None
    liquidez: Optional[str] = None
    risco: Optional[str] = None
    composite: str = "Gerida"
    observacao: Optional[str] = None
    data_vencimento: Optional[date] = None

    @field_validator("composite")
    @classmethod
    def composite_valido(cls, v):
        if v not in ("Gerida", "FUNCEF"):
            raise ValueError("composite deve ser 'Gerida' ou 'FUNCEF'")
        return v


class AtivoUpdate(BaseModel):
    classe: Optional[str] = None
    familia: Optional[str] = None
    setor: Optional[str] = None
    indexador: Optional[str] = None
    benchmark: Optional[str] = None
    liquidez: Optional[str] = None
    risco: Optional[str] = None
    composite: Optional[str] = None
    observacao: Optional[str] = None
    data_vencimento: Optional[date] = None

    @field_validator("composite")
    @classmethod
    def composite_valido(cls, v):
        if v is not None and v not in ("Gerida", "FUNCEF"):
            raise ValueError("composite deve ser 'Gerida' ou 'FUNCEF'")
        return v


# ─── Eventos ─────────────────────────────────────────────────────

TIPOS_VALIDOS = {
    "SALDO_INICIAL", "COMPRA", "VENDA", "DIVIDENDO", "JCP",
    "RENDIMENTO", "AMORTIZACAO", "BONIFICACAO", "CONTRIBUICAO",
    "APORTE_EXTERNO", "RESGATE_EXTERNO", "VENCIMENTO",
    "RESGATE", "APORTE",
}


class EventoOut(BaseModel):
    id: int
    linha: int
    data: date
    ativo: str
    tipo: str
    qtd: Optional[float] = None
    preco: Optional[float] = None
    valor: float
    obs: Optional[str] = None


class EventoCreate(BaseModel):
    data: date
    ativo: str
    tipo: str
    qtd: Optional[float] = None
    preco: Optional[float] = None
    valor: float = 0.0
    obs: Optional[str] = ""

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v):
        if v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo inválido: '{v}'. Valores aceitos: {sorted(TIPOS_VALIDOS)}")
        return v


class EventoUpdate(BaseModel):
    data: Optional[date] = None
    ativo: Optional[str] = None
    tipo: Optional[str] = None
    qtd: Optional[float] = None
    preco: Optional[float] = None
    valor: Optional[float] = None
    obs: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def tipo_valido(cls, v):
        if v is not None and v not in TIPOS_VALIDOS:
            raise ValueError(f"tipo inválido: '{v}'")
        return v


# ─── Preços Manuais ───────────────────────────────────────────────

class PrecoManualOut(BaseModel):
    id: int
    data: date
    ticker: str
    valor: float
    fonte: Optional[str] = None


class PrecoManualCreate(BaseModel):
    data: date
    ticker: str
    valor: float
    fonte: Optional[str] = None


# ─── Resultados do Engine ─────────────────────────────────────────

class PosicaoOut(BaseModel):
    ticker: str
    classe: Optional[str] = None
    familia: Optional[str] = None
    composite: str
    qtd: float
    custo_total: float
    custo_medio: float
    preco_atual: Optional[float] = None
    valor_atual: float
    pnl: float
    pnl_pct: float
    var_dia: Optional[float] = None      # variação absoluta no dia (R$)
    var_dia_pct: Optional[float] = None  # variação percentual no dia
    yield_12m: Optional[float] = None    # yield projetado 12m (fração)


class VendaOut(BaseModel):
    data: date
    ticker: str
    qtd_vendida: float
    preco_venda: Optional[float] = None
    custo_medio: float
    valor_recebido: float
    pnl: float
    pnl_pct: float


class EvolucaoDiariaOut(BaseModel):
    data: date
    patrimonio_gerida: float
    patrimonio_funcef: float
    patrimonio_total: float
    patrimonio_rv: float
    twr_gerida: float
    twr_total: float
    twr_rv: float
    cdi_acum: float
    ipca_acum: float
    ibov_acum: float
    sp500_brl_acum: float
    drawdown: Optional[float] = None


class AlertaOut(BaseModel):
    nivel: str
    ativo: str
    mensagem: str


class StatusOut(BaseModel):
    calculado_em: Optional[str] = None
    data_referencia: Optional[str] = None
    n_eventos: int = 0
    n_ativos: int = 0
    alertas: List[AlertaOut] = []
    erro: Optional[str] = None


class DashboardOut(BaseModel):
    patrimonio_total: float
    patrimonio_gerida: float
    patrimonio_funcef: float
    patrimonio_rv: float
    twr_gerida_ytd: float
    twr_total_ytd: float
    twr_rv_ytd: float
    cdi_ytd: float
    ibov_ytd: float
    sp500_brl_ytd: float
    excesso_cdi: float
    sharpe: float
    pnl_vendas_rv: float
    n_alertas: int
    alertas: List[AlertaOut] = []
    var_dia: Optional[float] = None
    var_dia_pct: Optional[float] = None
    var_mercado_dia: Optional[float] = None   # variação de mercado pura (ex-fluxos externos)
    fluxo_dia: Optional[float] = None         # APORTE_EXTERNO − RESGATE_EXTERNO no dia
    drawdown_max: Optional[float] = None
    drawdown_max_data: Optional[str] = None
    vol_anualizada: Optional[float] = None   # volatilidade anualizada da Gerida
    beta_ibov: Optional[float] = None        # beta da Gerida vs IBOV
    yield_12m: Optional[float] = None        # yield projetado 12m do portfolio (fração)
    yield_12m_gerida: Optional[float] = None # yield sobre só patrimônio_gerida
    renda_anual_est: Optional[float] = None  # renda anual estimada em R$
    proventos_30d: Optional[float] = None    # renda estimada nos próximos 30 dias
    vencimentos_rf: List[dict] = []          # ativos RF com data_vencimento


class MetaOut(BaseModel):
    patrimonio_atual: float
    twr_anualizado: float
    aporte_anual: float
    meta: float
    projecao: List[dict] = []


class AtribuicaoOut(BaseModel):
    mes: str
    composite: str
    ativo: str
    retorno_ativo: float
    peso_medio: float
    contribuicao: float
    benchmark: Optional[str] = None


class CarteiraRVOut(BaseModel):
    caixa_atual: float
    entrando_5d: float
    saindo_5d: float
    saldo_projetado: float
    pendentes: List[dict] = []
    setores: List[dict] = []
    twr_rv: float
    ibov_ytd: float
    sp500_brl_ytd: float
