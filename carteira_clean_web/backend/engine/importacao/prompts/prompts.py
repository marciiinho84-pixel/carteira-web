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
        "Sua tarefa é extrair dados financeiros com precisão absoluta. "
        "NUNCA invente valores, NUNCA aproxime, NUNCA some linhas — o sistema Python fará as somas. "
        "Se algum campo não estiver claro no documento, retorne null e explique em observacoes. "
        "Sempre responda SOMENTE com JSON válido, sem texto antes ou depois."
    )
    user = """Analise este extrato da FUNCEF seguindo RIGOROSAMENTE as instruções abaixo em ordem.

═══════════════════════════════════════════
PASSO 1 — ENUMERAR E FILTRAR COMPETÊNCIAS
═══════════════════════════════════════════
1a) Liste TODAS as competências que aparecem na tabela de contribuições. Exemplos: "2026/01", "2026/04", "2026/13".
    Registre-as em debug.competencias_encontradas.

1b) CLASSIFICAÇÃO OBRIGATÓRIA:
    ✅ Competência REGULAR: MM está entre 01 e 12 (janeiro a dezembro)
    ❌ Competência IGNORAR: MM = 13 → décimo-terceiro salário. NÃO É UM MÊS DO CALENDÁRIO.
       Tratar /13 exatamente como se não existisse. Não mencionar, não referenciar.

1c) Das competências REGULARES (MM ∈ {01..12}), selecione aquela com o MAIOR valor numérico de MM.
    Se houver empate de MM em anos diferentes, prefira o ano mais recente.
    Esse é o "competencia_referencia". Converta para formato YYYY-MM.

    EXEMPLO CORRETO: se o extrato tem 2026/01, 2026/02, 2026/03, 2026/04, 2026/13
    → competencias_encontradas = ["2026/01","2026/02","2026/03","2026/04","2026/13"]
    → competencias_regulares   = ["2026/01","2026/02","2026/03","2026/04"]  (13 excluído)
    → competencia_referencia   = "2026-04"  (MM=04 é o maior entre {01,02,03,04})

═══════════════════════════════════════════
PASSO 2 — LISTAR LINHAS INDIVIDUAIS (NÃO SOMAR)
═══════════════════════════════════════════
Para a competencia_referencia do Passo 1, identifique CADA linha que atenda TODOS estes critérios:
  ✅ Descrição começa com "Normal -" (ex: "Normal - Participante", "Normal - Patrocinador", "Normal Patrocinador - Excedente")
  ✅ Valor positivo (maior que zero)
  ✅ Competência == competencia_referencia exata (não misture outros meses)

IGNORAR obrigatoriamente:
  ❌ Qualquer linha com competência /13
  ❌ Linhas com "Acerto de Custeio Administrativo" (qualquer variação)
  ❌ Linhas com valor negativo ou zero
  ❌ Linhas de qualquer outra competência

Para CADA linha aprovada, registre UM objeto em "linhas_competencia" com:
  • "historico": texto exato da coluna Histórico/Descrição
  • "valor_contribuicao": valor da coluna "Valor da Contribuição" (float)
  • "credito_subconta": valor da coluna "Crédito na Subconta" (float)
  • "cotas": valor da coluna "Crédito na Subconta em Cotas" (float)

⛔ PROIBIDO ABSOLUTAMENTE:
  - Calcular qualquer total (valor_liquido_total, qtd_cotas_total, somas, etc.)
  - Colocar valores somados no JSON
  - Fazer qualquer aritmética entre as linhas
  O sistema Python calculará os totais — você só coleta as linhas individuais com precisão.

═══════════════════════════════════════════
PASSO 3 — VALOR DA COTA DO MÊS
═══════════════════════════════════════════
Na seção "Valorização da Cota Patrimonial do Plano", localize a cota do mês competencia_referencia.
Registre apenas o valor em validacao.cota_historico. Não calcule cota_calculada — o Python fará isso.

═══════════════════════════════════════════
PASSO 4 — HISTÓRICO COMPLETO DE COTAS
═══════════════════════════════════════════
Na seção "Valorização da Cota Patrimonial do Plano", extraia TODAS as linhas listadas.
Para cada linha: competência (YYYY-MM), data (YYYY-MM-DD) e valor da cota (float).
Ordene do mais antigo para o mais recente.

═══════════════════════════════════════════
PASSO 5 — SALDO ATUAL
═══════════════════════════════════════════
Na seção "Saldo nas SubContas" ou equivalente:
  - valor_real: soma total em R$ de todas as subcontas
  - quantidade_cotas: total de cotas
  - data_referencia: data de referência do saldo (YYYY-MM-DD)

═══════════════════════════════════════════
RETORNE EXATAMENTE este JSON preenchido:
═══════════════════════════════════════════

{
  "documento": {
    "tipo": "funcef",
    "titular": "nome do titular ou null",
    "competencia_referencia": "YYYY-MM"
  },
  "debug": {
    "competencias_encontradas": ["2026/01", "2026/04", "2026/13"],
    "competencias_regulares": ["2026/01", "2026/04"]
  },
  "historico_cotas_mensais": [
    {"competencia": "YYYY-MM", "data": "YYYY-MM-DD", "valor_cota": 0.0}
  ],
  "saldo_atual": {
    "valor_real": 0.0,
    "quantidade_cotas": 0.0,
    "data_referencia": "YYYY-MM-DD"
  },
  "contribuicao_mes_corrente": {
    "competencia": "YYYY-MM",
    "data_ultimo_dia": "YYYY-MM-DD",
    "linhas_competencia": [
      {
        "historico": "Normal - Participante",
        "valor_contribuicao": 0.0,
        "credito_subconta": 0.0,
        "cotas": 0.0
      },
      {
        "historico": "Normal - Patrocinador",
        "valor_contribuicao": 0.0,
        "credito_subconta": 0.0,
        "cotas": 0.0
      }
    ]
  },
  "validacao": {
    "cota_historico": 0.0,
    "ok": true,
    "mensagem": "OK"
  },
  "observacoes": "anote aqui qualquer dúvida, dado ausente ou anomalia encontrada"
}

ATENÇÃO FINAL:
- Todos os valores monetários: float com ponto decimal (não vírgula)
- Datas: sempre YYYY-MM-DD
- linhas_competencia: lista TODAS as linhas "Normal -" do mês, uma por uma. Nunca some.
- Se qualquer campo não for encontrado: use null e explique em observacoes
- NUNCA some competências de meses diferentes
- NUNCA inclua /13 em nenhum cálculo"""
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

• Para funcef (regras especiais — leia com atenção):
  PASSO A: Identifique a competência regular mais recente (MM entre 01 e 12). IGNORE /13 completamente.
  PASSO B: Para cada linha "Normal -" dessa competência com valor > 0, registre UM objeto em "dados_extras.funcef.linhas_competencia":
    {"historico": "texto exato", "valor_contribuicao": X, "credito_subconta": Y, "cotas": Z}
  ⛔ NÃO calcule totais — o Python soma. Apenas liste as linhas individuais.
  PASSO C: Registre a cota do mês em dados_extras.funcef.validacao.cota_historico.
  - "eventos": 1 evento CONTRIBUICAO com data=último dia do mês, qtd=null, preco=null, valor=null, obs="Contribuição FUNCEF YYYY/MM"
  - "dados_extras.funcef.linhas_competencia": lista das linhas individuais (ver PASSO B)
  - "dados_extras.funcef.historico_cotas_mensais": [{competencia, data, valor_cota}] — TODAS as cotas
  - "dados_extras.funcef.saldo_atual": {valor_real, quantidade_cotas, data_referencia}
  - "dados_extras.funcef.validacao": {cota_historico, ok, mensagem}

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
