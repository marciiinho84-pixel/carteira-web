"""
Prompts para extração de eventos por tipo de documento.

Cada função retorna (system_prompt, user_prompt).
O system_prompt é cacheado via cache_control para reduzir custos.
"""

_FORMATO_JSON = """
Retorne SOMENTE um JSON válido, sem nenhum texto antes ou depois. Formato:
{
  "eventos": [
    {
      "data": "YYYY-MM-DD",
      "ativo": "TICKER",
      "tipo": "TIPO_EVENTO",
      "qtd": 100.0,
      "preco": 25.50,
      "valor": 2550.00,
      "obs": "observação opcional"
    }
  ],
  "observacoes_gerais": "notas sobre o documento, dados ausentes, ambiguidades"
}

Tipos de evento válidos:
- COMPRA: compra de ativo (qtd, preco, valor obrigatórios)
- VENDA: venda de ativo (qtd, preco, valor obrigatórios)
- DIVIDENDO: dividendo recebido (valor obrigatório, qtd/preco opcionais)
- JCP: juros sobre capital próprio (valor obrigatório)
- RENDIMENTO: rendimento de RF (valor obrigatório)
- AMORTIZACAO: amortização de RF (valor obrigatório)
- BONIFICACAO: bonificação em ações (qtd obrigatório)
- CONTRIBUICAO: contribuição a fundo de previdência (valor obrigatório)
- APORTE_EXTERNO: aporte externo na carteira (valor obrigatório)
- RESGATE_EXTERNO: resgate da carteira (valor obrigatório)
- VENCIMENTO: vencimento de título RF (valor obrigatório)

Regras:
- Datas: sempre YYYY-MM-DD
- Valores monetários: float com ponto decimal (não vírgula)
- qtd e preco: null se não disponíveis
- ativo: use o ticker exato (ex: PETR4, VALE3, RENDA+2084, LCI-CEF-2025)
- Se houver dúvida sobre um campo, inclua nota em obs
- NÃO inclua eventos duplicados
- Se não encontrar eventos, retorne {"eventos": [], "observacoes_gerais": "..."}
"""

_SYSTEM_BASE = (
    "Você é um especialista em extração de dados financeiros de extratos e documentos de investimento brasileiros. "
    "Sua tarefa é extrair eventos de investimento de documentos e retorná-los em formato JSON estruturado. "
    "Seja preciso com datas, valores e tipos de evento. "
    "Sempre responda SOMENTE com JSON válido."
)


def get_prompt_b3_custodia() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato de Custódia B3.\n" + _FORMATO_JSON
    user = (
        "Extraia todos os ativos em custódia deste extrato B3. "
        "Para cada posição, crie um evento SALDO_INICIAL com a data do extrato, ticker, quantidade e valor. "
        "Se houver movimentações recentes, extraia também como COMPRA/VENDA/DIVIDENDO conforme o tipo."
    )
    return system, user


def get_prompt_b3_movimentacoes() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato de Movimentações B3.\n" + _FORMATO_JSON
    user = (
        "Extraia todas as movimentações deste extrato B3. "
        "Cada linha de movimentação deve virar um evento. "
        "Tipos comuns: compra/venda de ações, recebimento de dividendos, JCP, bonificação, desdobramento. "
        "Use os tickers exatos como aparecem no documento (ex: PETR4, VALE3, BBAS3)."
    )
    return system, user


def get_prompt_caixa_rv() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Nota de Corretagem ou Extrato de Renda Variável Caixa Econômica Federal.\n" + _FORMATO_JSON
    user = (
        "Extraia todas as operações de renda variável deste documento da Caixa Econômica. "
        "Identifique compras, vendas, dividendos e JCP. "
        "Use os tickers exatos conforme aparecem no documento."
    )
    return system, user


def get_prompt_funcef() -> tuple[str, str]:
    system = (
        "Você é um especialista em análise de extratos da FUNCEF (Fundação dos Economiários Federais). "
        "Sua tarefa é extrair SOMENTE três informações específicas deste extrato e retorná-las em JSON estruturado. "
        "Sempre responda SOMENTE com JSON válido, sem texto antes ou depois."
    )
    user = """Analise este extrato da FUNCEF e extraia EXATAMENTE as seguintes informações:

1. **Cota mais recente** — seção "Valorização da Cota Patrimonial do Plano":
   - Data e valor da cota do MÊS MAIS RECENTE listado

2. **Saldo atual** — seção "Saldo nas SubContas" ou equivalente:
   - Valor total em R$ (soma de todas as subcontas)
   - Quantidade total de cotas

3. **Contribuição do mês mais recente** — seção de contribuições/movimentações:
   - Identificar qual é o mês mais recente com lançamento
   - Somar TODAS as contribuições daquele único mês (participante + patrocinadora)
   - Criar 1 único evento consolidado para esse mês
   - NÃO retornar contribuições de meses anteriores

IMPORTANTE: NÃO extraia histórico de contribuições passadas. O sistema já tem o histórico.
Retorne SOMENTE o JSON abaixo, preenchido com os dados encontrados:

{
  "documento": {
    "tipo": "funcef",
    "titular": "nome do titular se disponível",
    "competencia": "YYYY-MM"
  },
  "cota_atual": {
    "data": "YYYY-MM-DD",
    "valor": 0.0
  },
  "saldo_atual": {
    "valor_real": 0.0,
    "quantidade_cotas": 0.0
  },
  "contribuicao_mes": {
    "data": "YYYY-MM-DD",
    "ativo": "FUNCEF",
    "tipo": "CONTRIBUICAO",
    "qtd": 0.0,
    "valor": 0.0,
    "obs": "Contribuição consolidada do mês YYYY/MM (participante + patrocinadora)"
  },
  "observacoes": "campo livre para anotar dúvidas ou dados ausentes"
}

Se algum campo não estiver disponível no documento, use null."""
    return system, user


def get_prompt_caixa_lci() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato de LCI (Letra de Crédito Imobiliário) Caixa Econômica Federal.\n" + _FORMATO_JSON
    user = (
        "Extraia as operações desta LCI da Caixa. "
        "Aplicação inicial: tipo COMPRA com ticker identificando o produto (ex: LCI-CEF-MMYYYY), data, valor e quantidade (cotas ou valor nominal). "
        "Rendimentos creditados: tipo RENDIMENTO com data e valor. "
        "Resgate/vencimento: tipo VENCIMENTO ou RESGATE_EXTERNO com data e valor."
    )
    return system, user


def get_prompt_caixa_ouro() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato de Ouro (BM&F/Caixa Econômica Federal).\n" + _FORMATO_JSON
    user = (
        "Extraia as operações de ouro deste documento. "
        "Use ticker='OURO' para todas as operações. "
        "Compras: tipo COMPRA com quantidade em gramas, preço por grama e valor total. "
        "Vendas: tipo VENDA. "
        "Saldo: tipo SALDO_INICIAL com quantidade em gramas e valor total."
    )
    return system, user


def get_prompt_caixa_fic_func() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato de Fundo de Investimento (FIC FUNC) Caixa Econômica Federal.\n" + _FORMATO_JSON
    user = (
        "Extraia as operações deste fundo de investimento da Caixa. "
        "Use o ticker exato do fundo conforme aparece no documento. "
        "Aplicações: tipo COMPRA com quantidade de cotas, valor da cota e valor total. "
        "Resgates: tipo VENDA. "
        "Rendimentos: tipo RENDIMENTO."
    )
    return system, user


def get_prompt_tesouro_direto() -> tuple[str, str]:
    system = _SYSTEM_BASE + "\n\nDocumento: Extrato do Tesouro Direto.\n" + _FORMATO_JSON
    user = (
        "Extraia todas as operações deste extrato do Tesouro Direto. "
        "Para cada título identifique: nome completo (ex: 'Tesouro Renda+ Aposentadoria Extra 2084'), "
        "data de vencimento, e operações (compra/venda/rendimento/vencimento). "
        "Use tickers no formato: RENDA+2084, IPCA+2035, SELIC2029, PREFIXADO2027, etc. "
        "Compras: tipo COMPRA com quantidade de títulos, PU e valor. "
        "Vendas/resgates: tipo VENDA. "
        "Vencimento: tipo VENCIMENTO."
    )
    return system, user


PROMPTS = {
    "b3_custodia": get_prompt_b3_custodia,
    "b3_movimentacoes": get_prompt_b3_movimentacoes,
    "caixa_rv": get_prompt_caixa_rv,
    "funcef": get_prompt_funcef,
    "caixa_lci": get_prompt_caixa_lci,
    "caixa_ouro": get_prompt_caixa_ouro,
    "caixa_fic_func": get_prompt_caixa_fic_func,
    "tesouro_direto": get_prompt_tesouro_direto,
}

_PROMPT_GENERICO_SYSTEM = _SYSTEM_BASE + "\n\nDocumento: extrato financeiro genérico.\n" + _FORMATO_JSON
_PROMPT_GENERICO_USER = (
    "Extraia todos os eventos de investimento que encontrar neste documento. "
    "Identifique compras, vendas, rendimentos, dividendos e outros eventos financeiros."
)


def get_prompt_auto() -> tuple[str, str]:
    """
    Prompt mestre para detecção automática de tipo + extração em uma única chamada.
    Claude primeiro identifica o tipo, depois aplica o schema correto.
    """
    system = (
        "Você é um especialista em análise de documentos financeiros brasileiros. "
        "Você vai identificar o tipo do documento E extrair os dados relevantes em uma única resposta JSON. "
        "Sempre responda SOMENTE com JSON válido, sem texto antes ou depois."
    )
    user = """Analise este documento financeiro e execute em duas etapas:

ETAPA 1 — IDENTIFICAÇÃO:
Classifique o documento em um destes tipos:
- "b3_custodia": extrato de posição em custódia da B3
- "b3_movimentacoes": extrato de movimentações/negociações da B3
- "caixa_rv": nota de corretagem ou extrato RV da Caixa Econômica
- "funcef": extrato da FUNCEF (Fundação dos Economiários Federais)
- "caixa_lci": extrato de LCI da Caixa Econômica
- "caixa_ouro": extrato de ouro (BM&F/Caixa)
- "caixa_fic_func": extrato de fundo FIC FUNC da Caixa
- "tesouro_direto": extrato do Tesouro Direto
- "desconhecido": nenhum dos anteriores

ETAPA 2 — EXTRAÇÃO:
Aplique as regras de extração conforme o tipo identificado:

• Para b3_custodia, b3_movimentacoes, caixa_rv, caixa_lci, caixa_ouro, caixa_fic_func, tesouro_direto:
  Extraia eventos no array "eventos" com campos: data (YYYY-MM-DD), ativo (ticker), tipo, qtd, preco, valor, obs.
  Tipos válidos: SALDO_INICIAL, COMPRA, VENDA, DIVIDENDO, JCP, RENDIMENTO, AMORTIZACAO, BONIFICACAO, CONTRIBUICAO, APORTE_EXTERNO, RESGATE_EXTERNO, VENCIMENTO
  Valores monetários: float com ponto decimal. qtd/preco: null se indisponíveis.

• Para funcef (regras especiais):
  - NÃO extraia contribuições históricas — apenas a do mês mais recente
  - "eventos": array com 1 evento CONTRIBUICAO consolidando o mês mais recente
  - "dados_extras.funcef.cota_atual": {data, valor} — cota patrimonial mais recente
  - "dados_extras.funcef.saldo_atual": {valor_real, quantidade_cotas} — saldo total

• Para desconhecido:
  - "eventos": tente extrair o que for possível no formato padrão
  - "dados_extras": {}

RETORNE EXATAMENTE este JSON (preencha os campos conforme o tipo):

{
  "tipo_identificado": "um dos tipos acima",
  "confianca": "alta|media|baixa",
  "justificativa": "1-2 frases explicando a identificação",
  "eventos": [],
  "dados_extras": {},
  "observacoes": "dados ausentes, ambiguidades ou avisos"
}"""
    return system, user


def get_prompt(tipo_documento: str) -> tuple[str, str]:
    """Retorna (system_prompt, user_prompt) para o tipo dado. Usa genérico se não reconhecido."""
    if tipo_documento == "auto":
        return get_prompt_auto()
    fn = PROMPTS.get(tipo_documento)
    if fn:
        return fn()
    return _PROMPT_GENERICO_SYSTEM, _PROMPT_GENERICO_USER
