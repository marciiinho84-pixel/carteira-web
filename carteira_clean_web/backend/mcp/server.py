"""
MCP Server — Carteira Clean

Expõe ferramentas de consulta à carteira via protocolo MCP (streamable-http).
Porta padrão: 8001

Uso:
    python3 -m carteira_clean_web.backend.mcp.server
"""

from fastmcp import FastMCP
from carteira_clean_web.backend.mcp.tools.portfolio import fn_obter_posicoes, fn_obter_performance

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


if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
