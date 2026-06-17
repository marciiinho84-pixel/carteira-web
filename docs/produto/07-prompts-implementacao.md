# Roadmap de Execução — Fatias 2-7

*Este documento é lido pelo Claude Code como guia de implementação.*
*O plano macro está em 06-plano-implementacao.md. O conceito em 01-conceito.md.*
*Em conflito, o conceito vence.*

---

## Como usar este documento

Executar as fatias na ordem abaixo. Cada fatia tem critérios de aceite
verificáveis — só avançar para a próxima quando todos os critérios da
anterior passarem.

**Pontos de parada (STOP):** marcados explicitamente. Nesses pontos,
parar e reportar ao usuário antes de prosseguir. O usuário levará a
questão ao chat de produto e retornará com a decisão.

**Princípios transversais (aplicam a TODA fatia):**
- Local primeiro → teste com dados sintéticos → commit → backup → produção.
- Não alterar engine de performance, cálculo de TWR, ou schema de posições
  existentes (exceto adicionar tabelas novas via Alembic).
- Não tocar no frontend Streamlit além do mínimo necessário para cada fatia.
- Testes de regressão existentes devem continuar passando após cada fatia.
- Cada tool MCP nova é registrada no server.py junto às tools existentes.

---

## Fatia 2 — Fundamentos ao vivo via API

### Etapa 2.1 — Avaliação de APIs

**⛔ STOP após esta etapa. Reportar resultado antes de implementar.**

Avaliar duas APIs candidatas para fonte de fundamentos. Dados de Mercado
é a preferencial (documentação verificável). Partnr é alternativa.

**API 1 — Dados de Mercado (preferencial)**
- Base: `api.dadosdemercado.com.br/v1`
- Docs: `dadosdemercado.com.br/api/docs`
- Autenticação: Bearer token

**API 2 — Partnr (alternativa)**
- Base: `developers.partnr.ai`
- Docs: `developers.partnr.ai`

**Para cada API, testar:**
- Cotação/fundamentos de 5 ativos BR: WEGE3, PETR4, PRIO3, ITUB3, EMBJ3
- Cobertura de BDRs: ASML34, ROXO34, M2PM34 (ponto fraco esperado)
- Cobertura de ETFs: DIVO11, SMAL11, BAER39
- Indicadores disponíveis: P/L, P/VP, ROE, ROIC, DY, margem EBITDA,
  dívida líquida/EBITDA, margem líquida, LPA, VPA
- Limites de requisição do plano gratuito/básico
- Endpoints de macro (Selic, IPCA, Focus) — mapear para Fatia 3
- Endpoints de notícias/eventos — mapear para Fatia 13 (futuro)

**Output:** relatório comparativo com cobertura real, indicadores
disponíveis, limites, preço estimado, e recomendação de qual usar.

**⛔ STOP aqui. Mostrar relatório ao usuário. Aguardar aprovação.**

### Etapa 2.2 — Implementação (após aprovação)

**Peça A — Tabela `fundamentos`**
- Migration Alembic, tabela append-only.
- Colunas: asset_id, data_referencia, indicador (enum), valor, fonte,
  fetched_at.
- Indicadores enum: PL, PVP, ROE, ROIC, DY, MARGEM_EBITDA,
  DIV_LIQ_EBITDA, MARGEM_LIQUIDA, LPA, VPA.
- Semântica bitemporal (fetched_at) — mesmo padrão da tabela `cotacoes`.

**Peça B — Coleta em lote**
- Script que busca fundamentos de todos os ativos da carteira na API
  escolhida.
- Retry com backoff (mesmo padrão das cotações).
- Se um ativo não tiver fundamentos (ETF, fundo): registrar como NULL,
  não falhar.
- Cron: 1x/dia após cotações (22h UTC) ou semanal se limites de API
  forem restritivos.

**Peça C — Tool MCP `consultar_fundamentos`**
- Input: ticker (ou lista de tickers)
- Output: últimos fundamentos disponíveis com data de referência.

**Critérios de aceite:**
1. Relatório de avaliação entregue com dados reais.
2. Tabela `fundamentos` populada para ≥20 ativos.
3. Tool MCP acessível via Claude Desktop.
4. Coleta em lote roda sem erro; ativos sem cobertura logados.
5. Testes de regressão passando.

**Não fazer:** não substituir Brapi para cotações; não criar instrumentista
fundamentalista (maestro cruza direto); não integrar notícias nem macro.

---

## Fatia 3 — Macro e eventos corporativos persistidos

*Depende de: Fatia 2 concluída (API escolhida).*

### Peça A — Tabela `macro_indicadores`

Migration Alembic, append-only. Colunas: indicador (enum),
data_referencia, valor, fonte, fetched_at.

Indicadores enum (MVP):
| Indicador | Frequência | Fonte |
|---|---|---|
| SELIC_META | diária | BCB SGS série 432 |
| SELIC_ACUMULADA | diária | BCB SGS série 11 |
| IPCA_MENSAL | mensal | BCB SGS série 433 |
| IPCA_12M | mensal | calculado |
| CAMBIO_PTAX | diária | BCB SGS série 1 |
| CDI_DIARIO | diária | já coletado para benchmarks — referenciar, não duplicar |
| FOCUS_SELIC_12M | semanal | API BCB Focus ou API escolhida |
| FOCUS_IPCA_12M | semanal | idem |

Crons: diário para indicadores diários (junto com cotações); semanal
para Focus (segunda-feira).

### Peça B — Tabela `eventos_corporativos`

Migration Alembic. Colunas: asset_id, data_evento, tipo_evento (enum),
descricao, fonte, fetched_at.

Tipos enum: FATO_RELEVANTE, DATA_BALANCO, DIVIDENDO_PROGRAMADO,
AGO_AGE, DESDOBRAMENTO, GRUPAMENTO.

Fonte: API escolhida na Fatia 2 (se cobrir eventos). Alternativa: CVM.
Cron diário.

### Peça C — Tools MCP

1. `consultar_macro` — input: indicador ou "todos", período (default:
   último valor). Output: valor atual + série últimos 3 meses.
2. `eventos_corporativos` — input: ticker ou "carteira". Output:
   próximos eventos + eventos dos últimos 30 dias.

**Critérios de aceite:**
1. `macro_indicadores` populada com ≥30 dias de Selic, IPCA, câmbio.
2. `eventos_corporativos` populada para ativos com eventos disponíveis.
3. Ambas as tools acessíveis via Claude Desktop.
4. Crons configurados e rodando.
5. Testes de regressão passando.

**Não fazer:** não criar curva de juros completa; não integrar notícias
(Fatia 13); não alterar engine.

---

## Fatias 4-7 — Disciplinas de gestão

*Independentes entre si e das Fatias 2-3. Podem rodar em paralelo.*
*Mesmo padrão para todas: migration Alembic + formulário Streamlit + tool MCP.*

### Fatia 4 — Teses com critérios de invalidação (§7.2)

**Tabela `teses`** — migration Alembic:
- id (PK), asset_id (FK), bloco_ips (enum: SWING_TRADE, GROWTH,
  DEFENSIVOS, RENDA_FIXA), racional (text), cenario_esperado (text),
  criterio_invalidacao (text), nivel_invalidacao (enum: VERDE, AMARELO,
  VERMELHO), data_criacao, data_atualizacao (nullable), status (enum:
  ATIVA, INVALIDADA, ENCERRADA), observacao_encerramento (text, nullable).

**Formulário Streamlit:**
- Dropdown de ativos com posição ativa.
- Campos: racional, cenário, critério de invalidação.
- Lista de teses ativas com opção de alterar nível e encerrar.

**Tool MCP `consultar_teses`:**
- Input: ticker (opcional — default: todas as ativas).
- Output: teses com racional, critério, nível, tempo desde criação.

**Critérios:** tabela criada, formulário funcional, tool acessível,
3 teses de teste criadas (WEGE3, PRIO3, EMBJ3).

**Não fazer:** não implementar checagem automática de invalidação;
não criar notificações automáticas.

### Fatia 5 — Diário de decisão (§7.3)

**Tabela `diario_decisoes`** — migration Alembic:
- id (PK), data_decisao, asset_id (FK), acao (enum: COMPRA, VENDA,
  AUMENTO, REDUCAO, MANTER, WATCHLIST), racional (text),
  cenario_esperado (text), conviccao (integer 1-5), preco_entrada
  (decimal, nullable), resultado_percentual (decimal, nullable —
  calculado dinamicamente na consulta, não armazenado),
  tese_id (FK para teses, nullable).

**Formulário Streamlit:**
- Página de diário: formulário + lista cronológica.
- No registro de COMPRA/VENDA, oferecer link para registrar no diário
  (opcional, não obrigatório).

**Tool MCP `consultar_diario`:**
- Input: ticker (opcional), período (opcional).
- Output: entradas em ordem cronológica reversa. resultado_percentual
  calculado na hora (preço entrada vs. cotação atual da tabela `cotacoes`).

**Critérios:** tabela criada, formulário funcional, tool com resultado
dinâmico, 3 entradas de teste.

**Não fazer:** não tornar obrigatório; não analisar padrões (Fatia 8).

### Fatia 6 — Risco ex-ante (§7.4)

Sem tabela nova — cálculo puro sobre dados existentes.

**Exposição por fator (3 fatores):**
1. Setor — usar classificação da CAD_ATIVOS. % patrimônio gerido/setor.
2. Moeda — BRL vs. USD (BDRs/ETFs internacionais = USD). % BRL, % USD.
3. Bloco IPS — reaproveitar da Fatia 1, não duplicar.

**Drawdown máximo:**
- Max drawdown da Carteira Gerida usando série TWR diária existente.
- MDD YTD, MDD 12 meses, MDD desde início.
- Duração: dias pico→vale, dias vale→recuperação.

**Escala de liquidez:**
- Campo Liquidez da CAD_ATIVOS. % patrimônio disponível em D+0, D+1,
  D+3, D+30, D+30+.
- Alerta se <20% disponível em D+3.

**Cenários de stress (fixos, MVP):**
- IBOV -20%: impacto estimado (beta implícito por regressão 60 dias).
- USD +30%: BDRs +30%, ações BR 0 (exceto exportadoras: proxy +15%).
- Selic +300bps: positivo pós-fixados, negativo prefixados/IPCA+.
- São aproximações de ordem de grandeza, não modelos institucionais.

**Tool MCP `risco_carteira`:**
- Input: tipo (exposicao | drawdown | liquidez | stress | todos).
- Output: métricas solicitadas. Default: "todos" = resumo consolidado.

**Critérios:** exposição conferida manualmente para 3 ativos, MDD
conferido contra série TWR, tool acessível.

**Não fazer:** não implementar VaR/CVaR; não criar dashboard; cenários
fixos (configuráveis depois).

### Fatia 7 — Disciplina de aporte e caixa (§7.6)

**Tabela `regra_aportes`** — migration Alembic:
- id (PK), valor_mensal_alvo (decimal), tipo (enum: PROGRAMADO,
  OPORTUNISTICO, MISTO), criterio_oportunismo (text, nullable),
  data_criacao, ativo (boolean — 1 regra ativa por vez).

**Monitoramento de cash drag:**
- Caixa atual (% Carteira Gerida).
- Dias acima de 15%.
- Aporte realizado no mês vs. valor_mensal_alvo.
- Status: SAUDAVEL | ELEVADO_TEMPORARIO (<6 sem) | REQUER_REVISAO (>6 sem).
- Regras de tempo derivadas da IPS §4.

**Tool MCP `disciplina_caixa`:**
- Input: nenhum (sempre Carteira Gerida).
- Output: caixa %, dias acima do limiar, aporte mês vs. alvo, status.

**Formulário Streamlit:** definir/alterar regra ativa.

**Critérios:** tabela criada, monitoramento correto (conferir vs.
dashboard), tool acessível.

**Não fazer:** não implementar aporte automático nem sugestão de
alocação; não alterar alertas existentes.

---

## Sequência recomendada

```
Sessão 1: Fatia 2 (etapa 2.1 — avaliação) → ⛔ STOP
Sessão 2: Fatias 4 + 5 + 6 + 7 (disciplinas — paralelas, mesmo padrão)
Sessão 3: Fatia 2 (etapa 2.2 — implementação, após aprovação)
Sessão 4: Fatia 3 (macro/eventos — depende da API da Fatia 2)
```

As Fatias 4-7 não dependem das APIs e podem rodar enquanto a avaliação
da Fatia 2 está em análise.

---

*Próximas fatias (8+) serão definidas após as Fases 1-2 estarem entregues.*
