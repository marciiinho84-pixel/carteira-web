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
    fn_atribuicao, fn_brinson, fn_analise_aderencia_setorial,
    fn_obter_diario, fn_obter_sinais, fn_obter_fundamentos,
    fn_obter_watchlist, fn_obter_analise_rv, fn_consultar_fundamentos,
    fn_consultar_teses, fn_consultar_diario_decisoes,
    fn_risco_carteira, fn_disciplina_caixa,
    fn_consultar_macro, fn_consultar_eventos_corporativos,
    fn_perfil_comportamental, fn_divergencias_dito_feito,
    fn_vieses_comportamentais,
    fn_analise_fundamentalista, fn_screening_fundamentalista, fn_comparar_multiplos,
    fn_contexto_setorial, fn_regime_mercado,
    fn_analise_tecnica, fn_grafico_tecnico,
    fn_noticias_ativos, fn_impacto_macro,
    fn_consultar_glossario,
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


@mcp.tool(
    description="""
    Retorna a decomposição Brinson-Fachler da carteira Gerida:
    quanto do excesso de retorno (vs benchmark IPS) veio de
    ALOCAÇÃO (apostas táticas nos blocos) vs SELEÇÃO (escolha de ativos).

    Benchmark IPS composto: 30%IBOV + 20%NasdaqBRL + 20%OuroBRL + 30%CDI.
    Blocos IPS: SWING_TRADE (alvo 30%, bench IBOV),
                GROWTH (alvo 20%, bench NasdaqBRL),
                DEFENSIVOS (alvo 20%, bench OuroBRL),
                RENDA_FIXA (alvo 30%, bench CDI).

    Parâmetros opcionais:
    - mes: "YYYY-MM". Sem filtro → todos os meses disponíveis.
    - bloco_ips: filtrar por bloco específico ou "TOTAL".

    Use quando o usuário perguntar sobre:
    excesso de retorno, alpha, de onde veio a performance,
    efeito alocação, efeito seleção, apostei bem nos setores?,
    o Growth contribuiu positivamente?, estou batendo o benchmark?,
    Brinson, decomposição de performance.
    """
)
def obter_brinson(
    mes: str = None,
    bloco_ips: str = None,
) -> dict:
    return fn_brinson(mes, bloco_ips)


@mcp.tool(
    description="""
    Analisa a aderência setorial da Carteira Gerida à IPS v1.0.

    Cruza duas lentes:
    - Espelho (Peça B): exposição real por bloco IPS vs. alvos e bandas da IPS
      (Swing Trade 30% ±10pp, Growth 20% ±10pp, Defensivos 20% ±5pp, Renda Fixa 30% ±5pp).
      Detalha os setores que compõem cada bloco.
    - Janela (Peça A): desempenho recente (último mês) dos índices setoriais B3
      correspondentes a cada setor (IEE, UTIL, ICON, IFNC, IMOB, INDX, AGFS, IMAT).

    Todo número retornado é rastreável: vem do cache da carteira ou da tabela
    de índices — nada é estimado pelo modelo.

    Use quando o usuário perguntar sobre:
    alocação por bloco, aderência à IPS, estou dentro da banda?,
    qual bloco está fora do alvo, concentração setorial, bloco Growth acima do limite,
    como está o Swing Trade vs. IPS, setor X está pesando muito, aderência setorial.
    """
)
def analise_aderencia_setorial() -> dict:
    return fn_analise_aderencia_setorial()


@mcp.tool(
    description="""
    Retorna anotações de estratégia e decisões do diário do investidor.

    Parâmetros opcionais:
    - periodo: "7d", "30d" (padrão), "90d" ou "all"
    - busca: texto livre para filtrar entradas (pesquisa no conteúdo e no ticker)
    - ticker: filtrar entradas que mencionam especificamente este ticker

    Use quando o usuário perguntar sobre:
    estratégias registradas, decisões anteriores, planos, teses de compra/venda,
    histórico de decisões, o que decidi sobre X, quando comprei Y, minhas notas.
    """
)
def obter_diario(
    periodo: str = "30d",
    busca: str = None,
    ticker: str = None,
) -> dict:
    return fn_obter_diario(periodo=periodo, busca=busca, ticker=ticker)


@mcp.tool(
    description="""
    Retorna sinais técnicos (RSI, MACD, Médias Móveis) e indicadores
    fundamentalistas (P/L, P/VP, ROE, EV/EBITDA, Margem Líq., Dív/EBITDA)
    para os ativos da carteira ou lista específica.

    Parâmetros opcionais:
    - tickers: lista de tickers (ex: ["WEGE3", "ITUB4"]). Se vazio, usa todos
      os ativos de Renda Variável da carteira.
    - apenas_ativos: se true, retorna apenas ativos com sinal diferente de NEUTRO.

    Use quando o usuário perguntar sobre:
    análise técnica, RSI, MACD, médias móveis, sinais de compra/venda,
    fundamentos, P/L, ROE de ativos específicos ou da carteira geral.
    """
)
def obter_sinais(
    tickers: list[str] = None,
    apenas_ativos: bool = False,
) -> dict:
    return fn_obter_sinais(tickers=tickers, apenas_ativos=apenas_ativos)


@mcp.tool(
    description="""
    Retorna indicadores fundamentalistas detalhados (P/L, P/VP, EV/EBITDA,
    ROE, Margem Líquida, Dívida/EBITDA) para ativos da carteira ou lista.

    Parâmetro opcional:
    - tickers: lista de tickers. Se vazio, usa todos os ativos RV da carteira.

    Use quando o usuário quiser comparar múltiplos entre ativos, fazer triagem
    por fundamentos, ou análise fundamentalista focada sem sinais técnicos.
    Prefira obter_sinais quando quiser fundamentos + técnicos juntos.
    """
)
def obter_fundamentos(tickers: list[str] = None) -> dict:
    return fn_obter_fundamentos(tickers=tickers)


@mcp.tool(
    description="""
    Retorna a watchlist do investidor com cotações ao vivo, preço-alvo,
    stop-loss, distância percentual ao alvo e sinal (NA_ZONA / PROXIMO / ACIMA).

    Use quando o usuário perguntar sobre:
    ativos que está monitorando, watchlist, candidatos a compra,
    alvos de preço, qual ativo está próximo do alvo, stop-loss.
    """
)
def obter_watchlist() -> dict:
    return fn_obter_watchlist()


@mcp.tool(
    description="""
    ANÁLISE COMPLETA da carteira de Renda Variável.
    Combina em paralelo: posições RV + sinais técnicos + fundamentos + watchlist.

    Use quando o usuário pedir análise geral da carteira RV, avaliação de ativos,
    revisão de portfólio, ou qualquer análise que precise de múltiplos indicadores.
    PREFIRA esta tool a chamar obter_posicoes + obter_sinais separadamente.

    NÃO use para aderência à IPS ou concentração por bloco — use
    analise_aderencia_setorial para isso.
    """
)
def obter_analise_rv() -> dict:
    return fn_obter_analise_rv()


@mcp.tool(
    description="""
    Retorna os indicadores fundamentalistas completos persistidos no banco de dados
    para os ativos da carteira ou lista específica de tickers.

    Indicadores disponíveis: P/L, P/VP, ROE, ROIC, DY (Dividend Yield),
    Margem EBITDA, Dívida Líquida/EBITDA, Margem Líquida, LPA, VPA.
    Inclui data de referência e quando os dados foram coletados.

    Parâmetro opcional:
    - tickers: lista de tickers. Se vazio, usa todos os ativos RV da carteira.

    ETFs e fundos retornam NULL para indicadores não aplicáveis (esperado).

    Use quando o usuário quiser:
    análise fundamentalista detalhada com todos os indicadores, comparar valuations,
    ver ROIC, dividend yield, ou LPA/VPA de ativos da carteira.
    Prefira obter_sinais para uma visão técnica + fundamentalista combinada.
    """
)
def consultar_fundamentos(tickers: list[str] = None) -> dict:
    return fn_consultar_fundamentos(tickers)


@mcp.tool(
    description="""
    Retorna as teses de investimento ativas da carteira (ou de um ticker específico).

    Parâmetro opcional:
    - ticker: filtrar teses de um ativo específico.
      Sem ticker → retorna TODAS as teses com status ATIVA.

    Cada tese inclui: racional, critério de invalidação, nível de alerta
    (VERDE/AMARELO/VERMELHO), bloco IPS, data de criação e dias desde criação.

    Use quando o usuário perguntar sobre:
    teses de investimento, por que comprei X, critério de saída, nível de convicção,
    qual a tese do WEGE3, quais teses estão em alerta.
    """
)
def consultar_teses(ticker: str = None) -> dict:
    return fn_consultar_teses(ticker)


@mcp.tool(
    description="""
    Retorna o diário de decisões estruturado da carteira.

    Parâmetros opcionais:
    - ticker: filtrar decisões de um ativo específico.
    - periodo: "7d", "30d" (padrão: "90d"), "all".

    Inclui resultado_percentual calculado dinamicamente (preço de entrada vs. preço atual).

    Use quando o usuário perguntar sobre:
    decisões de compra/venda, histórico de operações, quando comprei, convicção,
    razão de uma decisão, cenário esperado, diário de operações.
    """
)
def consultar_diario(ticker: str = None, periodo: str = "90d") -> dict:
    return fn_consultar_diario_decisoes(ticker, periodo)


@mcp.tool(
    description="""
    Análise de risco ex-ante da Carteira Gerida.

    Parâmetro:
    - tipo: "exposicao" | "drawdown" | "liquidez" | "stress" | "todos" (padrão)

    Retorna conforme o tipo:
    - exposicao: % por bloco IPS, moeda (BRL/USD) e classe de ativo
    - drawdown: MDD YTD, 12m e desde início + duração da maior queda
    - liquidez: % disponível por prazo (D+0, D+3, D+30, D+30+) e alerta se <20% em D+3
    - stress: IBOV -20%, USD +30%, Selic +300bps — impactos estimados em R$ e %

    Use quando o usuário perguntar sobre:
    risco, exposição cambial, liquidez, drawdown, stress test, quanto perderia se IBOV cair,
    concentração em dólar, quanto tenho disponível para resgatar, beta da carteira.
    """
)
def risco_carteira(tipo: str = "todos") -> dict:
    return fn_risco_carteira(tipo)


@mcp.tool(
    description="""
    Monitoramento de caixa e disciplina de aportes.

    Retorna:
    - Caixa atual em R$ e % da Carteira Gerida
    - Status: SAUDAVEL | ELEVADO_TEMPORARIO (<6 sem) | REQUER_REVISAO (>6 sem)
    - Dias acima do limiar de 15%
    - Aporte realizado no mês atual vs. meta mensal (se regra cadastrada)
    - Regra de aporte ativa

    Use quando o usuário perguntar sobre:
    caixa, cash drag, quanto tenho parado, quanto aportei este mês, meta de aporte,
    preciso investir o caixa, estou dentro do plano de aportes.
    """
)
def disciplina_caixa() -> dict:
    return fn_disciplina_caixa()


@mcp.tool(
    description="""
    Retorna indicadores macro persistidos no banco (fonte: BCB SGS + Focus/Olinda).

    Indicadores disponíveis:
    - SELIC_META: taxa Selic meta (% a.a.) — BCB SGS 432
    - SELIC_DIARIA: CDI / Selic over (% a.d.) — BCB SGS 12
    - IPCA: inflação mensal (% a.m.) — BCB SGS 433
    - USD_BRL: câmbio USD/BRL PTAX — BCB SGS 1
    - IPCA_FOCUS: expectativa mediana IPCA anual (Focus) — BCB Olinda

    Parâmetros opcionais:
    - indicadores: lista de indicadores. None = todos.
    - ultimos_n: quantas observações por indicador (default 12)

    Use quando o usuário perguntar sobre:
    Selic, juros, IPCA, inflação, câmbio, dólar, Focus, expectativas de mercado,
    ambiente macro, cenário de juros, PTAX, CDI histórico.
    """
)
def consultar_macro(
    indicadores: list[str] = None,
    ultimos_n: int = 12,
) -> dict:
    return fn_consultar_macro(indicadores, ultimos_n)


@mcp.tool(
    description="""
    Retorna eventos corporativos futuros dos ativos da carteira.

    Inclui:
    - EARNINGS_DATE: próximas datas de divulgação de resultados
    - EX_DIVIDEND_DATE: próximas datas ex-dividendo

    Parâmetros opcionais:
    - ticker: filtrar por ativo específico (ex: "WEGE3"). None = todos.
    - janela_dias: horizonte em dias à frente (default 60)

    Fonte: yfinance.

    Use quando o usuário perguntar sobre:
    próximos resultados, divulgação de balanço, data ex-dividendo,
    agenda corporativa, quando sai o resultado de X, calendário de proventos.
    """
)
def consultar_eventos_corporativos(
    ticker: str = None,
    janela_dias: int = 60,
) -> dict:
    return fn_consultar_eventos_corporativos(ticker, janela_dias)


@mcp.tool(
    description="""
    Perfil comportamental do investidor, calculado sobre o event log histórico.

    Calcula (sem interpretar — fatos apenas):
    - turnover: giro real por bloco IPS (valor vendas / patrimônio do bloco)
    - holding: tempo médio de permanência nas posições por bloco IPS,
      comparado ao horizonte declarado na IPS
    - frequencia: operações por mês, tendência, picos (> média + 2σ)
    - concentracao: top-5 posições como % da Carteira Gerida + HHI

    Parâmetros:
    - metrica: "turnover" | "holding" | "frequencia" | "concentracao" | "todos"
    - periodo_meses: janela de análise (default 12 meses)

    Use quando o usuário perguntar sobre:
    meu perfil de investidor, giro da carteira, quanto tempo fico nas posições,
    frequência de operações, concentração, como me comporto, padrões de comportamento.
    """
)
def perfil_comportamental(
    metrica: str = "todos",
    periodo_meses: int = 12,
) -> dict:
    return fn_perfil_comportamental(metrica, periodo_meses)


@mcp.tool(
    description="""
    Cruzamento dito-vs-feito: divergências entre o que foi declarado
    (IPS, teses de investimento, diário de decisão) e o comportamento real.

    Retorna fatos — sem recomendações, sem juízo de valor.
    Cada divergência tem: descricao, fonte_dito, fonte_feito, severidade.
    Severidade: INFO | ATENCAO | CRITICO.

    4 cruzamentos disponíveis:
    - horizonte: horizonte declarado no IPS vs holding period real por bloco
    - alocacao: bandas IPS vs alocação real atual
    - conviccao: convicção registrada no diário vs resultado % real
    - invalidacao: teses com critério de invalidação atingido ou sem revisão

    Parâmetros:
    - tipo: "horizonte" | "alocacao" | "conviccao" | "invalidacao" | "todos"
    - periodo_meses: janela para padrões comportamentais (default 6 meses)

    Use quando o usuário perguntar sobre:
    dito vs feito, coerência, disciplina, estou seguindo a IPS,
    teses válidas, critério de invalidação, convicção vs resultado,
    quanto tempo fico nas posições vs o que planejei.
    """
)
def divergencias_dito_feito(
    tipo: str = "todos",
    periodo_meses: int = 6,
) -> dict:
    return fn_divergencias_dito_feito(tipo, periodo_meses)


@mcp.tool(
    description="""
    Detecta 5 vieses comportamentais a partir do histórico de operações.

    Vieses analisados (com fato mensurável):
    - disposition_effect: segura perdedores mais que ganhadores (ratio holding)
    - overtrading: giro excessivo em blocos de horizonte longo
    - subdiversificacao: concentração (HHI > 15 ou top-1 > 25%)
    - clustering_temporal: operações agrupadas em poucos meses
    - trend_chasing: compra após altas e obtém retorno inferior

    Retorna: detectado (true/false), fato_mensuravel, severidade, referencia_glossario.
    Use quando o usuário perguntar: vieses, padrões de comportamento, disposition effect,
    overtrading, estou concentrado demais, cluster de operações, trend chasing.
    """
)
def vieses_comportamentais(periodo_meses: int = 12) -> dict:
    return fn_vieses_comportamentais(periodo_meses)


@mcp.tool(
    description="""
    Análise fundamentalista em 4 dimensões para um ativo específico.

    Dimensões:
    - valuation: P/L, P/VP, EV/EBITDA vs peers do setor
    - rentabilidade: ROE, ROIC, margem EBITDA, margem líquida
    - saude_financeira: Dív.Líq/EBITDA
    - proventos: DY, LPA, VPA

    Compara o ativo com peers do mesmo setor cadastrados na carteira.
    Fonte: tabela fundamentos (yfinance — executar coleta antes).

    Parâmetro:
    - ticker: código do ativo (ex: "PETR4", "WEGE3")

    Use quando o usuário perguntar: P/L, ROE, fundamentos, análise fundamentalista,
    múltiplos, ROIC, DY, balanço, rentabilidade de [ativo].
    """
)
def analise_fundamentalista(ticker: str) -> dict:
    return fn_analise_fundamentalista(ticker)


@mcp.tool(
    description="""
    Filtra ativos da carteira por critérios fundamentalistas.

    Todos os critérios são opcionais — combine os que quiser.
    Parâmetros:
    - roe_min: ROE mínimo (%)
    - dy_min:  DY mínimo (%)
    - pl_max:  P/L máximo
    - div_liq_ebitda_max: Dív.Líq/EBITDA máximo
    - margem_ebitda_min:  Margem EBITDA mínima (%)

    Use quando o usuário perguntar: screening, quais ativos pagam mais dividendos,
    filtrar por ROE, baratos por P/L, menos endividados.
    """
)
def screening_fundamentalista(
    roe_min: float | None = None,
    dy_min: float | None = None,
    pl_max: float | None = None,
    div_liq_ebitda_max: float | None = None,
    margem_ebitda_min: float | None = None,
) -> dict:
    return fn_screening_fundamentalista(roe_min, dy_min, pl_max, div_liq_ebitda_max, margem_ebitda_min)


@mcp.tool(
    description="""
    Tabela comparativa de múltiplos fundamentalistas para 2 a 5 ativos side-by-side.

    Parâmetro:
    - tickers: lista de tickers (ex: ["PETR4", "PRIO3", "RRRP3"])

    Útil para comparar ações de um mesmo setor antes de decidir entre elas.
    Use quando o usuário perguntar: comparar fundamentos, qual está mais barato entre X e Y,
    P/L de PETR4 vs PRIO3.
    """
)
def comparar_multiplos(tickers: list[str]) -> dict:
    return fn_comparar_multiplos(tickers)


@mcp.tool(
    description="""
    Contexto setorial: performance recente do índice B3 (via taxonomia
    setorial brapi), quais indicadores macro são relevantes para cada
    setor e quais ativos da carteira estão nele.

    Parâmetro:
    - setor: código do índice (ex: "IFNC"), nome amigável (ex: "Bancos",
      "Imobiliário") ou "todos" (default)

    Use quando o usuário perguntar: contexto do setor, macro relevante para bancários,
    quais indicadores impactam construtoras, análise setorial, desempenho do setor X.
    """
)
def contexto_setorial(setor: str = "todos") -> dict:
    return fn_contexto_setorial(setor)


@mcp.tool(
    description="""
    Classifica o regime macroeconômico atual em 4 eixos:
    juros (subindo/estável/caindo), inflação (acelerando/controlada/desacelerando),
    câmbio (depreciação/estável/apreciação), indicando o valor atual de cada.

    Dados: BCB SGS + Focus (já coletados na tabela macro_indicadores).

    Use quando o usuário perguntar: regime de mercado, como está a macro,
    cenário atual, Selic subindo ou caindo, inflação controlada.
    """
)
def regime_mercado() -> dict:
    return fn_regime_mercado()


@mcp.tool(
    description="""
    Análise técnica com sistema de votação para um ativo.

    Indicadores calculados:
    - Médias móveis: MM20, MM50, MM200
    - Osciladores: RSI 14, MACD (12,26,9), Bollinger (20,2)
    - Suportes e resistências (pivôs de preço)

    Sistema de votação: cada indicador vota -1/0/+1.
    rating_geral: média ponderada (−1 = venda forte, +1 = compra forte).

    Também retorna: entrada sugerida, alvo, stop, tendencia.

    Parâmetros:
    - ticker: código do ativo (ex: "PETR4", "WEGE3")
    - periodo: "1mo" | "3mo" | "6mo" | "1y" | "2y" (default "6mo")

    Use quando o usuário perguntar: análise técnica, suporte, resistência, RSI,
    MACD, médias móveis, tendência de [ativo], setup técnico.
    """
)
def analise_tecnica(ticker: str, periodo: str = "6mo") -> dict:
    return fn_analise_tecnica(ticker, periodo)


@mcp.tool(
    description="""
    Gera gráfico candlestick interativo (Plotly HTML) com MMs, Bollinger,
    suportes/resistências, volume e RSI em subplots separados.

    Salva o arquivo em /data/charts/ e retorna o caminho.

    Parâmetros:
    - ticker: código do ativo
    - periodo: "1mo" | "3mo" | "6mo" | "1y" | "2y" (default "6mo")

    Use quando o usuário perguntar: mostrar gráfico, gráfico técnico, chart de [ativo],
    ver candlestick, quero ver o gráfico.
    """
)
def grafico_tecnico(ticker: str, periodo: str = "6mo") -> dict:
    return fn_grafico_tecnico(ticker, periodo)


@mcp.tool(
    description="""
    Retorna notícias recentes dos ativos via yfinance.

    Parâmetros:
    - ticker: código do ativo (ex: "PETR4"), "carteira" (top-10 por patrimônio),
              ou "watchlist" (default: "carteira")
    - dias: janela em dias (default 7, máx recomendado 30)

    Use quando o usuário perguntar: notícias de [ativo], o que está acontecendo com [ativo],
    novidades da carteira, notícias da semana, últimas notícias.
    """
)
def noticias_ativos(ticker: str = "carteira", dias: int = 7) -> dict:
    return fn_noticias_ativos(ticker, dias)


@mcp.tool(
    description="""
    Avalia o impacto de um evento macro nos ativos da carteira.

    Consulta a matriz de sensibilidade macro→setor e identifica quais ativos
    em carteira são afetados positiva ou negativamente.

    Parâmetros (escolha um dos dois modos):
    Modo 1 — texto livre:
    - evento: descrição do evento (ex: "queda de 0.5pp na Selic")
              (indicador e variação são inferidos automaticamente)
    Modo 2 — estruturado:
    - indicador: "SELIC_META" | "USD_BRL" | "IPCA"
    - variacao:  "ALTA" | "QUEDA"

    Use quando o usuário perguntar: impacto da Selic na carteira, o que muda se o dólar subir,
    como o IPCA afeta meus ativos, análise macro, impacto de [evento] nos meus papéis.
    """
)
def impacto_macro(
    evento: str = "",
    indicador: str = "",
    variacao: str = "QUEDA",
) -> dict:
    return fn_impacto_macro(evento, indicador, variacao)


@mcp.tool(
    description="""
    Consulta o glossário de indicadores e conceitos de investimento.

    Cobre: indicadores fundamentalistas (P/L, ROE, ROIC, DY…),
    técnicos (RSI, MACD, Bollinger, suporte, resistência…) e
    vieses comportamentais (disposition effect, overtrading…).

    Parâmetros (escolha um):
    - termo: busca por nome/código (ex: "P/L", "RSI", "disposition effect", "overtrading")
    - categoria: "fundamentalista" | "tecnico" | "comportamental" — lista todos

    Use quando o usuário perguntar: o que é [indicador], explica [conceito],
    o que significa P/L, o que é RSI, o que é disposition effect.
    """
)
def consultar_glossario(termo: str = "", categoria: str = "") -> dict:
    return fn_consultar_glossario(termo, categoria)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001)
