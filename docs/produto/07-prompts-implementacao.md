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

A sequência completa e atualizada está no final deste documento.

## Fase 3 — Inferência comportamental (Fatias 8-9)

*Realiza: "espelho para dentro" (§2), "dito vs. feito" (§3).*
*O diferencial que ninguém no mercado tem.*
*Depende de: 1a (event log) + Fatias 4-5 (teses e diário = o "dito").*

### Fatia 8 — Leitura do event log para padrões de comportamento

O event log existe e é rico, mas é usado apenas para calcular performance.
Esta fatia o transforma em fonte de conhecimento sobre o *investidor* —
como ele se comporta, não como a carteira performa.

**Módulo `comportamento.py`** — funções que leem o event log e calculam:

1. **Giro real (turnover) por bloco IPS**
   - Fórmula: (valor total de vendas no período) / (patrimônio médio
     do bloco no período).
   - Período: mensal, trimestral, anual.
   - Separar por bloco IPS (Swing Trade deve ter giro maior que Growth
     ou Defensivos — se Growth tiver giro alto, é sinal).

2. **Holding period médio por bloco**
   - Para posições encerradas: dias entre compra e venda.
   - Para posições abertas: dias desde a compra até hoje.
   - Separar por bloco IPS.
   - Comparar com o horizonte declarado do bloco na IPS (Swing = semanas
     a meses; Growth = multi-ano).

3. **Frequência de operações**
   - Número de operações por mês (compras + vendas).
   - Tendência: acelerando ou desacelerando?
   - Picos: meses com frequência anormalmente alta (>2σ da média).

4. **Concentração efetiva vs. IPS**
   - Já existe parcialmente na Fatia 1 (aderência setorial).
   - Expandir: concentração por ativo individual — top 5 posições
     como % da Carteira Gerida.
   - Herfindahl-Hirschman simplificado (soma dos quadrados dos pesos)
     como proxy de diversificação.

**Persistência:**
- Tabela `metricas_comportamento` — migration Alembic.
- Colunas: metrica (enum), bloco_ips (nullable), periodo_inicio,
  periodo_fim, valor, calculado_em.
- Atualização: sob demanda via tool (não cron — teste das 4 condições:
  frequência real < semanal, custo de cálculo baixo, não justifica
  automação ainda).

**Tool MCP `perfil_comportamental`:**
- Input: métrica (turnover | holding | frequencia | concentracao | todos),
  período (default: últimos 12 meses).
- Output: métricas calculadas, com comparação vs. IPS onde aplicável.
- Recalcula na hora se dados novos desde último cálculo; senão retorna
  cache.

**Referência conceitual:** FinCon/FinMem — memória em camadas. Implementar
três horizontes nas métricas: curto (último mês), médio (último trimestre),
longo (desde início). O maestro escolhe o horizonte relevante.

**Critérios de aceite:**
1. Tabela `metricas_comportamento` criada via Alembic.
2. Turnover calculado e verificado manualmente para 1 bloco (Swing Trade)
   — conferir valor de vendas vs. patrimônio médio.
3. Holding period calculado para ≥5 posições (abertas e encerradas).
4. Frequência mensal conferida contra contagem manual do event log.
5. Concentração top-5 conferida contra posições atuais.
6. Tool MCP `perfil_comportamental` acessível via Claude Desktop,
   retornando dados nos 3 horizontes.
7. Testes de regressão passando.

**Não fazer:**
- NÃO interpretar os padrões — esta fatia só computa. A interpretação
  é da Fatia 9 (cruzamento) e do maestro.
- NÃO criar alertas ou notificações.
- NÃO alterar engine de performance ou event log.
- NÃO implementar detecção de vieses cognitivos (ancoragem, FOMO) —
  fica para fatias futuras.

---

### Fatia 9 — Cruzamento dito-vs-feito

*O insight central do conceito (§3): "A divergência entre o dito e o*
*feito é o material mais valioso."*

**Módulo `dito_vs_feito.py`** — cruza o "feito" (Fatia 8) com o "dito"
(Fatias 4-5) e reporta divergências como fatos, sem juízo.

**4 cruzamentos no MVP:**

1. **Horizonte declarado vs. holding period real**
   - Fonte "dito": bloco IPS (Growth = multi-ano, Swing = semanas/meses)
     + tese do ativo (se existir, campo cenario_esperado).
   - Fonte "feito": holding period da Fatia 8.
   - Divergência: "Bloco Growth — holding period médio: 45 dias.
     Horizonte declarado: multi-ano."

2. **Alocação declarada vs. concentração real**
   - Fonte "dito": IPS (alvos e bandas por bloco).
   - Fonte "feito": concentração efetiva da Fatia 8 + aderência Fatia 1.
   - Divergência: "Growth está em 32% (alvo 20%, banda 10-30%) — acima
     da banda superior."
   - Nota: a aderência por bloco já existe na Fatia 1. Aqui o que se
     adiciona é a *persistência temporal* — não só "está fora agora",
     mas "está fora há 3 meses consecutivos."

3. **Convicção declarada vs. resultado**
   - Fonte "dito": diário de decisão (convicção 1-5, cenário esperado).
   - Fonte "feito": resultado_percentual calculado na Fatia 5.
   - Divergência: "Suas 5 operações com convicção 5 tiveram resultado
     médio de -3%. Suas 8 operações com convicção 2-3 tiveram resultado
     médio de +12%."

4. **Critério de invalidação vs. dados atuais**
   - Fonte "dito": teses ativas com critério de invalidação (Fatia 4).
   - Fonte "feito": dados do substrato (fundamentos Fatia 2, cotações,
     macro Fatia 3).
   - Divergência: "Tese de PRIO3: critério de invalidação = 'petróleo
     abaixo de USD 60.' Petróleo atual: USD 62. Proximidade: 3%."
   - Este cruzamento é o mais rico — é onde o maestro vira **auditor**
     da própria disciplina do investidor (§7 do conceito).

**Tool MCP `divergencias_dito_feito`:**
- Input: tipo (horizonte | alocacao | conviccao | invalidacao | todos),
  período (default: últimos 6 meses para padrões, atual para invalidação).
- Output: lista de divergências encontradas, cada uma com:
  - descricao (texto factual, sem juízo)
  - fonte_dito (de onde veio a declaração)
  - fonte_feito (de onde veio o dado real)
  - severidade (INFO | ATENCAO | CRITICO)
    - INFO: divergência existe mas dentro de margem razoável
    - ATENCAO: divergência significativa, monitorar
    - CRITICO: critério de invalidação atingido ou banda IPS violada

**⛔ STOP após implementação. Mostrar ao usuário as divergências reais
encontradas na carteira antes de considerar esta fatia concluída.**
O objetivo é validar que os cruzamentos fazem sentido com dados reais,
não sintéticos.

**Critérios de aceite:**
1. Os 4 cruzamentos implementados e retornando dados.
2. Tool MCP acessível via Claude Desktop.
3. Pelo menos 1 divergência real encontrada na carteira (se a carteira
   estiver perfeitamente alinhada com a IPS e não houver teses, criar
   dados de teste que simulem divergência).
4. Output factual — nenhuma recomendação, nenhum juízo. O maestro pode
   contextualizar, o módulo apenas reporta fatos.
5. Testes de regressão passando.

**Não fazer:**
- NÃO recomendar ações ("você deveria vender" — nunca).
- NÃO atribuir vieses cognitivos ("isso é ancoragem" — futuro).
- NÃO criar alertas automáticos ou push — reportar sob demanda via tool.
- NÃO alterar as Fatias 4-5 (teses e diário).
- NÃO implementar proatividade — o maestro consulta quando relevante.

---

## Sequência atualizada

```
Sessão 1: Fatia 2 (etapa 2.1 — avaliação) → ⛔ STOP          ✅ ENTREGUE
Sessão 2: Fatias 4 + 5 + 6 + 7 (disciplinas)                 ✅ ENTREGUE
Sessão 3: Fatia 2 (etapa 2.2 — yfinance estendido)            ✅ ENTREGUE
Sessão 4: Fatia 3 (macro/eventos com BCB)                     ✅ ENTREGUE
Sessão 5: Fatia 8 (inferência event log)                      🔜 PRÓXIMA
Sessão 6: Fatia 9 (dito vs. feito) → ⛔ STOP                  ─
```

*Próximas fatias (10+) serão definidas após a Fase 3 estar entregue.*
