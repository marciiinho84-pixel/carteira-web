"""
MCP Server — Carteira Clean

Expõe ferramentas de consulta à carteira via protocolo MCP (streamable-http).
Porta padrão: 8001

Uso:
    python3 -m carteira_clean_web.backend.mcp.server
"""

from fastmcp import FastMCP
from carteira_clean_web.backend.mcp.tools.portfolio import (
    fn_obter_posicoes, fn_obter_performance, fn_obter_cotacao,
    fn_atribuicao,
)

mcp = FastMCP(
    name="Carteira Clean",
    instructions="""
    Você tem acesso aos dados reais da carteira de investimentos
    do Marcio de Almeida Souza. Use as ferramentas disponíveis
    para responder perguntas sobre o portfólio com precisão.
    Nunca invente ou estime dados financeiros — use sempre
    as ferramentas.
    """,
)


@mcp.tool(
    description="""
    Retorna todas as posições ativas da carteira com:
    - Valor atual, custo médio e P&L de cada posição
    - Alocação percentual por ativo e por classe
    - Resumo agregado por classe de ativo
    - Alertas automáticos sobre concentração

    Use esta ferramenta quando o usuário perguntar sobre:
    posições, portfólio, o que tenho, quanto vale, alocação,
    diversificação, concentração, maior posição, P&L.
    """
)
def obter_posicoes() -> dict:
    return fn_obter_posicoes()


@mcp.tool(
    description="""
    Retorna a performance (rentabilidade) da carteira no
    período solicitado, comparada com CDI e IBOV.

    Parâmetros:
    - periodo: "ytd" (ano atual), "1m", "3m", "6m", "1a"
    - benchmark: "CDI", "IBOV" ou "ambos" (padrão)

    Use quando o usuário perguntar sobre:
    rentabilidade, performance, retorno, quanto rendeu,
    estou ganhando do CDI, comparação com mercado,
    drawdown, dias positivos, resultado do período.
    """
)
def obter_performance(periodo: str = "ytd", benchmark: str = "ambos") -> dict:
    return fn_obter_performance(periodo, benchmark)


@mcp.tool(
    description="""
    Busca a cotação atual de qualquer ativo financeiro e
    cruza com a posição do usuário na carteira.

    Parâmetro:
    - ticker: código do ativo (ex: "WEGE3", "MSFT34",
      "BURA39", "MSFT" para o ativo americano original)

    Para ativos brasileiros e BDRs, use o código sem .SA
    (ex: "WEGE3", não "WEGE3.SA"). Para ativos americanos
    originais, use o código em inglês (ex: "MSFT").

    Use quando o usuário perguntar sobre:
    cotação, preço atual, quanto está valendo, variação
    do dia, quanto rendeu hoje, máxima/mínima do ano,
    está acima/abaixo do meu preço médio.
    """
)
def obter_cotacao(ticker: str) -> dict:
    return fn_obter_cotacao(ticker)


@mcp.tool(
    description="""
    Retorna a atribuição mensal de performance da carteira:
    quais ativos contribuíram (positiva ou negativamente) para o retorno.

    Parâmetros opcionais:
    - mes: "YYYY-MM" (ex: "2026-05"). Sem filtro → todos os meses.
    - composite: "Gerida", "FUNCEF" ou "TOTAL_CARTEIRA".
    - bloco_ips: "SWING_TRADE", "GROWTH", "RENDA_FIXA", "DEFENSIVOS" ou "FORA_IPS".

    Inclui linhas TOTAL por composite (retorno ponderado do bloco) e
    TOTAL_CARTEIRA (retorno total da carteira no mês).

    Use quando o usuário perguntar sobre:
    quais ativos contribuíram mais, performance por bloco IPS,
    atribuição de retorno, o que puxou a carteira para cima/baixo,
    como foi o bloco Growth este mês, contribuição de cada ativo.
    """
)
def obter_atribuicao(
    mes: str = None,
    composite: str = None,
    bloco_ips: str = None,
) -> dict:
    return fn_atribuicao(mes, composite, bloco_ips)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
