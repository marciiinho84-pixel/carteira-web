from pydantic import BaseModel
from typing import Optional


class PorClasse(BaseModel):
    valor: float
    pct: float


class Resumo(BaseModel):
    por_classe: dict[str, PorClasse]
    total_posicoes_ativas: int
    pl_total_reais: float
    pl_total_pct: float


class Posicao(BaseModel):
    ticker: str
    nome: str
    classe: str
    setor: str
    composite: str
    qtd: float
    preco_atual: float
    valor_atual: float
    custo_medio: Optional[float]
    pl_percentual: Optional[float]
    pl_reais: Optional[float]
    pct_carteira: float
    maior_posicao: bool


class ResultadoPosicoes(BaseModel):
    data_referencia: str
    patrimonio_total: float
    resumo: Resumo
    posicoes: list[Posicao]
    alertas: list[str]


class RetornoBenchmark(BaseModel):
    retorno_pct: float
    alpha_pct: float
    ganhando: bool


class Risco(BaseModel):
    drawdown_max_pct: float
    dias_positivos: int
    dias_negativos: int


class ResultadoPerformance(BaseModel):
    periodo: str
    periodo_efetivo: str
    data_inicio: str
    data_fim: str
    dias_uteis: int
    twr_gerida_pct: float
    benchmarks: dict[str, RetornoBenchmark]
    risco: Risco
