# App Inteligente de Gestão de Investimentos — ESTRUTURA

*Como construir. Deriva do CONCEITO. Camada mutável: muda com a tecnologia.*
*Cada decisão aqui aponta para o princípio de conceito que a justifica.*

---

## Princípio de ordenação

A estrutura serve ao conceito, nunca o contrário. Cada escolha técnica abaixo
existe para realizar um item do documento de conceito.

## Propriedade transversal — APRENDER

Antes das camadas, um princípio que atravessa várias delas e que o assistente
atual **não tem**: o sistema aprende. Aprende sobre **o mundo** (contexto que
sedimenta ao longo do tempo) e sobre **o usuário** (comportamento inferido do
event log). Um agente que lê e esquece a cada turno nunca passa de leitor de
planilha. Aprender = conhecimento persistido e acumulado que dá sentido ao dado
frio. Esta propriedade vive na Camada 1-exógena e na Camada 2 — não é detalhe
da Camada 3.

## As camadas

**Camada 1 — Substrato. Tem duas metades de natureza distinta.**

*1a — Substrato endógeno (dados da carteira).*
*Realiza: a dor de origem (§1) e as duas lentes (§2).*
Tudo entra (ações, fundos, previdência, renda fixa). Cada ativo pertence a um
"balde" mas soma no todo. Dado frio e interno: o que o usuário tem e como se
comportou. **No projeto atual: maduro (event sourcing).**

*1b — Substrato exógeno (contexto do mundo).*
*Realiza: "janela para fora" (§2); torna instrumentistas especialistas.*
Contexto macro, setorial e micro **persistido e acumulado** — não lookup que
evapora. **No projeto atual: inexistente como substrato** (tools Brapi/BCB são
consulta efêmera). Alimentado por digestão contínua (NotebookLM) e dados
sedimentados. Regra: dado frio sem contexto produz leitores, não especialistas.

**Camada 2 — Memória dupla (conhecimento sobre o usuário).**
*Realiza: conhecer o usuário (§3), portão de pertinência (§4), disciplinas (§7).*
O **declarado** (IPS, teses com invalidação, diário de decisão — §7) + o
**inferido** do event log (giro real, concentração, padrões). Mesma natureza da
1b: conhecimento persistido — 1b olha para fora, a 2 para dentro; o insight
nasce do cruzamento.

**Camada 3 — Agente / maestro.**
*Realiza: temperamento (§4), princípios de comportamento (§5), metáfora (§6).*
Interlocutor configurado como uma "constituição" legível: personalidade,
portões de pertinência e fundamentação, regra de afiar em vez de prescrever.
Traduz entre as duas lentes e convoca os instrumentistas especializados.
A coordenação entre maestro e instrumentistas (A2A) vive **dentro** desta
camada — é fiação interna, não andar separado. **Instrumentistas são
independentes:** cada um reporta ao maestro sem ouvir os outros.

**Camada 4 — Interface (comunicação usuário ↔ app).**
*Realiza: o ato de comunicação entre usuário e app; mostra as duas lentes (§2)
e os insights/divergências dos instrumentistas (§5).*
É a face do app. Onde a carteira, os baldes, o todo e as observações do maestro
aparecem. Candidata a usar Generative UI (ver seção própria).

**Ordem de dependência:** substrato endógeno (1a) + substrato exógeno (1b) →
memória (2) → agente (3) → interface (4). As duas metades do substrato e a
memória são o que o sistema "aprende"; sem elas o agente é leitor, não maestro.
Construir nessa ordem evita o "chat genérico colado ao lado".

## Capacidades de IA disponíveis (o "universo")

1. **Conversar/raciocinar** — o interlocutor. A alma.
2. **Memória persistente** — a IA que conhece o usuário no tempo.
3. **Ferramentas e dados ao vivo** — conecta o raciocínio aos números reais.
4. **Executar código** — computa de verdade (backtests, risco, simulações).
5. **Autonomia agendada** — o ensaio contínuo; alertas que chegam sem pedir.
6. **Processar documentos** — releases, calls, transcrições, gráficos.
7. **Gerar artefatos** — relatórios, dashboards, gráficos.

Nota: raciocínio e documentos servem mais ao fundamentalista/setorial; análise
técnica é majoritariamente cálculo (capacidade 4).

## Disciplinas de gestão (§7 do conceito) — implementação

Custo baixo, valor alto: formulários + tabelas SQLite (via Alembic, mesmo
padrão da tabela `cotacoes`). IPS, teses e diário são dados **declarados** da
Camada 2; risco ex-ante e atribuição Brinson usam a capacidade de cálculo
sobre o event log já existente. O maestro lê a IPS como referência objetiva do
portão de pertinência.

## Engenharia do ensaio (loops do trabalho de fundo)

Três padrões para o "a orquestra nunca para":

- **Maker vs. Checker:** validador determinístico no portão "fundamentado" do
  maestro — confere que métricas vieram de tools e que contas fecham, antes de
  qualquer observação chegar ao usuário. Vive no maestro, **nunca entre
  instrumentistas** (preserva independência).
- **Estado persistido entre execuções:** cada job do ensaio registra o que fez
  e aprendeu; sem isso, o loop "lê e esquece" na camada operacional.
- **Teste das 4 condições antes de automatizar:** repetição real ≥ semanal,
  verificação automatizável, custo de tokens justificado, acesso a
  dados/ferramentas. Filtro de disciplina + regra de custo (modelo barato para
  volume/digestão, modelo forte para síntese do maestro).

## Fontes consultadas → diretriz extraída

| Fonte | O que nos deu | Onde aplica |
|---|---|---|
| Kubera (mycapitally.com/blog/best-portfolio-tracker-for-the-modern-diy-investor) | Expõe portfólio a IAs via MCP — direção da indústria; mas é balanço sem ledger | Valida nosso MCP; reforça valor do event sourcing (1a) |
| Snowball / Sharesight / Empower (benchmark 2026) | Consolidação está saturada; ninguém tem espelho comportamental | Diferencial = Camadas 1b + 2, não consolidação |
| TradingAgents (arxiv.org/abs/2412.20138) | Firma simulada: analistas especializados por papel | Valida instrumentistas (Camada 3) |
| FinCon / FinMem (survey arxiv.org/pdf/2503.21422) | Hierarquia gestor-analista; memória em camadas (curto/médio/longo prazo com recência+relevância) | Maestro; especificação pronta para 1b/2 |
| Posts Gen UI / CopilotKit (github.com/CopilotKit/CopilotKit) | 3 padrões de UI generativa; protocolo AG-UI desacopla agente↔interface | Camada 4 |
| NotebookLM (aulas Software 3.0) | Maker-vs-Checker, estado persistido, teste das 4 condições | Engenharia do ensaio |
| Literatura gestão (GIPS, Brinson, IPS) | Disciplinas de processo do gestor profissional | §7 do conceito |

## Protocolo de execução por IA (Claude Code)

Estes documentos alinham visão — **não são prompts de implementação**. Para
executar com mínima interferência:

1. **01-conceito vira a "constituição"** no repositório (CLAUDE.md ou
   referenciado por ele): o Claude Code lê em toda sessão e nunca contraria.
2. **Cada fatia vertical ganha um brief próprio**, produzido em sessão de
   chat (barata) antes da sessão de código (cara): escopo fechado, critérios
   de aceite verificáveis, lista explícita do que NÃO fazer.
3. **Sessões curtas e específicas** > sessão longa e aberta. Uma fatia por
   sessão.
4. **Fluxo já estabelecido permanece:** local primeiro → teste com dados
   sintéticos → commit/push → backup on-demand → migrar produção.

## Fronteira de autoridade (micro-decisões)

Decisões visíveis ao usuário ou que tocam a constituição (nº de instrumentistas,
o que cada um faz, comportamento do maestro, aparência) são fechadas **aqui no
chat**, brief a brief — nunca pelo Claude Code. Ele decide apenas *como codar*
(organização interna, nomes, detalhes técnicos).

**Instrumentistas:** começar com 1 na primeira fatia; orquestra cresce por
necessidade. Teste de admissão de novo agente: só nasce se tem **substrato e
método próprios** (ex.: fundamentalista lê demonstrativos, técnico lê séries de
preço). Se não passa, é tool de um agente existente.

**Aparência:** paleta e referência já fixadas (`#0F1117`, verde/vermelho estilo
TradingView, referência Investidor10/TradingView, React na Fase 4). Demais
detalhes visuais entram via design tokens no brief da fatia da Camada 4.

## Componentes externos mapeados

**NotebookLM — camada de digestão / offload.**
Digere conteúdo primário pesado (calls de resultado, RI no YouTube, entrevistas)
no compute do Google, sem onerar o núcleo. Alimenta memória e agente. A digestão
é insumo; a tradução pela lente da tese é o produto.

**Partnr (partnr.ai) — candidata a fonte da Camada 1b (a avaliar).**
API de dados do mercado brasileiro num só lugar: fundamentos CVM (150+
indicadores), cotações, dividendos, notícias com score de relevância, macro —
e expõe servidor MCP (mesmo protocolo do app). Candidata a fonte unificada do
substrato exógeno: fundamentos (instrumentista fundamentalista) + notícias
(matéria-prima do portão) + macro. **Ressalvas:** material é marketing; "score
de relevância / análise de impacto" prometido ≠ pertinência para o usuário
(score de terceiro não substitui a Camada 2); preço, limites, cobertura real e
estabilidade não verificados; adotar como fonte central cria ponto único de
falha e custo recorrente. Avaliar em paralelo, sem travar a primeira fatia.

## Camada de interface — Generative UI

Interface desenhada em parte pelo agente, em tempo real. Três padrões:

- **Controlado** — componentes prontos; o agente escolhe. Controle alto, custo
  cresce com o nº de componentes.
- **Declarativo** — o agente emite esquema; o app mapeia. Escala bem; layout
  varia entre execuções.
- **Aberto** — o agente desenha livre em sandbox. Flexível, marca inconsistente;
  só para uso descartável.

**Decidido:** Declarativo como base; Controlado nos poucos fluxos que exigem
precisão (patrimônio consolidado, tela de alocação onde o usuário dá o enter);
Aberto só para visualizações descartáveis, nunca como interface principal.

**Multiplataforma:** web responsivo + app mobile nativo.
- *Web responsivo* — ambiente de análise densa (telas grandes: estudar a
  carteira, conversar com o maestro).
- *Mobile nativo* — realiza o temperamento "falar no momento em que algo surge"
  via notificação push de verdade (melhor em nativo que em web).
Cada plataforma serve a um modo de uso distinto, não é redundância.

**Possibilidade a avaliar (Camada 4): CopilotKit** — framework open-source
sobre AG-UI: streaming, estado sincronizado agente↔UI, threads persistentes,
reconexão. Implementa os três padrões de Gen UI e **desacopla agente da
interface** (protege a decisão orquestra vs. maestro único). Ressalva: persistir
histórico ≠ aprender; a inferência (Camada 2) continua trabalho próprio. *Sem
decisão.*

## Decisões de estrutura em aberto

- **Caminho de construção detalhado** — o que entra em cada etapa abaixo, à
  medida que se aterrissa em dados, orçamento e quem constrói.

## Decisões de estrutura já fechadas

- **Cinco blocos estruturais:** substrato endógeno (1a) + substrato exógeno
  (1b) → memória dupla (2) → agente/maestro (3) → interface (4). "Quatro
  camadas" com a Camada 1 desdobrada em duas metades de natureza distinta.
- **Aprender é propriedade transversal** — vive em 1b e 2 (contexto do mundo +
  comportamento do usuário, ambos persistidos), não é detalhe do agente.
- **A2A dentro da Camada 3** — coordenação é fiação interna, não camada própria.
- **Instrumentistas independentes** — reportam ao maestro, não se ouvem.
- **Generative UI:** Declarativo como base; Controlado nos poucos fluxos de
  precisão (ex.: patrimônio consolidado, tela de alocação); Aberto só para
  visualizações descartáveis, nunca como principal.
- **Exibir convergência/divergência:** o maestro sintetiza primeiro, com
  expansão para cada instrumentista. O sinal de convergência/divergência é
  visível sem precisar abrir nada; o raciocínio completo fica a um clique.
- **Multiplataforma:** web responsivo (análise densa) + app mobile nativo
  (notificação push, realiza o temperamento do §4).
- **Caminho de construção (sequência macro):**
  1. **Consolidação** — já existe (MVP funcional atual).
  2. **Memória dupla** — integrar ao app atual.
  3. **IA** — maestro + primeiro instrumentista, depois os demais e a autonomia.
  4. **Interface (UI)** — Generative UI conforme decidido.
  Cada etapa é usável antes da seguinte. Ponto de partida real: integrar
  memória ao MVP existente, não construir a base do zero.

---

*Status: estrutura macro mapeada, derivada do conceito.*
