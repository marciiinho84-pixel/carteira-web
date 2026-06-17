# Plano de Implementação — App Minha Carteira Inteligente

*Deriva dos documentos 01-conceito a 05-brief-fatia-1 e da IPS v1.0.*
*Organizado em fatias verticais finas. Cada fatia usável antes da seguinte.*
*O micro de cada etapa é discutido no chat antes do brief de implementação.*

---

## Estado atual (ponto zero)

| Camada | Status | O que existe |
|---|---|---|
| 1a — endógeno | ✅ madura | Event sourcing, TWR GIPS/Modified Dietz, Brinson-Fachler verificado (0.005pp), 38 ativos, 5 fontes de preço, cron diário, backup GCS |
| 1b — exógeno | 🟡 mínimo | 8 índices setoriais B3 numéricos (Fatia 1). Tools Brapi/BCB = lookup efêmero, não substrato |
| 2 — memória declarada | 🟡 parcial | IPS v1.0, memória FIFO 50, histórico 20 msgs. Sem teses, sem diário |
| 2 — memória inferida | 🔴 zero | Event log existe e é rico, mas usado só para performance. Nenhuma leitura de comportamento |
| 3 — maestro | 🟡 v2 operacional | 11 tools MCP, prompt propositivo, modelo Opus 4.8. Zero instrumentistas |
| 4 — interface | 🔴 Streamlit | Teto de design reconhecido. React decidido, não iniciado. Mobile/push inexistente |

**Disciplinas de gestão (§7 do conceito):**

| Disciplina | Status |
|---|---|
| §7.1 IPS | ✅ v1.0 (4 blocos, bandas, benchmark composto) |
| §7.2 Teses com invalidação | 🔴 não iniciada |
| §7.3 Diário de decisão | 🔴 não iniciado |
| §7.4 Risco ex-ante | 🔴 não iniciado |
| §7.5 Atribuição Brinson | ✅ implementada (Fase 3.1) |
| §7.6 Disciplina de aporte/caixa | 🔴 não iniciada (regras de caixa na IPS §4 existem, monitoramento não) |

**Implementado (commits de referência):**
- Fatia 1 (117a85a): substrato setorial + aderência IPS + tool MCP
- Maestro v2 + migração MCP (4de1f04): 11 tools, regra FUNCEF, -225 linhas

**Pendência de higiene:** rotação do MCP_TOKEN (exposto em conversa anterior).

---

## Propriedade transversal — APRENDER

Antes das fatias, o princípio que atravessa tudo e que o sistema atual **não tem** (02-estrutura):

> O sistema aprende. Aprende sobre **o mundo** (1b) e sobre **o usuário** (2).
> Um agente que lê e esquece a cada turno nunca passa de leitor de planilha.

Cada fatia abaixo é avaliada por: **o maestro ficou mais capaz de traduzir entre as duas lentes?**

## Engenharia do ensaio — 3 padrões transversais

Governam toda fatia que envolve trabalho de fundo ou observação automatizada (02-estrutura):

1. **Maker vs. Checker** — validador determinístico antes de qualquer observação chegar ao usuário. Confere que métricas vieram de tools e que contas fecham. Vive no maestro, nunca entre instrumentistas.
2. **Estado persistido entre execuções** — cada job registra o que fez e aprendeu. Sem isso, o loop "lê e esquece" na camada operacional.
3. **Teste das 4 condições antes de automatizar** — repetição real ≥ semanal, verificação automatizável, custo de tokens justificado, acesso a dados/ferramentas.

**Regra de custo:** modelo barato para volume/digestão; modelo forte para síntese do maestro.

## Nível de autonomia — Maestro = L3

O maestro recomenda e contextualiza dentro de parâmetros (IPS, teses); o humano aprova e decide. Consistente com §5 do conceito ("a decisão é sempre do usuário"). Validado pela literatura (Self-Driving Portfolio, Ang 2026).

---

## Cadeia de dependências

```
1a endógena ✅
1b exógena (Fases 1-2)──────────────────────┐
                                             │
2 declarada (Fase 3)─────────────────────────┤
                                             ├── APRENDER (mundo + usuário)
2 inferida (Fase 4)──────────────────────────┤     │
                                             │     └── habilita portão de pertinência
                                             │              │
3 instrumentistas ×4 (Fase 5)────────────────┘              │
  ├─ fundamentalista (depende 1b fundamentos)               │
  ├─ setorial/macro (depende 1b macro)                      │
  ├─ técnico (depende 1a cotações — já pronto)              │
  └─ notícias/intel macro (depende 1b notícias + macro)     │
                                                            │
3 temperamento (Fase 7)─────────── depende de portão ───────┘
         │
4 interface React (Fase 6)──── pode iniciar em paralelo com Fase 5
         │
4 mobile + push (Fase 7)──── habilita temperamento completo
```

---

## Fase 1 — Substrato exógeno: fundamentos e macro (Camada 1b)

*Realiza: "janela para fora" (§2). Torna instrumentistas futuros especialistas.*
*Capacidades de IA usadas: ferramentas e dados ao vivo (cap. 3).*

### Fatia 2 — Fundamentos ao vivo via API

**Objetivo:** os ~38 ativos da carteira têm fundamentos persistidos (P/L, ROE, DY, margens, endividamento), não lookup efêmero. Nova tool MCP para o maestro consultar.

**Peças:**
- Avaliar APIs: Dados de Mercado (candidata preferencial — documentação real) e Partnr (alternativa — ressalva de marketing). Critérios: cobertura dos 38 ativos, limites, preço, estabilidade, qualidade real dos dados.
- Tabela de fundamentos append-only (mesma mecânica da Fatia 1 — tabela `cotacoes`, cron, Alembic).
- Tool MCP `consultar_fundamentos` — retorna indicadores do ativo com data de referência.
- Brapi permanece para cotações e preços (não substituir o que funciona).

**Decisões a tomar:**
- Qual API vence a avaliação.
- Brapi convive com a nova API ou é substituída?
- Maestro cruza fundamentos direto (como na Fatia 1) ou já nasce o instrumentista fundamentalista? (Regra: substrato *e* método. Método = ler demonstrativos, comparar com histórico/setor. Se a API entrega demonstrativos, o fundamentalista tem substrato e método → passa no teste de admissão.)

### Fatia 3 — Macro e eventos corporativos persistidos

**Objetivo:** o contexto macro e os eventos corporativos sedimentam em vez de evaporar.

**Peças:**
- Indicadores macro persistidos: Selic, IPCA, câmbio, curva de juros, Focus. Fonte: BCB SGS (já usado) + API que venceu na Fatia 2 se cobrir macro.
- Eventos corporativos: fatos relevantes, datas de balanço, dividendos programados. Fonte: API escolhida.
- Tabelas append-only, cron periódico.

**Decisões a tomar:**
- Granularidade do macro persistido (por indicador: Selic = diária, Focus = semanal, PIB = mensal).
- Eventos corporativos: tabela própria ou extensão da tabela setorial?
- O que é "macro suficiente" para o maestro sem overload?

### Processo paralelo — NotebookLM como offload

**Não é fatia de código.** Processo operacional: o usuário digere calls de RI, entrevistas, releases no NotebookLM (ou Cowork), e o produto curado entra como tese ou observação na Fase 3 abaixo. Digestão é insumo; tradução pela lente da tese é produto (02-estrutura).

**Restrição técnica:** não há API pública do NotebookLM (só Enterprise). Sem automação no pipeline — humano-no-loop, episódico. Não entra no "ensaio contínuo."

---

## Fase 2 — Disciplinas de gestão restantes (Camada 2, parte declarada)

*Realiza: §7 do conceito — compromissos que transformam a IA de comentarista em auditora.*
*Custo baixo, valor alto: formulários + tabelas SQLite via Alembic (02-estrutura).*
*Capacidades de IA usadas: memória persistente (cap. 2), ferramentas (cap. 3).*

### Fatia 4 — Teses com critérios de invalidação (§7.2)

**Objetivo:** toda posição pode ter uma tese com "o que me provaria errado." Instrumentistas futuros vigiam condições de invalidação, não notícias soltas. Elimina mover a trave.

**Peças:**
- Tabela `teses` (ativo, bloco IPS, racional, cenário esperado, critério de invalidação, data de criação, status ativo/invalidada/encerrada).
- Formulário de registro no Streamlit (ou via assistente).
- Tool MCP `consultar_teses` — o maestro lê teses ativas e confronta com substrato.

**Decisões a tomar:**
- Tese por ativo, por bloco IPS, ou ambos?
- Invalidação: binária (sim/não) ou graduada (sinal amarelo/vermelho)?
- Checagem: maestro via tool sob demanda, ou job de fundo agendado (teste das 4 condições)?

### Fatia 5 — Diário de decisão (§7.3)

**Objetivo:** no momento do "enter": racional, cenário, convicção. É o "dito" do dito-vs-feito (§3). Habilita post-mortem de processo.

**Peças:**
- Tabela `diario` (data, ativo, ação, racional, cenário esperado, convicção, resultado posterior — preenchido depois).
- Registro pode ser integrado ao fluxo de COMPRA/VENDA existente.
- Tool MCP `consultar_diario` — maestro acessa histórico de decisões.

**Decisões a tomar:**
- Obrigatório em toda operação ou só nas marcadas como "deliberadas"?
- Convicção: escala numérica (1-5) ou texto livre?
- Resultado posterior: preenchido manual ou calculado automaticamente (preço de entrada vs. preço atual)?

### Fatia 6 — Risco ex-ante (§7.4)

**Objetivo:** exposição efetiva por fator, orçamento de drawdown, escala de liquidez, cenários de stress sobre a carteira viva.

**Peças:**
- Cálculo de exposição por fator (setor, moeda, classe) sobre posições atuais — reaproveita projeções existentes.
- Drawdown máximo histórico da Carteira Gerida (já tem série TWR diária).
- Escala de liquidez: classificação por ativo já existe na CAD_ATIVOS (campo Liquidez).
- Cenários de stress: simulação "se IBOV cair X%, quanto a carteira perde?" — usa betas estimados.
- Tool MCP `risco_carteira`.

**Decisões a tomar:**
- Quais fatores de risco no MVP (setor, moeda, classe — 3 suficientes)?
- Cenários de stress: fixos (IBOV -20%, USD +30%) ou configuráveis pelo usuário?
- Frequência de atualização: diária (cron) ou sob demanda?

### Fatia 7 — Disciplina de aporte e caixa (§7.6)

**Objetivo:** regra escrita para aportes (programado vs. oportunístico com critério) + monitoramento de cash drag. A IPS §4 já define regras temporais de caixa (4-6 semanas aceitável, >6 semanas requer revisão); esta fatia implementa o monitoramento.

**Peças:**
- Regra de aporte registrada (frequência, valor, critério de oportunismo).
- Alerta de cash drag: caixa % da carteira × tempo acima do limiar (IPS §4).
- Integra com os 5 alertas operacionais já existentes no dashboard.

**Decisões a tomar:**
- Aporte programado tem meta mensal fixa ou % da renda?
- Alerta de cash drag: integrado ao maestro (observação) ou só no dashboard?

---

## Fase 3 — Inferência comportamental (Camada 2, parte inferida)

*Realiza: "espelho para dentro" (§2), "dito vs. feito" (§3), portão de pertinência (§4).*
*O diferencial que ninguém no mercado tem (02-estrutura: consolidação está saturada; ninguém tem espelho comportamental).*
*Capacidades de IA usadas: executar código (cap. 4), memória persistente (cap. 2).*

**Depende de:** Fase 2 (teses e diário = o "dito") + 1a (event log = o "feito").

### Fatia 8 — Leitura do event log para padrões de comportamento

**Objetivo:** o event log — hoje usado só para performance — passa a ser lido para extrair padrões do *investidor*: como ele se comporta, não como a carteira performa.

**Peças:**
- Módulo de inferência que lê o event log e computa métricas de comportamento, persistidas como série temporal mensal:
  - Giro real (turnover) por bloco IPS.
  - Holding period médio por bloco.
  - Frequência de operações.
  - Concentração efetiva vs. declarada (IPS).
- Tool MCP `perfil_comportamental`.

**Referência conceitual:** FinCon/FinMem (02-estrutura, fontes) — memória em camadas com recência + relevância. Métricas de curto prazo (último mês), médio (último trimestre), longo (histórico completo).

**Decisões a tomar:**
- Quais métricas de comportamento no MVP (as 4 acima suficientes?).
- Atualização: cron mensal ou sob demanda?
- Maestro fala sobre padrões: L3 (reporta fato, você decide) — confirmar.

### Fatia 9 — Cruzamento dito-vs-feito

**Objetivo:** o insight central do conceito. Cruza o "feito" (Fatia 8) com o "dito" (Fatias 4-5): "sua tese de WEGE3 dizia horizonte de meses; seu holding period real é 18 dias." Confronto sem juízo.

**Peças:**
- Módulo que compara: tese declarada × comportamento inferido; IPS declarada × concentração real; convicção no diário × resultado.
- Output estruturado: divergência nomeada, dados de ambos os lados, sem recomendação.
- Tool MCP `divergencias_dito_feito`.

**Decisões a tomar:**
- Divergência reportada proativamente ou só sob demanda?
- Tom: fato puro ("holding period = 18d vs. tese = meses") ou com contexto temporal ("ocorreu N vezes")?
- Esta fatia é onde o portão de pertinência começa a ser necessário — a decisão de *quando* reportar uma divergência já é juízo. Mecanismo?

---

## Fase 4 — Instrumentistas (Camada 3 expandida)

*Realiza: metáfora da orquestra (§6), instrumentistas independentes (§5).*
*Capacidades de IA usadas: conversar/raciocinar (cap. 1), executar código (cap. 4), processar documentos (cap. 6), gerar artefatos (cap. 7).*

**Depende de:** 1b rico (Fase 1) + memória funcional (Fases 2-3). Exceção: o técnico (Fatia 12) depende apenas de 1a (cotações), que já está madura — pode ser antecipado.

**Decisão prévia (arquitetura de agentes):** orquestra plural (agentes separados com prompts e instâncias próprias) vs. maestro único com tools agrupadas por especialidade. A leitura 3 (03-leituras) aponta o `ant` CLI / Agentes Gerenciados Anthropic como **candidato mais sólido** — agente definido como configuração versionável, sem frameworks de terceiros. Decisão a tomar antes desta fase.

**Teste de admissão** (02-estrutura): instrumentista só nasce se tem **substrato e método próprios.** Se não passa, é tool de um agente existente.

**Orquestra planejada — 4 instrumentistas:**

| # | Instrumentista | Substrato | Método | Depende de |
|---|---|---|---|---|
| 10 | Fundamentalista | Fundamentos API (Fatia 2) + demonstrativos CVM | Ler balanço, múltiplos, comparar com histórico/setor | Fase 1 |
| 11 | Setorial/macro | Índices setoriais (Fatia 1) + macro (Fatia 3) | Contextualizar setores com macro, identificar regime | Fase 1 |
| 12 | Técnico | Cotações diárias (1a, já madura) | Análise técnica + geração de gráficos anotados | **Nenhuma** (1a pronta) |
| 13 | Notícias/intel macro | Feed notícias + macro (Fatias 2-3) + carteira/watchlist | Monitorar notícias + inferir impacto macro→micro | Fase 1 |

### Fatia 10 — Fundamentalista

**Substrato:** fundamentos da API (Fatia 2) + demonstrativos CVM.
**Método:** ler balanço, calcular múltiplos, comparar com histórico e setor, vigiar critérios de invalidação de teses (§7.2).
**Output:** reporta ao maestro, sem ouvir outros instrumentistas. Fatos fundamentalistas, não recomendações.

**Decisões a tomar:**
- Agente separado ou grupo de tools? (Depende da decisão de arquitetura acima.)
- Modelo: barato para análise de volume (Haiku/Sonnet), forte para síntese (Opus)?
- Escopo: ativos da Carteira Gerida, watchlist, ou ambos?

### Fatia 11 — Setorial/macro

**Substrato:** índices setoriais (Fatia 1), macro persistido (Fatia 3).
**Método:** contextualizar movimentos dos setores com macro, identificar regime, confrontar com exposição da carteira.
**Output:** contexto setorial-macro reportado ao maestro.

**Decisões a tomar:**
- Mesmo framework da Fatia 10.

### Fatia 12 — Técnico (análise gráfica + geração de gráficos)

**Substrato:** séries de cotações diárias (tabela `cotacoes`, já madura), volume, histórico OHLCV.
**Método:** análise técnica — suportes, resistências, médias móveis, padrões gráficos, indicadores (RSI, MACD, Bollinger). Gera **pontos de entrada, saída e alvos de preço**. Produz **gráficos anotados** que demonstram visualmente a tese gráfica — não apenas números, mas a imagem que sustenta a leitura.
**Output:** reporta ao maestro com gráfico + tese técnica. Independente. O maestro apresenta convergência ou divergência entre leitura técnica e fundamental ao usuário.

**Teste de admissão:** ✅ passa. Substrato = cotações existentes (sem API nova). Método = análise técnica + geração de gráficos (distinto de todos os outros).

**Peças:**
- Módulo de cálculo de indicadores técnicos (suportes/resistências, MMs, RSI, MACD, Bollinger).
- Gerador de gráficos anotados (candlestick com marcações de entrada/saída/alvo, linhas de tendência, zonas de suporte/resistência).
- Tool MCP `analise_tecnica` — recebe ticker, retorna leitura + gráfico.
- Gráfico como artefato visual entregue ao usuário (capacidade 7: gerar artefatos).

**Decisões a tomar:**
- Mesmo framework de agente das Fatias 10-11.
- Indicadores no MVP (candidatos: suporte/resistência, MM 20/50/200, RSI 14, MACD, Bollinger 20,2).
- Gráfico: imagem estática (PNG) ou interativo (Plotly HTML)?
- Timeframe default: diário? Suportar múltiplos (semanal, mensal)?
- Integração com teses (§7.2): leitura técnica pode informar critérios de invalidação? (Ex.: "se perder suporte de R$X, tese invalidada.")

### Fatia 13 — Notícias e inteligência macro

**Substrato:** feed de notícias da API escolhida (Fatias 2-3) + macro persistido + carteira e watchlist do usuário.
**Método:** dois movimentos:
1. **Monitorar notícias relevantes** para ativos em carteira e watchlist — filtrar por ativo, tag, relevância. Vigiar o que toca posições reais, não curar tudo.
2. **Inferência macro → micro** — correlacionar mudanças macro (juros, câmbio, política fiscal, regulação) com impacto provável em setores e ativos específicos. Ex.: queda na Selic → beneficia construção civil (empresas alavancadas, financiamento imobiliário) e pode pressionar bancos (spread). Alta do dólar → beneficia exportadoras (PRIO3, WEGE3), pressiona importadoras.
**Output:** reporta ao maestro com notícia ou evento macro + inferência de impacto nos ativos da carteira/watchlist. Independente.

**Teste de admissão:** ✅ passa. Substrato = feed de notícias + macro persistido (depende das Fatias 2-3). Método = correlação macro→setorial→ativo (distinto da fundamentalista e da técnica).

**Peças:**
- Ingestão de notícias via API, filtradas por ativos em carteira + watchlist.
- Matriz de sensibilidade macro → setor (configurável): quais indicadores macro afetam quais setores e em qual direção. Base inicial estática (tabela de referência); evolui com uso.
- Tool MCP `noticias_relevantes` — notícias recentes filtradas por ativo ou setor.
- Tool MCP `impacto_macro` — dado evento macro, retorna ativos da carteira potencialmente afetados e direção esperada.

**Decisões a tomar:**
- Mesmo framework de agente das Fatias 10-12.
- Matriz de sensibilidade macro→setor: estática (tabela editável) ou inferida pelo LLM a cada evento?
- Frequência de ingestão de notícias: intraday, diária, ou sob demanda?
- A inferência macro→micro é determinística (regra: Selic↓ → construção↑) ou probabilística (LLM avalia caso a caso)?
- Watchlist já existe como tabela (Fase 3.0a.4). Integrar direto ou expandir?
- Risco de overload: quantas notícias/dia passam pelo filtro? Limiar de relevância mínima.

---

## Fase 5 — Interface web (Camada 4, parte 1)

*Realiza: comunicação usuário ↔ app (§2), mostra duas lentes e divergências (§5).*
*Capacidades de IA usadas: gerar artefatos (cap. 7), Generative UI.*

**Pode iniciar em paralelo com a Fase 4** — a interface é o "como mostrar", as fases anteriores dão o "o quê mostrar."

### Fatia 14 — React + infra cloud

**Objetivo:** sair do teto do Streamlit. Frontend React com qualidade visual (paleta TradingView #0F1117, referência Investidor10).

**Peças:**
- Frontend React (Vercel).
- Backend FastAPI migra para Cloud Run.
- SQLite migra para PostgreSQL.
- Autenticação própria (substituir basic auth Caddy).
- Design tokens derivados da paleta fixada (02-estrutura).

**Decisões a tomar:**
- PostgreSQL desde já ou manter SQLite com migração posterior?
- Design system completo antes de codar, ou tokens mínimos + evolução?
- CopilotKit como framework de Generative UI (02-estrutura: possibilidade a avaliar, sem decisão). Se adotado, desacopla agente da interface — protege a decisão orquestra vs. maestro único.
- Autenticação: OAuth, magic link, ou mais simples?

**Generative UI já decidida:**
- Declarativo como base (agente emite esquema, app mapeia).
- Controlado nos poucos fluxos de precisão (patrimônio consolidado, tela de alocação).
- Aberto só para visualizações descartáveis.

### Fatia 15 — Generative UI

**Objetivo:** o maestro não só descreve — mostra. Observações, divergências, composição da carteira renderizadas pelo agente em tempo real.

**Peças:**
- Protocolo de comunicação agente → interface (AG-UI ou equivalente).
- Componentes controlados para fluxos de precisão.
- Componentes declarativos para observações do maestro.

**Decisões a tomar:**
- Framework: CopilotKit (open-source, AG-UI) ou implementação própria?
- Quais fluxos são controlados vs. declarativos? (Primeiros candidatos: patrimônio = controlado, observação do maestro = declarativo.)

---

## Fase 6 — Interface mobile + temperamento (Camada 4, parte 2 + Camada 3 completa)

*Realiza: temperamento (§4) — "fala no momento em que algo surge, desde que pertinente e fundamentado."*
*Depende de: Camada 2 completa (portão de pertinência) + Camada 3 (instrumentistas) + Camada 4 (push).*

### Fatia 16 — Mobile nativo + push

**Objetivo:** habilitar o temperamento. Push notification = pré-requisito do §4. Web responsivo ≠ mobile nativo — servem modos de uso distintos (02-estrutura).

**Decisões a tomar:**
- PWA (mais barato, menos controle sobre push) vs. nativo (React Native/Expo)?
- Quais eventos disparam push no MVP?
  - Candidatos objetivos (derivam da IPS): violação de banda, invalidação de tese, cash drag > 6 semanas.
  - Candidatos inferidos (derivam da Camada 2): divergência dito-vs-feito acima de limiar.

### Fatia 17 — Portão de pertinência + ensaio contínuo

**Objetivo:** "a orquestra nunca para." Jobs de fundo (cron): instrumentistas rodam, produzem observações, as observações passam pelo portão, as que passam são entregues via push ou na próxima sessão.

**Peças:**
- Portão com dois critérios (§4): **fundamentado** (Maker-vs-Checker: dados de tools, contas fecham) + **pertinente** (violação IPS = objetiva; padrões comportamentais = aprendida).
- Autonomia agendada (capacidade 5): cron pós-fechamento de mercado.
- Estado persistido entre execuções (padrão 2 do ensaio).
- Teste das 4 condições antes de automatizar cada observação nova.

**Decisões a tomar:**
- O default é falar ou o default é silêncio? (§4: o default é falar; o silêncio se justifica.)
- Frequência do ensaio: diário, pós-fechamento? Semanal para observações mais pesadas?
- Limiar de pertinência para observações inferidas (não-IPS): como calibrar sem overload?

---

## Fase 7 — Extensões

Após o conceito completo (Fases 1-6), extensões que enriquecem sem mudar a arquitetura.

### Fatia 18 — IRPF

DARF, isentômetro, declaração pronta. Depende de React + mobile.

### Fatia 19 — Agenda visual de proventos

Previsão de renda passiva baseada em histórico de dividendos/JCP.

### Fatia 20 — Comparador interno

Ativos lado a lado com fundamentos. Usa substrato do instrumentista fundamentalista.

### Fatia 21 — Rebalanceamento inteligente

Sugestão de trades para voltar às bandas da IPS. O maestro sugere; o usuário dá o enter (L3).

---

## Mapa completo — fatia × camada × conceito

| Fatia | Camada | §conceito | Status |
|---|---|---|---|
| 1 — Índices setoriais B3 | 1b | §2 janela | ✅ entregue |
| 2 — Fundamentos API | 1b | §2 janela | 🔜 próxima |
| 3 — Macro/eventos persistidos | 1b | §2 janela | ─ |
| 4 — Teses com invalidação | 2 decl. | §7.2 | ─ |
| 5 — Diário de decisão | 2 decl. | §7.3 | ─ |
| 6 — Risco ex-ante | 2 decl. | §7.4 | ─ |
| 7 — Aporte/caixa | 2 decl. | §7.6 | ─ |
| 8 — Inferência event log | 2 inf. | §3 dito-feito | ─ |
| 9 — Dito vs. feito | 2 inf. | §3 dito-feito | ─ |
| 10 — Fundamentalista | 3 | §6 orquestra | ─ |
| 11 — Setorial/macro | 3 | §6 orquestra | ─ |
| 12 — Técnico (gráficos) | 3 | §6 orquestra | ─ |
| 13 — Notícias/inteligência macro | 3 | §6 orquestra | ─ |
| 14 — React + infra | 4 | §2 interface | ─ |
| 15 — Generative UI | 4 | §2 interface | ─ |
| 16 — Mobile + push | 4 | §4 temperamento | ─ |
| 17 — Portão + ensaio | 3+4 | §4 temperamento | ─ |
| 18 — IRPF | ext. | — | ─ |
| 19 — Proventos | ext. | — | ─ |
| 20 — Comparador | ext. | — | ─ |
| 21 — Rebalanceamento | ext. | — | ─ |

**Disciplinas §7 já implementadas:** §7.1 IPS ✅, §7.5 Brinson ✅.

---

## Decisões abertas (cross-fase)

| # | Decisão | Onde impacta | Quando precisa estar fechada |
|---|---|---|---|
| D1 | Fonte API do substrato exógeno (Dados de Mercado vs. Partnr) | Fatias 2-3, 13 | Antes do brief da Fatia 2 |
| D2 | Arquitetura de agentes: orquestra plural vs. maestro com tools | Fatias 10-13 | Antes da Fase 4 |
| D3 | Framework de agentes: `ant` CLI / Anthropic nativo vs. terceiros | Fatias 10-13 | Junto com D2 |
| D4 | CopilotKit para Generative UI | Fatias 14-15 | Antes da Fase 5 |
| D5 | SQLite → PostgreSQL: quando migrar | Fatia 14 | Antes da Fase 5 |
| D6 | Mobile: PWA vs. nativo (React Native/Expo) | Fatia 16 | Antes da Fase 6 |
| D7 | Pertinência: configurada (IPS) + aprendida (como?) | Fatia 17 | Antes da Fase 6 |
| D8 | Rotação MCP_TOKEN | Higiene | Imediato |
| D9 | Matriz macro→setor: estática (tabela) ou inferida (LLM) | Fatia 13 | Antes do brief da Fatia 13 |
| D10 | Gráficos técnicos: estáticos (PNG) ou interativos (Plotly HTML) | Fatia 12 | Antes do brief da Fatia 12 |

---

## Protocolo de execução (02-estrutura, confirmado)

1. Conceito (01) vira constituição no repositório — Claude Code lê e nunca contraria.
2. Cada fatia ganha brief próprio no chat (barato) antes da sessão de código (cara).
3. Sessões curtas, uma fatia por sessão.
4. Local → teste sintético → commit → backup → produção.
5. Decisões de produto no chat, micro-decisões técnicas no Claude Code.

---

*Status: plano macro mapeado. Próxima ação: discutir as decisões da Fatia 2 e produzir o brief 06-brief-fatia-2.md.*
