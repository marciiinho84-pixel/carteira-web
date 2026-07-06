# Registro de Implementação — App Minha Carteira

*Log detalhado de execução. Fases 1-5 congeladas (o que foi feito).*
*Fases 6-7 atualizáveis (briefs de fatias futuras).*
*Polimento em andamento: ver polimento/*.md*
*Visão macro: ver 06-plano-implementacao.md*

---

# FASES 1-5 — EXECUTADAS (congelado)

## Fase 1 — Substrato exógeno ✅

### Fatia 1 — Índices setoriais B3 ✅
*Commits: 117a85a, 4de1f04*
- 8 índices setoriais B3, tabela append-only, cron diário
- Tool: `analise_aderencia_setorial`
- Maestro v2 com 11 tools MCP

### Fatia 2 — Fundamentos ao vivo ✅
*Parte do commit 8e3264b*
- **Desvio:** plano previa APIs pagas → yfinance estendido (gratuito)
- Avaliação real: yfinance cobre 8-9 dos 10 indicadores. ROIC calculado manualmente
- Migration 0004: tabela `fundamentos` append-only
- Tool: `consultar_fundamentos`. Cron 22h15 UTC

### Fatia 3 — Macro e eventos ✅
*Commit: 1525bd9*
- BCB SGS + Olinda Focus + yfinance eventos (tudo gratuito)
- Migration 0006: `macro_indicadores` + `eventos_corporativos`
- Tools: `consultar_macro`, `consultar_eventos_corporativos`
- Crons: macro 22h20, Focus seg 12h

---

## Fase 2 — Disciplinas de gestão ✅

### Fatias 4+5+6+7 — em bloco ✅
*Commit: 8e3264b*
- Migration 0005: `teses`, `diario_decisoes`, `regra_aportes`
- Fatia 4: teses com invalidação → `consultar_teses`
- Fatia 5: diário de decisão → `consultar_diario`
- Fatia 6: risco ex-ante → `risco_carteira`
- Fatia 7: aporte/caixa → `disciplina_caixa`

---

## Fase 3 — Inferência comportamental ✅

### Fatia 8 — Perfil comportamental ✅
*Migration 0007: `metricas_comportamento`*
- Turnover, holding, frequência, concentração (HHI)
- Tool: `perfil_comportamental`

### Fatia 9 — Dito vs. feito ✅
- 4 cruzamentos. Refinamento: n_encerradas==0 → INFO
- Divergências reais: Defensivos 9.6% (abaixo banda), Growth holding 39d
- Tool: `divergencias_dito_feito`

### Fatia 8b — Vieses comportamentais ✅
- 5 vieses nomeados (disposição, overtrading, sub-diversificação, clustering, trend chasing)
- Viés nomeado na saída (decisão de produto)
- Tool: `vieses_comportamentais`

---

## Fase 4 — Instrumentistas ✅

*Decisão D2: tools sob maestro, não agentes separados*

### Fatias 10-13 + Glossário — em bloco ✅
*Migration 0008: `matriz_sensibilidade` (15 seeds)*
- Fatia 10 — Fundamentalista (4 dimensões): `analise_fundamentalista`, `screening_fundamentalista`, `comparar_multiplos`
- Fatia 11 — Setorial/macro: `contexto_setorial`, `regime_mercado`
- Fatia 12 — Técnico (votação -1/0/+1, Plotly): `analise_tecnica`, `grafico_tecnico`
- Fatia 13 — Notícias/intel macro: `noticias_ativos`, `impacto_macro`
- Glossário (24 definições): `consultar_glossario`

**Total: ~31 tools MCP**

---

## Ações fora de fatia ✅

- **Navbar:** 18→10 páginas. Absorções + renomeações.
- **bloco_ips:** formalizado na CAD_ATIVOS (38 ativos classificados)
- **Rotação MCP_TOKEN**

---

## Fase 5 — Interface React ✅

### Fatia 14 — Infra ✅
**Desvios do plano:**
| Planejado | Executado | Motivo |
|---|---|---|
| Cloud SQL | PostgreSQL Docker na VM | Custo zero |
| Cloud Run | FastAPI na VM | Sem necessidade |
| Vercel | Next.js Docker na VM + Caddy | Unificou infra |
| Magic link | Google OAuth (NextAuth.js) | UX |

Migração SQLite→PostgreSQL: 38 ativos, 7993 cotações, 136 eventos, 49 conversas.
Problemas pós-migração corrigidos: precos.py hardcoded, sequences, IBOV duplicado, backup.py, Focus URL, DetachedInstanceError.

### Fatia 15 — Sala de Comando ✅
- 5 seções: KPIs, orquestra, semáforos teses, espelho, progress-to-goal
- Paleta TradingView

### Fatia 16 — Maestro no React ✅
- **Desvio:** CopilotKit → implementação customizada SSE + Anthropic tool use
- 31 tools, 8 componentes, hook useAutomacao L1-L4
- Auth: Google OAuth, trustHost:true para Caddy

### Fatia 16.1 — Correção "Por quê?" ✅
- Bug do expand das observações corrigido

### Fatia 17 — Migração completa + drill-down ✅
*Commit: bcec347*
- 10 páginas migradas com drill-down
- DetalheAtivo: técnico + fundamentos + notícias + tese
- Drill-down bloco IPS → ativos
- Deploy automático GitHub Actions (Workload Identity Federation)
- Streamlit mantido em paralelo (/streamlit/)

### Paridade Streamlit → React ✅
- 11 itens (Grupos A+C+B+D) implementados e deployados
- Bugs corrigidos: CAIXA LCI (filtro qtd>0→valor_atual>0), FUNCEF no Risco, bloco_ips em PosicaoOut, fallback AGREGADO_PRIVADO, patrimonio_funcef ao vivo no Dashboard
- Importar Extrato: fluxo 2 etapas (upload→preview→confirmar)
- Meta: aporte_anual dinâmico
- Deduplicação cotas + UNIQUE CONSTRAINT

---

# FASES FUTURAS (atualizável)

## Fase 6 — Temperamento + mobile

### Fatia 18 — Mobile + push
Habilita §4 (temperamento). Push para: violação IPS, invalidação
de tese, divergência dito-vs-feito, cash drag.
Decisão pendente D11: PWA vs. nativo (React Native/Expo).

### Fatia 19 — Portão de pertinência + ensaio contínuo
"A orquestra nunca para." Jobs de fundo, portão fundamentado +
pertinente, autonomia agendada.
Decisão pendente D7: pertinência configurada + aprendida.
**Metade A (alertas) antecipada no polimento do Maestro.**

## Fase 7 — Extensões

| Fatia | Entrega |
|---|---|
| 20 | IRPF (DARF, isentômetro, declaração) |
| 21 | Agenda visual de proventos |
| 22 | Comparador interno |
| 23 | Rebalanceamento inteligente (L3) |

---

# REFERÊNCIA

## Glossário de indicadores
*24 definições em engine/glossario.py, tool consultar_glossario*

### Fundamentalistas
| Indicador | O que é |
|---|---|
| P/L | Preço ÷ Lucro por Ação |
| P/VP | Preço ÷ Valor Patrimonial |
| EV/EBITDA | Valor empresa ÷ EBITDA |
| ROE | Lucro Líq. ÷ PL |
| ROIC | NOPAT ÷ Capital Investido |
| Margem EBITDA | EBITDA ÷ Receita |
| Margem Líquida | Lucro Líq. ÷ Receita |
| Dív.Líq/EBITDA | (Dívida-Caixa) ÷ EBITDA |
| DY | Dividendos 12m ÷ Preço |

### Técnicos
| Indicador | O que é |
|---|---|
| MM 20/50/200 | Médias móveis |
| RSI 14 | Força Relativa (0-100) |
| MACD | Diferença de EMAs |
| Bollinger | Bandas de volatilidade |
| Rating (-1 a +1) | Média dos votos dos indicadores |

### Comportamentais
| Viés | Como é medido |
|---|---|
| Efeito Disposição | Holding vendas lucro vs. prejuízo |
| Overtrading | Turnover por bloco IPS |
| Sub-diversificação | HHI + peso top-5 |
| Clustering Temporal | Desvio padrão frequência mensal |
| Trend Chasing | Retorno 30d antes vs. depois da compra |

---

## Polimento do Maestro ✅ (pós-Fase 5)

*Detalhes em polimento/01-maestro.md. Resumo do que foi entregue:*

- **Camada 1 — Bugs:** tela do ativo (DetalheAtivo lia chave errada de
  fundamentos) e gráfico técnico no chat (StaticFiles + evento
  TOOL_CALL_RESULT) corrigidos
- **Camada 2 — Temperamento:** system prompt ajustado para objetividade,
  sem preâmbulos, preservando honestidade intelectual
- **Camada 3 — Tools de escrita L2:** registrar_tese, registrar_decisao_diario,
  atualizar_tese, invalidar_tese, criar_alerta, verificar_alertas,
  forcar_coleta. Migration: tabela `alertas`. Página Alertas criada.
- **Camada 4 — Web search:** pesquisar_web via Brave Search API
  (DuckDuckGo bloqueou IP de datacenter GCP). Hierarquia de fontes
  em 5 tiers no system prompt. Plano free 2.000 buscas/mês.

**Total de tools após o polimento: ~40 tools MCP**

---

*Última atualização: 28/06/2026*
