# 🎯 Projeto Carteira Clean — Roteiro para Claude Code

> **Este documento é o ponto de partida para você (Claude Code) dar continuidade
> ao Projeto Carteira Clean.** O trabalho até aqui foi feito em conversas com
> Claude no chat, gerando uma planilha Excel + engine Python. Sua missão é
> transformar isso em uma **ferramenta web automatizada**.
>
> **Antes de começar a programar**, leia este documento INTEIRO. Ele contém
> contexto crítico, decisões já tomadas (para preservar), princípios que
> devem guiar suas escolhas, e números de validação para garantir que nada
> quebre na migração.

---

## 📑 ÍNDICE

1. [Quem é o usuário e qual o problema](#1-quem-é-o-usuário)
2. [Estado atual da implementação](#2-estado-atual)
3. [Glossário e modelo conceitual](#3-glossário)
4. [Modelo de dados — Event Log](#4-modelo-de-dados)
5. [Motor de cálculos — algoritmos chave](#5-motor-de-cálculos)
6. [Decisões arquiteturais já tomadas (preservar!)](#6-decisões-tomadas)
7. [Princípios operacionais (guardrails)](#7-princípios)
8. [Anti-padrões a evitar](#8-anti-padrões)
9. [Missão: Ferramenta web — visão do produto](#9-missão-web)
10. [Stack tecnológica recomendada](#10-stack)
11. [Plano faseado de migração](#11-plano-faseado)
12. [Números de validação (regression tests)](#12-validação)
13. [Arquivos de referência disponíveis](#13-arquivos)
14. [Primeira tarefa sugerida](#14-primeira-tarefa)

---

## 1. Quem é o usuário <a name="1-quem-é-o-usuário"></a>

**Marcio de Almeida Souza** — funcionário público da Caixa Econômica Federal,
próximo da aposentadoria. **Não tem formação em TI.** Usa Ubuntu Linux
(Inspiron 15-3530).

**Patrimônio:** ~R$ 1,37 MM em 5 produtos:
1. **FUNCEF** (previdência complementar Caixa) — 90% da carteira
2. **Carteira Gerida** na Caixa (Renda Variável + RF + Multimercado) — ~9%
3. **Tesouro Renda+ 2065** — pequena posição
4. **Caixa LCI** — reserva
5. **Caixa OURO** — exposição commodities

**Meta:** R$ 3.000.000 (chegar a essa marca antes/durante a aposentadoria).

**Estilo de gestão:**
- Estratégia **fluida** (não quer alertas rígidos, não quer regras automatizadas)
- Investidor temático em RV (semicondutores, urânio, terras raras, aeroespacial, etc.)
- Faz muitas operações pequenas (~60 trades em 4,5 meses)
- D+2 é restrição operacional crítica (não tem caixa automático)
- **Quer apoio para execução, não medição passiva**

**Aportes mensais previstos:**
- R$ 6.392/mês em FUNCEF (contribuição compulsória)
- R$ 10.000 em março e outubro na Carteira Gerida

**Frequência de uso desejada:** atualizar a carteira **diariamente** com
mínimo esforço operacional.

---

## 2. Estado atual da implementação <a name="2-estado-atual"></a>

### O que já existe (Fase 1 — local, Excel + Python)

**Planilha `Carteira_Clean_v2.xlsx`** com 10 abas:

| Aba | Função |
|---|---|
| `DASHBOARD` | KPIs executivos + alertas |
| `CARTEIRA_RV` | Estação operacional de Renda Variável (4 seções) |
| `POSICOES` | Foto detalhada de todas as posições (com status liquidação) |
| `EVOLUCAO` | Patrimônio diário + TWR + benchmarks (96 dias úteis) |
| `ATRIBUICAO_MENSAL` | Long format: mês × ativo (92 linhas) |
| `RELATORIO_VENDAS` | Vendas com P&L realizado |
| `META_PATRIMONIO` | Projeção ano-a-ano até R$ 3MM |
| `CAD_ATIVOS` | **Cadastro mestre** dos 35 ativos |
| `EVENTOS` | **Event log** — fonte única de verdade (105 eventos) |
| `HISTORICO_PRECOS` | Preços manuais para ativos sem cotação pública |

**Script `atualizar_carteira.py`** (~1.400 linhas, modular):
- Lê EVENTOS + CAD_ATIVOS + HISTORICO_PRECOS
- Baixa preços via yfinance + benchmarks via BCB SGS
- Calcula posições (PEPS), TWR, atribuição mensal, projeção
- Infere aportes externos retroativos via caixa virtual
- Detecta status de liquidação D+2 automaticamente
- Valida ativamente e emite alertas
- Sobrescreve as 7 abas geradas (POSICOES, CARTEIRA_RV, EVOLUCAO, etc.)
- **Nunca toca em EVENTOS** (preserva fonte única de verdade)

**Workflow atual do user:**
1. Adiciona eventos novos na aba EVENTOS
2. Salva e fecha a planilha
3. Roda `python3 atualizar_carteira.py` no Terminal
4. Reabre a planilha — tudo recalculado

**Documentação:**
- `GUIA_EXECUCAO.md` — passo a passo para uso do user não-técnico
- `instalar.py` — instala dependências (yfinance, pandas, openpyxl, requests, numpy)
- `RELATORIO_LEITURA_B3.md` + `RELATORIO_LEITURA_MOVIMENTACOES.md` —
  análise das fontes de dados originais

### O que falta (Fase 2 — web)

**Sua missão.** Detalhada em [Seção 9](#9-missão-web).

---

## 3. Glossário e modelo conceitual <a name="3-glossário"></a>

**Conceitos críticos para entender o código:**

| Termo | Significado |
|---|---|
| **Composite** | Agrupamento contábil para TWR. Existem 2: `FUNCEF` (separado, não-influenciável) e `Gerida` (todo o resto). |
| **Família** | Tipo do ativo. `Ação BR`, `BDR`, `BDR de ETF`, `ETF BR`, `Fundo CP`, `Fundo de Pensão`, `Fundo Indexado`, `Tesouro Direto`, `Letra de Crédito`. |
| **COTIZADO_PUBLICO** | Família com preço diário público via yfinance: `Ação BR`, `BDR`, `BDR de ETF`, `ETF BR`. |
| **COTIZADO_PRIVADO** | Família cotizada (qtd × preço) mas SEM preço público: `Fundo CP`, `Fundo de Pensão`, `Fundo Indexado`, `Tesouro Direto`. Preços manuais na HISTORICO_PRECOS. |
| **AGREGADO_PRIVADO** | Família onde a posição é direto o saldo (sem cotas): `Letra de Crédito`. Saldos manuais. |
| **Modelo A** | Período retroativo (02/01/2026 → 16/05/2026). Caixa NÃO trackeado explicitamente. Aportes inferidos via caixa virtual. |
| **Modelo B** | Período futuro (17/05/2026 +). `CAIXA FIC FUNC` é tratado como **caixa explícito**. Compras debitam FIC FUNC, dividendos creditam. |
| **D+2** | Liquidação em 2 dias úteis após o trade. Crítico para gestão de caixa operacional. |
| **PEPS** | Primeiro a Entrar, Primeiro a Sair. Método contábil para custo médio. **Com reset em zeramento** (importante!). |
| **TWR** | Time-Weighted Return (Modified Dietz simplificado). Padrão GIPS para retornos. Neutraliza efeito de fluxos externos. |
| **Caixa virtual** | Modelo retroativo: saldo "fictício" que entra com VENDAs/RESGATEs/PROVENTOs e sai com COMPRAs/APLICAÇÕES. Quando ficaria negativo → APORTE_EXTERNO inferido. |
| **Aporte externo inferido** | APORTE_EXTERNO calculado dinamicamente pelo engine, sem tocar no event log. Aparece como fluxo no cálculo de TWR. |

---

## 4. Modelo de dados — Event Log <a name="4-modelo-de-dados"></a>

### Tipos de eventos (12 tipos)

| Tipo | Significado | Afeta posição? | Afeta caixa virtual? |
|---|---|---|---|
| `SALDO_INICIAL` | Foto inicial em 02/01/2026 | ✓ aumenta qtd e custo | Não (é foto) |
| `COMPRA` | Trade de compra | ✓ aumenta qtd e custo | Sim, sai caixa |
| `VENDA` | Trade de venda | ✓ reduz qtd e custo (PEPS) | Sim, entra caixa |
| `DIVIDENDO` | Dividendo pago | Não | Sim, entra caixa |
| `JCP` | Juros sobre capital próprio | Não | Sim, entra caixa |
| `RENDIMENTO` | Rendimento de RF (LCI, FIC FUNC) | Não | Depende: LCI fica na LCI, FIC FUNC fica no FIC |
| `AMORTIZACAO` | Amortização (Tesouro, p.ex.) | Não | Sim, entra caixa |
| `BONIFICACAO` | Bonificação em ações | ✓ aumenta qtd (custo R$ 0) | Não |
| `CONTRIBUICAO` | Contribuição FUNCEF | ✓ aumenta qtd FUNCEF | Não (é fluxo externo composite FUNCEF) |
| `APORTE_EXTERNO` | Dinheiro entrando de fora | Não | Sim, entra caixa |
| `RESGATE_EXTERNO` | Dinheiro saindo pra fora | Não | Sim, sai caixa |
| `VENCIMENTO` | Vencimento de título | ✓ zera posição | Sim, entra caixa |

### Schema da tabela EVENTOS (8 colunas)

```
Data  | Ativo  | Tipo  | Quantidade | Preço | Valor R$ | Observação
```

**Regras de integridade:**
- `Data` sempre presente
- `Ativo` deve estar em CAD_ATIVOS
- `Tipo` deve ser um dos 12 tipos
- `Valor R$` é sempre POSITIVO (sinal vem do tipo)
- `Observação` é livre; algumas convenções usadas:
  - `AGREGADO maio` → evento provisório, será detalhado depois
  - `PENDENTE LIQUIDAÇÃO` → override manual (script infere automaticamente também)
  - `IRRF: R$ X,XX` → informação fiscal

### Schema da tabela CAD_ATIVOS

```
Ticker | Classe | Família | Setor | Indexador | Benchmark | Liquidez | Risco | Composite | Observação
```

**Composites:** apenas 2 valores possíveis: `FUNCEF` (1 ativo) ou `Gerida` (34 ativos).

**Setor:** re-setorizado v3, granular temático (23 setores). Exemplos: "Hyperscalers",
"Mineração de Terras Raras", "Semicondutores", "Aeroespacial e Defesa", etc.

### Schema da tabela HISTORICO_PRECOS

```
Data | Ticker | Valor | Fonte
```

Usado para ativos sem preço público:
- FUNCEF (cota mensal — 26 pontos atuais)
- CAIXA FIC FUNC (cota mensal — 5 pontos)
- CAIXA LCI (saldos absolutos — 5 pontos)
- CAIXA OURO (cota mensal — 5 pontos)
- C6 RENDA+ (valor do título — 6 pontos)

**Cuidado:** para AGREGADO_PRIVADO (LCI), o "valor" é o saldo total, não preço unitário.

---

## 5. Motor de cálculos — algoritmos chave <a name="5-motor-de-cálculos"></a>

### 5.1 PEPS com reset em zeramento

```python
# Para cada VENDA, calcula P&L com custo médio acumulado
custo_medio = custo_total / qtd
custo_vendido = custo_medio * qtd_vendida
pnl = valor_recebido - custo_vendido
custo_total -= custo_vendido
qtd -= qtd_vendida

# RESET: se zerou completamente, custo volta a 0 (PEPS limpo)
if abs(qtd) < 1e-6:
    qtd = 0; custo_total = 0
```

**Por que reset?** Quando o user vende tudo e recompra depois (ex: PETR4, AURA33),
o novo custo médio começa do zero, não carrega resíduo da posição anterior.

### 5.2 Inferência de aportes externos retroativos

**Problema:** No Modelo A (jan-mai/2026), as COMPRAs de RV não vêm
acompanhadas de APORTE_EXTERNO no event log. Sem isso, o TWR fica
artificialmente alto (lê dinheiro novo como retorno).

**Solução:** Caixa virtual.

```
saldo_virtual = 0
para cada evento em ordem cronológica (apenas Composite=Gerida, antes de 17/05):
    se VENDA de RV ou RESGATE de FIC FUNC ou PROVENTO de RV:
        saldo_virtual += valor
    se COMPRA de RV ou APLICAÇÃO em FIC FUNC ou COMPRA Renda+:
        se saldo_virtual < valor:
            APORTE_EXTERNO_INFERIDO = valor - saldo_virtual no dia do evento
            saldo_virtual = 0
        senão:
            saldo_virtual -= valor

saldo_residual = saldo_virtual no fim do período → snapshot inicial Modelo B
```

**Validação:** o `saldo_residual` deve bater (com pequeno desvio) com o saldo real
do FIC FUNC em 16/05/2026 (R$ 2.450,48). Hoje bate em R$ 2.070,00 (desvio R$ 380,
dentro do esperado para agregado provisório).

### 5.3 TWR com Modified Dietz simplificado

```python
# Para cada dia i (a partir do dia 1):
v0 = patrimonio[i-1]
v1 = patrimonio[i]
cf = fluxo_externo[i]  # APORTE positivo, RESGATE negativo
r_i = (v1 - cf - v0) / (v0 + cf)
twr_cumulativo[i] = (1 + twr_cumulativo[i-1]) * (1 + r_i) - 1
```

**Composites calculados separadamente:**
- `twr_gerida` — só Composite=Gerida
- `twr_total` — Gerida + FUNCEF
- `twr_rv` — sub-portfolio RV (Ação BR + BDR + ETF) tratado como sub-carteira isolada

### 5.4 Detecção D+2

```python
def status_liquidacao(evento, hoje):
    dias_uteis_passados = num_dias_uteis_entre(evento.data, hoje)
    if dias_uteis_passados >= 2:
        return "LIQUIDADO"
    if evento.tipo == "COMPRA":
        return "PENDENTE_ENTRADA"
    elif evento.tipo == "VENDA":
        return "PENDENTE_SAIDA"
```

Override manual via observação (`PENDENTE LIQUIDAÇÃO` ou `LIQUIDADO`) também aceito.

### 5.5 Tratamento especial para eventos AGREGADO

Eventos com `obs="AGREGADO maio"` (resgate consolidado provisório do FIC FUNC)
têm data internamente antecipada para o **1º dia útil do mês** durante o cálculo
de inferência retroativa. Isso reflete que os resgates reais aconteceram ao longo
do mês, não na data arbitrária do agregado.

**Quando o extrato real chegar**, basta substituir o agregado por movimentações
detalhadas e este tratamento deixa de ter efeito.

### 5.6 Atribuição mensal (long format)

Para cada mês fechado, para cada ativo:
- `retorno_ativo` = (preco_fim_mes / preco_inicio_mes) - 1
- `peso_medio` = (valor_inicio + valor_fim) / 2 / patrimonio_medio_composite
- `contribuicao` = retorno × peso_medio

Soma das contribuições no mês ≈ TWR do composite no mês.

---

## 6. Decisões arquiteturais já tomadas (preservar!) <a name="6-decisões-tomadas"></a>

Estas decisões saíram de **7 reuniões de design**. Não devem ser reabertas
sem motivo forte:

| # | Decisão | Racional |
|---|---|---|
| 1 | **Event log como single source of truth** | Idempotência: rodar engine N vezes = mesmo resultado |
| 2 | **Composites separados: Gerida vs FUNCEF** | FUNCEF não é influenciável pelo user; deve ter TWR independente |
| 3 | **Trade-date accounting (GIPS-aligned)** | Padrão profissional; data de execução, não liquidação |
| 4 | **PEPS com reset em zeramento** | Custo médio "limpo" quando posição zera e reabre |
| 5 | **Modelo A retroativo (caixa virtual) + Modelo B futuro (caixa explícito)** | Reconstrói histórico sem extrato + caixa real após corte |
| 6 | **TWR Modified Dietz simplificado** | Equilíbrio entre precisão e simplicidade |
| 7 | **4 benchmarks**: CDI, IPCA (BCB) + IBOV, S&P500 BRL (yfinance) | Cobertura completa: indexador, inflação, BR, internacional |
| 8 | **Concentração alerta > 15% na Carteira Gerida** | Diversificação básica |
| 9 | **Re-setorização v3 granular temática** (23 setores) | Reflete teses de investimento do user (urânio, terras raras, hyperscalers, etc) |
| 10 | **Detecção D+2 automática** (inferência por data) | User não precisa marcar/desmarcar pendências |
| 11 | **Tratamento especial AGREGADO** (antecipar internamente) | Sem tocar no event log; some quando extrato real chegar |
| 12 | **CARTEIRA_RV como aba operacional separada** | Estação de trabalho diária; foco em caixa, liquidações, setor, performance |
| 13 | **TWR RV calculado como sub-portfolio isolado** | Permite comparação direta com IBOV/S&P500 |
| 14 | **Sem alertas estratégicos automáticos** | User explicitamente quer estratégia fluida; só alertas operacionais |
| 15 | **Validação ativa com 7 tipos de alertas** | Concentração, posição negativa, ativo não cadastrado, pendências, reconciliação caixa, etc |
| 16 | **Idempotência total** | Rodar 1 vez ou 100 vezes = mesma planilha |
| 17 | **Separação dados/lógica** | Script nunca edita EVENTOS / CAD_ATIVOS / HISTORICO_PRECOS |

---

## 7. Princípios operacionais (guardrails) <a name="7-princípios"></a>

Todo código novo deve respeitar:

1. **Confiabilidade**: Cálculos corretos e auditáveis. Bug em PEPS = todo P&L errado.

2. **Automação**: Reduzir trabalho manual ao mínimo. User não-técnico não pode
   ser obrigado a "marcar" ou "limpar" estados.

3. **Flexibilidade**: Adicionar/remover ativos deve ser trivial (1 linha no CAD_ATIVOS).
   Nada hardcoded.

4. **Auditabilidade**: Log estruturado de cada cálculo importante. User deve poder
   responder: "por que esse número?".

5. **Idempotência**: Estado do output só depende do estado do input. Sem efeitos colaterais.

6. **Validação ativa**: Sistema deve detectar inconsistências SOZINHO e alertar.
   Exemplo: saldo virtual residual diverge do real → alerta automático.

7. **Separação dados/lógica**: Engine nunca modifica fontes de verdade.

8. **Transparência sobre limitações**: Quando uma fonte falha (ex: yfinance BSLV39),
   sinalizar claramente — não fingir que o dado existe.

---

## 8. Anti-padrões a evitar <a name="8-anti-padrões"></a>

❌ **NÃO faça:**

1. **Modificar event log automaticamente.** NUNCA. Único caso aceito: user
   explicitamente editando via interface. Mesmo assim, com confirmação.

2. **Confiar cegamente em uma única fonte de preços.** O yfinance falhou para
   BSLV39 (retornou R$ 0). Implementar fallback (brapi.dev) e validação de sanidade.

3. **Hardcodar tickers ou regras.** Tudo deve sair do CAD_ATIVOS.

4. **Recalcular do zero a cada operação leve.** Para web, considere cache de
   posições/evolucao (recalcula só quando há novo evento).

5. **Esconder limitações.** Se BSLV39 = R$ 0, mostrar alerta explícito. Não
   esconder e fingir que dá pra calcular o patrimônio total.

6. **Alertas que travem a estratégia.** User não quer "você está com X% em setor Y,
   limite X-1%!". Quer apenas a FOTO clara da realidade.

7. **Migrar dados perdendo histórico.** Os 105 eventos e 47 preços manuais são
   resultado de trabalho cuidadoso. Migração deve ser 100% fiel.

8. **Quebrar reproducibilidade.** A planilha v2 atual produz resultados específicos
   (P&L vendas RV = R$ +3.629,15). A versão web deve produzir os MESMOS números.

---

## 9. Missão: Ferramenta web — visão do produto <a name="9-missão-web"></a>

### Necessidades do user (em ordem de prioridade)

1. **Adicionar eventos com facilidade** — não digitar em planilha; formulário inteligente
2. **Visualizar estação operacional RV** — caixa, liquidações D+2, distribuição setorial
3. **Acompanhar performance diária** — TWR, benchmarks, P&L
4. **Drill-down em ativos** — clicar em um ativo e ver histórico, gráfico, eventos
5. **Backup automático** — não perder dados nunca
6. **Acesso de qualquer lugar** — celular (quando estiver na corretora, na rua)

### Capacidades adicionais que web habilita (mas Excel não):

- **Gráficos interativos** (TWR vs benchmarks com hover, histograma de retornos mensais, treemap setorial)
- **Notificações** (caixa negativo, vencimento próximo, etc.)
- **Histórico versionado** (rollback de mudanças)
- **Multi-dispositivo** (mobile + desktop)
- **Validação em tempo real** ao digitar evento (ex: "esse ticker não está cadastrado, deseja cadastrar?")
- **Importação automática** de extratos B3 PDF/Excel (longo prazo)
- **Simulador "what-if"** (e se eu vendesse X? quanto sobra de caixa?)

### O que NÃO deve ser feito (escopo controlado):

- ❌ Trading automatizado / execução de ordens (não é robô)
- ❌ Recomendações de investimento (não é robô-advisor)
- ❌ Alertas estratégicos automatizados (user não quer)
- ❌ Multi-usuário inicialmente (single-user — Marcio)
- ❌ Reinventar o engine (reusar `atualizar_carteira.py` ao máximo)

---

## 10. Stack tecnológica recomendada <a name="10-stack"></a>

### Backend (Python — preserva engine atual)

- **FastAPI** — framework web moderno, async, OpenAPI nativo
- **SQLAlchemy 2.0** + **Alembic** — ORM e migrations
- **SQLite** inicialmente → PostgreSQL quando crescer
- **Pydantic v2** — validação de dados (já está embutido FastAPI)
- **uvicorn** — servidor ASGI

### Engine de cálculos

- **Reaproveitar `atualizar_carteira.py`** — modularizar em pacote `engine/`:
  - `engine/io.py` — leitura/escrita (mas via SQLite, não Excel)
  - `engine/posicoes.py` — PEPS
  - `engine/twr.py` — Modified Dietz + benchmarks
  - `engine/inferencia.py` — caixa virtual
  - `engine/atribuicao.py` — atribuição mensal
  - `engine/validacao.py` — alertas
  - `engine/precos.py` — fonte de preços (yfinance + brapi fallback + BCB SGS)

### Frontend — recomendação inicial: **Streamlit**

**Por quê Streamlit no MVP:**
- Python puro (sem JS) — reaproveita conhecimento
- Componentes prontos (forms, gráficos, tabelas)
- Deploy trivial (1 comando)
- Iteração rápida — bom para alinhar com user antes de investir em React

**Quando migrar para React/Next.js (Fase posterior):**
- Quando precisar de mobile real (PWA)
- Quando UI ficar limitada pelo Streamlit
- Quando user pedir features específicas que Streamlit não entrega bem

### Hospedagem

- **Fase MVP**: rodar local no Ubuntu do user (mesmo modelo atual)
- **Fase 2.5**: container Docker — rodar em VPS pessoal ou Railway/Fly.io
- **Acesso mobile**: via IP local ou Tailscale (sem precisar expor publicamente)

### Bibliotecas chave (Python)

```
fastapi[all]
sqlalchemy>=2.0
alembic
pydantic>=2
streamlit
yfinance
requests
pandas
numpy
plotly  # gráficos interativos
python-multipart  # uploads de arquivo
```

---

## 11. Plano faseado de migração <a name="11-plano-faseado"></a>

### Fase 2.1 — Migração de dados (Excel → SQLite)

**Objetivo:** Criar banco SQLite com mesmos dados da planilha, sem mudar
nenhum cálculo. Engine deve produzir mesmos números a partir do banco.

**Entregáveis:**
1. Schema SQLite (`alembic` migration inicial):
   - `ativos` (cad_ativos)
   - `eventos` (event log)
   - `precos_manuais` (historico_precos)
   - `cache_posicoes` (snapshot atual — recalculado)
   - `cache_evolucao` (séries diárias — recalculadas)
2. Script `migrate_from_excel.py` que importa o `Carteira_Clean_v2.xlsx`
3. Engine refatorado para ler de SQLite (era de Excel)
4. **Validação**: rodar engine sobre SQLite e comparar com planilha existente.
   Números devem bater **exatos**. Ver [Seção 12](#12-validação).

**Critério de pronto:** rodar `python -m engine.run` produz os mesmos números
da última rodada da planilha v2.

---

### Fase 2.2 — API REST sobre o engine

**Objetivo:** Expor o engine via HTTP. Permite que qualquer frontend
(Streamlit, React, mobile) consuma.

**Endpoints essenciais:**

```
GET    /api/v1/ativos                    # lista de ativos cadastrados
POST   /api/v1/ativos                    # cadastra novo ativo
PATCH  /api/v1/ativos/{ticker}           # edita ativo

GET    /api/v1/eventos?from=...&to=...   # lista eventos com filtros
POST   /api/v1/eventos                   # adiciona evento (revalida tudo!)
PATCH  /api/v1/eventos/{id}              # edita evento
DELETE /api/v1/eventos/{id}              # remove evento

GET    /api/v1/precos-manuais            # historico_precos
POST   /api/v1/precos-manuais            # adiciona ponto manual

POST   /api/v1/calcular                  # roda engine — força recálculo
GET    /api/v1/status                    # último cálculo, alertas pendentes

GET    /api/v1/posicoes                  # foto atual
GET    /api/v1/evolucao?from=...&to=...  # série temporal
GET    /api/v1/carteira-rv               # estação operacional RV
GET    /api/v1/atribuicao?mes=...        # atribuição mensal
GET    /api/v1/meta                      # projeção meta R$ 3MM
GET    /api/v1/dashboard                 # KPIs executivos

GET    /api/v1/precos/{ticker}?from=...  # série de preços (cache + API)
```

**Detalhe importante:** após POST/PATCH/DELETE em `/eventos`, o engine deve
**automaticamente** recalcular o cache de posições/evolucao. Pode ser síncrono
(MVP) ou via background task (depois).

---

### Fase 2.3 — Interface web MVP (Streamlit)

**Páginas mínimas:**

1. **🏠 Dashboard** — KPIs grandes (Patrimônio, TWR, Excesso CDI, Sharpe, Caixa)
   + gráfico TWR vs benchmarks
2. **📊 Carteira RV** — réplica da aba CARTEIRA_RV atual (4 seções)
3. **📋 Posições** — tabela filtrável/ordenável, com status liquidação
4. **➕ Novo Evento** — formulário com validação em tempo real:
   - Dropdown ativos (do CAD_ATIVOS)
   - Dropdown tipo (12 opções)
   - Date picker
   - Auto-cálculo: se preenchi qtd + preço, valor é auto. Se preenchi qtd + valor, preço é auto.
   - Botão "Salvar e recalcular"
5. **📈 Evolução** — gráfico TWR + tabela diária
6. **💰 Vendas Realizadas** — todas as vendas com P&L
7. **🎯 Meta** — projeção ano-a-ano interativa (slider para ajustar TWR estimado)
8. **⚙️ Configurações** — editar CAD_ATIVOS, premissas, etc.

**UX considerations:**

- Mobile-first onde fizer sentido (Dashboard, Posições, Novo Evento)
- Dark mode opcional
- Loading states claros (cálculos podem demorar 30s)
- Confirmação para ações destrutivas (deletar evento)
- "Última atualização: há 3min" sempre visível

---

### Fase 2.4 — Recursos avançados

- **Gráficos interativos com Plotly:**
  - TWR vs benchmarks (linha)
  - Atribuição mensal (waterfall)
  - Distribuição setorial (treemap)
  - Histograma de retornos mensais (positivos/negativos)
- **Importação de extrato B3** — upload PDF/Excel, parsing automático, preview, confirmar
- **Notificações:**
  - E-mail / Telegram quando caixa projetado fica negativo
  - E-mail mensal com resumo de performance
- **Backup automático:**
  - Diário do SQLite para nuvem (Drive, S3 — escolher)
  - Versionamento (mantém últimos 30 dias)
- **Histórico de mudanças** — log auditável de quem mudou o quê (single-user, mas útil)
- **Simulador "what-if"** — separar ambiente sandbox da carteira real

---

### Fase 2.5 — Polimento e deploy

- Migração para React/Next.js se necessário
- PWA (instalável no celular)
- Docker compose
- Deploy em VPS pessoal ou Railway
- Acesso via domínio próprio (carteira.marcio.com.br)
- HTTPS via Let's Encrypt

---

## 12. Números de validação (regression tests) <a name="12-validação"></a>

**Estes números devem bater na migração para web.** Se algum divergir,
**parar e investigar** — provavelmente bug.

### A) P&L de vendas realizadas

**Total acumulado:** R$ **+3.629,15**

| Data | Ativo | P&L R$ | P&L % |
|---|---|---|---|
| 28/01/2026 | BSLV39 | +R$ 300,10 | +20,01% |
| 13/04/2026 | AURA33 | +R$ 479,00 | +16,60% |
| 27/04/2026 | SEER3 | +R$ 243,55 | +14,23% |
| 04/05/2026 | PETR4 | +R$ 2.189,00 | +28,69% |
| 06/05/2026 | PRIO3 | +R$ 387,50 | +28,18% |
| 15/05/2026 | PLPL3 | +R$ 30,00 | +1,47% |

### B) Custos médios de posições ativas

| Ativo | Custo Médio Esperado |
|---|---|
| PETR4 | R$ 31,3100 (verificado antes da venda total) |
| WEGE3 | R$ 47,3182 |
| AURA33 (pós compra pendente) | R$ 138,7833 |
| AURA33 (até 13/04, antes da venda) | R$ 124,00 |
| BSLV39 (até 28/01, antes da venda) | R$ 124,99 |

### C) Patrimônio e performance (15/05/2026, com APIs reais)

| Métrica | Valor Esperado |
|---|---|
| Patrimônio Total | R$ 1.369.353,69 |
| Patrimônio Gerida | R$ 135.856 (aprox.) |
| Patrimônio FUNCEF | R$ 1.233.498 |
| Patrimônio RV (isolado) | R$ 68.319 (aprox.) |
| TWR Gerida YTD | +7,91% |
| TWR Total YTD | +3,88% |
| TWR RV YTD | +9,36% |
| CDI acumulado YTD | +5,04% |
| IBOV YTD | +10,43% |
| S&P 500 BRL YTD | -2,02% |

### D) Inferência de fluxos retroativos

| Métrica | Valor Esperado |
|---|---|
| APORTES inferidos | 22 unidades |
| Total inferido | R$ 37.582,59 |
| Saldo residual em 16/05 | R$ 2.070,00 |
| Saldo real reportado | R$ 2.450,48 |
| Desvio (esperado < R$ 500) | R$ 380,48 |

### E) Projeção META

| Métrica | Valor Esperado |
|---|---|
| TWR anualizado | +10,50% |
| Ano de atingimento (R$ 3MM) | 2032 |
| Patrimônio em 2032 | ~R$ 3.248.950 (108% da meta) |

### F) Outras validações estruturais

- 35 ativos cadastrados (1 FUNCEF + 30 RV + 4 RF/Caixa)
- 105 eventos no event log
- 47 pontos de preço manual em HISTORICO_PRECOS
- 23 setores diferentes na CARTEIRA_RV (granular temática)
- 18 vendas no total (6 de RV + 12 de RF cotizada — só RV vai pro relatório)
- 7 alertas atuais no Dashboard (5 pendências D+2 + 1 agregado provisório + 1 reconciliação caixa)

---

## 13. Arquivos de referência disponíveis <a name="13-arquivos"></a>

Você (Claude Code) tem acesso aos seguintes artefatos da Fase 1:

| Arquivo | Conteúdo | Para que usar |
|---|---|---|
| `Carteira_Clean_v2.xlsx` | Planilha completa com 10 abas | **Fonte de dados** para migração. Ler com `openpyxl`. |
| `atualizar_carteira.py` | Engine Python ~1.400 linhas | **Reaproveitar e modularizar.** Não reescrever do zero. |
| `instalar.py` | Script de instalação de dependências | Reusar como referência para `requirements.txt` |
| `GUIA_EXECUCAO.md` | Guia para user não-técnico | Entender o workflow atual antes de redesenhar |
| `RELATORIO_LEITURA_B3.md` | Análise das fontes B3 (extrato custódia, movimentações) | Entender de onde vêm os dados originais |
| `RELATORIO_LEITURA_MOVIMENTACOES.md` | Análise complementar | Idem |

**Acesso aos dados:** o Marcio tem acesso ao SaTotal, app Caixa, app Caixa Tem,
e ao portal de Renda Variável da Caixa. Para o futuro, podemos automatizar
parsing desses extratos.

---

## 14. Primeira tarefa sugerida <a name="14-primeira-tarefa"></a>

**Antes de fazer qualquer coisa nova, sugiro começar pela Fase 2.1 — Migração
para SQLite com validação rigorosa.**

### Passos:

1. **Setup inicial do projeto:**
   ```
   /carteira_clean_web/
       /backend/
           /engine/       # módulos refatorados de atualizar_carteira.py
           /api/          # FastAPI routers
           /db/           # SQLAlchemy models + alembic migrations
           /scripts/      # migrate_from_excel.py, recompute.py
       /frontend/         # Streamlit MVP
       /tests/
           /regression/   # testes que validam Seção 12
       /docs/
           ROTEIRO.md     # este documento
       pyproject.toml
       README.md
   ```

2. **Migrate from Excel:**
   - Ler as 3 abas-fonte (`CAD_ATIVOS`, `EVENTOS`, `HISTORICO_PRECOS`)
   - Validar integridade (todos os ativos de eventos estão no cad? tipos de evento são válidos? etc.)
   - Popular SQLite
   - Confirmar contagens: 35 ativos, 105 eventos, 47 preços

3. **Refatorar engine:**
   - Trocar `openpyxl.load_workbook` por queries SQLAlchemy
   - **Não mudar a lógica de cálculo** — só a fonte
   - Manter assinaturas de funções principais (`calc_posicoes_e_vendas`, `calc_twr_e_benchmarks`, etc.)

4. **Testes de regressão:**
   - Para cada métrica da [Seção 12](#12-validação), criar um teste pytest
   - Rodar engine sobre SQLite migrado e comparar com valores esperados
   - **Tolerância: 0** em valores exatos; **< 0.01%** para floats com arredondamento

5. **Comparar saída end-to-end:**
   - Rodar engine novo sobre SQLite
   - Comparar valores célula a célula com a planilha v2 atual
   - Listar quaisquer divergências (espera-se zero)

### O que você NÃO deve fazer na primeira tarefa:

- Construir frontend (Fase 2.3)
- Criar API REST (Fase 2.2)
- Adicionar novos cálculos (sempre é depois)
- Otimizar performance (engine atual roda em 30s, está bom para MVP)

### Quando concluir Fase 2.1, reportar:

- Migrate executou sem warnings?
- Testes de regressão: quantos passaram / falharam?
- Há divergências numéricas? Quais?
- Próximo passo proposto.

---

## 🤝 Como interagir com o user

Marcio:
- É inteligente e curioso, mas não técnico
- Prefere explicações com tabelas, exemplos numéricos, e analogias concretas
- Detalhista — quer entender por que algo é de um jeito
- Aceita complexidade quando justificada, mas valoriza simplicidade no uso final
- Tem expectativa profissional sobre a ferramenta (não é hobby)

**Sugestões de boa comunicação:**

- ✅ Mostrar resultados numéricos antes de "vai dar certo"
- ✅ Reconhecer trade-offs explicitamente
- ✅ Pedir confirmação antes de decisões arquiteturais grandes
- ✅ Apresentar opções (A/B/C) quando houver tradeoffs reais
- ✅ Usar tabelas markdown para clareza
- ❌ Não introduzir jargões sem explicar
- ❌ Não fazer decisões silenciosas sobre estrutura
- ❌ Não pressupor que ele entende terminologia técnica

---

## 📝 Glossário pessoal do Marcio (curiosidades úteis)

- Ele chama a planilha de "minha carteira", não "o workbook"
- A pasta dele é `~/Carteira/`
- Ele usa o Terminal apenas para rodar os comandos que damos
- Ele entende conceitos financeiros (TWR, custo médio, P&L, etc.) — não é leigo nisso
- Ele NÃO entende: ORM, migrations, container, REST, Pydantic, etc.
- Tom desejado: técnico nos cálculos, simples nas explicações

---

## 🎬 Resumo executivo (TL;DR)

Você (Claude Code) está continuando o **Projeto Carteira Clean**, transformando
uma planilha Excel + script Python em **ferramenta web automatizada**.

**Bagagem da Fase 1:**
- Planilha com 10 abas (3 fontes + 7 geradas)
- Engine Python ~1.400 linhas, modular e funcional
- 105 eventos, 35 ativos, 47 preços manuais
- Cálculos validados (P&L = R$ +3.629,15, TWR = +7,91%, patrimônio = R$ 1,37MM)

**Próxima missão:**
- Fase 2.1: migrar Excel → SQLite preservando 100% dos números
- Fase 2.2: API REST sobre o engine
- Fase 2.3: Streamlit MVP
- Fase 2.4+: avançados (gráficos Plotly, importação automática, mobile)

**Princípios que NUNCA devem ser quebrados:**
1. Event log é fonte única de verdade — nunca modificar automaticamente
2. Engine deve produzir os mesmos números da planilha v2 atual
3. User não-técnico — UX deve compensar
4. Validação ativa — sistema deve se auto-detectar inconsistências

**Comece pela Fase 2.1 e me reporte ao concluir.** Boa sorte! 🚀
