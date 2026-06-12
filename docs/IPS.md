# IPS — Investment Policy Statement
## Carteira Gerida v1.0 · junho 2026

---

## 1. Escopo e Perímetro

Esta IPS governa exclusivamente a **Carteira Gerida** — ativos sob gestão ativa do titular, negociados em conta corretora (B3, BDRs, ETFs, Renda Fixa direta).

A **FUNCEF** (e o CAIXA FIC FUNC vinculado a ela) está **fora da atribuição**: é monitorada como patrimônio separado, mas não entra no cálculo de benchmark, bandas ou rebalanceamento desta IPS. O campo `composite = "FUNCEF"` marca esses ativos no sistema.

---

## 2. Blocos Estratégicos

| Bloco | Alvo | Banda | Benchmark |
|-------|------|-------|-----------|
| Swing Trade | 30% | ±10 pp | IBOV |
| Growth | 20% | ±10 pp | Nasdaq (BRL) |
| Defensivos | 20% | ±5 pp | Ouro (BRL) |
| Renda Fixa | 30% | ±5 pp | CDI |

### 2.1 Swing Trade — alvo 30%, banda 20%–40%

Ações brasileiras negociadas na B3 e ETFs de índices domésticos. Teses táticas com horizonte de semanas a meses, aproveitando volatilidade de curto prazo com fundamento macroeconômico ou de resultado. Benchmark: IBOV.

**Decisões conscientes de classificação neste bloco:**

- **DIVO11** (ETF Dividendos BR): buy-and-hold de ações brasileiras pagadoras de dividendos. Medido contra IBOV — correto, pois a carteira do fundo é integralmente de ações da B3. O baixo giro não contradiz o bloco; "Swing" nomeia o conjunto de exposição doméstica em RV, não o estilo de operação.

- **AURA33** (BDR — Aura Minerals, mineradora de ouro): beta de Renda Variável, não replica ouro físico. Em Defensivos distorceria o efeito-seleção do bloco vs. benchmark Ouro BRL; em Swing Trade compete contra o IBOV, que é o benchmark correto para uma ação de mineradora listada.

### 2.2 Growth — alvo 20%, banda 10%–30%

BDRs e ETFs de teses estruturais de longo prazo: inteligência artificial, semicondutores, aeroespacial, robótica, biotecnologia, fintechs digitais, transição energética (lítio, urânio, terras raras). Horizonte multi-ano; tolerância a volatilidade elevada. Benchmark: Nasdaq Composite (cotado em BRL).

### 2.3 Defensivos — alvo 20%, banda 15%–25%

Instrumentos que replicam diretamente o preço de metais preciosos (ETFs de ouro/prata, fundos indexados a commodities). Função: proteção de patrimônio em crises e hedge cambial. Benchmark: Ouro à vista (cotado em BRL).

> Ações de mineradoras (ex: AURA33) são classificadas em Swing Trade — o bloco Defensivos é reservado para instrumentos que replicam o metal, não para empresas do setor.

### 2.4 Renda Fixa — alvo 30%, banda 25%–35%

Instrumentos pós-fixados, prefixados e IPCA+ de baixo risco de crédito: Tesouro Direto, LCI, fundos conservadores. Função: âncora de liquidez e carrego. Benchmark: CDI.

---

## 3. Benchmark Composto da Carteira Gerida

```
Benchmark = 30% IBOV + 20% Nasdaq(BRL) + 20% Ouro(BRL) + 30% CDI
```

Usado para medir a performance agregada da Carteira Gerida em janelas de 12 meses.

---

## 4. Caixa — Categoria Observada

Caixa (recursos disponíveis em conta, não alocados em nenhum bloco) é **monitorado mas sem alvo de alocação**.

- **Caixa elevado temporário**: sinal de que o bloco Swing Trade está aguardando entrada — ponto de compra ainda não identificado ou condição de mercado adversa. Aceitável por até 4–6 semanas.
- **Caixa persistente** (> 6 semanas): indica que o alvo de 30% em Swing Trade não está sendo executado. Requer revisão da tese ou redução do alvo do bloco.

Caixa operacional de curto prazo (ex: CAIXA FIC FUNC como reserva de liquidez imediata) pode ser marcado como `FORA_IPS` e excluído da atribuição.

---

## 5. Regras de Rebalanceamento

- **Gatilho**: qualquer bloco fora de sua banda.
- **Ação**: rebalancear até o alvo central no prazo de 30 dias, priorizando aportes novos antes de vendas.
- **Exceção**: em tendência clara de mercado, pode-se manter na extremidade da banda por até 60 dias antes de forçar venda.

---

## 6. Revisão desta IPS

Esta IPS deve ser revisada anualmente ou sempre que houver mudança relevante no perfil de risco, horizonte de investimento ou composição do patrimônio total.

**Versão 1.0** — criada em junho 2026.
