# Reconciliação Crítica — Conceito/Estrutura da Sessão × Estado Real do Carteira Clean

*Leitura sem complacência. O objetivo não é celebrar convergências, é medir
honestamente a distância entre o que projetamos (docs 01–03) e o que existe
hoje no projeto — e nomear o que está faltando, não o que está pronto.*

---

## Veredito de abertura

O Carteira Clean é um **excelente sistema de mensuração de carteira** com um
**esboço de assistente acoplado**. O que os documentos 01–03 descrevem é uma
**outra categoria de produto**: um sistema cuja inteligência é o centro, não
um anexo. A sobreposição real entre os dois é menor do que parece à primeira
vista. O projeto resolveu com maestria **metade da Camada 1** — o substrato
endógeno (dados da carteira). A outra metade (substrato exógeno: contexto
persistido) e tudo da Camada 2 para cima são fundações e roadmap — não a coisa.

A armadilha a evitar: olhar o roadmap do projeto (que *menciona* memória,
proatividade, MCP, mobile) e confundir "está planejado / esboçado" com "está
a caminho de virar o conceito". Não está. O roadmap atual leva a um bom
assistente-sobre-dashboard. O conceito que fechamos é outra ambição. A ponte
entre os dois não está desenhada.

---

## Camada por camada — a distância real

### Camada 1 — Substrato — DISTÂNCIA: nula no endógeno, MÁXIMA no exógeno

Aqui é preciso desdobrar, porque tratar a Camada 1 como uma coisa só foi um
erro conceitual dos próprios documentos da sessão.

**1a — Substrato endógeno (dados da carteira): distância ~nula.** O projeto não
só atende, supera. Event sourcing com event log imutável e idempotência,
projeções puras, GIPS/Modified Dietz, TWR validado, multi-asset real, automação
de preços de 5 fontes. Esta metade é o ativo mais valioso do projeto e está
madura.

**1b — Substrato exógeno (contexto macro/micro/setorial): distância máxima.**
O contexto em que os dados da carteira existem **não é substrato no projeto** —
é lookup efêmero. As tools (Brapi para fundamentos, BCB para macro) buscam o
contexto no instante da pergunta e o descartam depois. Nada sedimenta. Isso
significa que os futuros instrumentistas seriam abastecidos com dado frio e
teriam de reconstruir o contexto do zero a cada convocação — o que os torna
**leitores, não especialistas**. Um fundamentalista de verdade carrega
entendimento acumulado do setor; o projeto não tem onde acumular isso. Esta
lacuna é tão estrutural quanto as das camadas superiores e não tinha sido
nomeada nem nos documentos da sessão nem na primeira reconciliação.

### Camada 2 — Memória dupla — DISTÂNCIA: grande

O que existe: a Fase 3.0a.4 prevê memória *estruturada* — tabelas de
preferências, watchlist, análises salvas, histórico de conversas. Isso é a
metade "declarada" da memória (o que o usuário conta/salva).

O que falta inteiro: a **inferência de comportamento**. Não há nada no projeto
que leia o event log — que já existe e é rico — para extrair padrões de
comportamento do investidor (giro real vs. declarado, viés de concentração,
ancoragem, repetição de erros, descolamento entre perfil dito e perfil
praticado). O conceito mais forte da sessão — *a divergência entre o dito e o
feito como material central* — tem **zero implementação e zero roadmap** no
projeto. E, ironicamente, o projeto já tem a matéria-prima perfeita para isso
(o event log) parada, usada só para calcular performance.

Reconciliação honesta: a Camada 2 do conceito não é uma evolução da memória
estruturada planejada. É um segundo eixo inteiro que ninguém começou.

### Camada 3 — Agente/maestro — DISTÂNCIA: grande, e mal-medida antes

Aqui minha primeira reconciliação foi leniente. Deixa eu ser exato.

O que existe HOJE rodando (Fase 3.0): **snapshot estático injetado no system
prompt, sem function calling, sem memória entre sessões, modelo respondendo
sobre um retrato textual da carteira.** O próprio projeto classifica isso como
"Dashboard com narrativa", não advisor. É a definição literal do "chat genérico
colado ao lado" que o conceito rejeita.

O que está PLANEJADO (Fase 3.0a.1–5): migração para MCP + tools, em 5 sub-fases,
começando por 8 tools de portfólio interno e progredindo até fundamentos e
memória. Isso é bom e é a direção certa — mas é **roadmap, não realidade**, e
mesmo quando completo entrega um **assistente único com tools**, não a orquestra.

A distância para o conceito tem três camadas, da menor para a maior:
1. *Snapshot → tools*: planejado, caminho claro. (menor)
2. *Assistente único → instrumentistas especializados independentes que reportam
   ao maestro*: *não existe no projeto em nenhuma forma*. O projeto pensa "um
   Claude com muitas tools". O conceito pensa "vários analistas independentes +
   um maestro que orquestra". São arquiteturas de agente diferentes. (média)
3. *Assistente reativo → temperamento que fala no momento em que algo surge,
   com portão de pertinência calibrado pela memória de inferência*: o projeto
   tem "sugestões proativas" como uma linha solta na Fase 3.0a.5, sem princípio,
   sem portão, sem a memória que tornaria a pertinência possível. O temperamento
   que definimos **depende da Camada 2 que não existe**. (maior)

Ou seja: o coração comportamental do conceito está represado atrás de uma
camada não construída. Não dá para ter o maestro com temperamento sem a memória
de inferência. O projeto não enxergou essa dependência.

### Camada 4 — Interface — DISTÂNCIA: máxima, e é dívida estrutural

O projeto é **Streamlit**. Os documentos da sessão decidiram **web responsivo +
mobile nativo + Generative UI (Declarativo/Controlado)**. Não há ponte entre os
dois — há substituição.

Pontos duros que a primeira reconciliação minimizou:
- Streamlit tem teto de design reconhecido pelo próprio histórico e **não vira
  mobile nativo**. O temperamento "falar no momento em que surge" exige push
  notification, que exige mobile nativo. Logo: **o temperamento do conceito é
  inalcançável na stack de interface atual.** A Camada 4 não é cosmética — ela
  bloqueia a Camada 3.
- Generative UI não tem absolutamente nada no projeto. É conceito novo inteiro.
- A migração Streamlit → web stack (FastAPI/React) foi *cogitada* como "F4" num
  roadmap antigo, sem decisão nem início.

Esta é a maior dívida estrutural entre conceito e realidade, e tem efeito
dominó sobre a Camada 3.

---

## Os três erros da minha primeira reconciliação (corrigidos)

1. **Chamei de "🟡 parcial" o que é "🔴 fundação apenas".** Memória e agente não
   estão "meio prontos" — têm fundações e o resto é projeto não construído.
2. **Tratei roadmap como progresso.** Mencionar MCP, proatividade e mobile não
   aproxima do conceito; são intenções sem a arquitetura que o conceito exige.
3. **Não vi a dependência Camada 2 → Camada 3 → Camada 4.** O temperamento
   (C3) precisa da memória de inferência (C2) e de push/mobile (C4). As três
   lacunas não são independentes; são uma cadeia. Atacar uma sem as outras não
   entrega o conceito.

---

## O que isto significa para o caminho

A sequência que fechamos na estrutura (consolidação → memória → IA → UI) está
**certa na ordem, mas subdimensionada na escala** do que cada etapa exige:

- **Consolidação**: feita. De verdade.
- **Memória**: o projeto fará a metade fácil (estruturada). A metade que importa
  (inferência sobre o event log) não está sequer especificada. É aqui que o
  conceito vira realidade ou morre.
- **IA**: o caminho snapshot→MCP→tools resolve o "investigar", mas não entrega
  orquestra nem temperamento. Decidir conscientemente: a orquestra plural vale a
  complexidade, ou "instrumentistas = grupos de tools de um maestro único" é
  suficiente para realizar o conceito? (Esta é uma decisão de design ainda não
  tomada — e legítima nas duas direções.)
- **UI**: a decisão Streamlit × (web responsivo + mobile nativo + Gen UI) é a
  mais cara e a mais evitada. Sem ela, o temperamento não existe. Não dá para
  adiar indefinidamente sem amputar o conceito.

## Dependências (o que trava o quê)

```
Camada 1a endógena (pronta)
Camada 1b exógena — contexto persistido  [NÃO INICIADA: só lookup efêmero]
   └── habilita → instrumentistas que são especialistas, não leitores
Camada 2 inferência sobre comportamento  [NÃO INICIADA]
   └── (1b + 2 = o que o sistema "APRENDE": mundo + usuário)
         └── habilita → portão de pertinência
                           └── habilita → temperamento (C3)
                                             └── exige → mobile/push (C4) [NÃO INICIADO]
```

O assistente atual não aprende — não tem nem contexto persistido (1b) nem
inferência de comportamento (2). Lê e esquece. Por isso pode virar bom músico,
nunca maestro. As duas metades do "aprender" são pré-requisito de tudo que está
acima delas na cadeia.

## Recomendação crítica de prioridade

1. **Substrato exógeno + memória de inferência** — as duas metades do
   "aprender". O contexto persistido (1b) torna os instrumentistas especialistas
   de verdade; a inferência (2) cruza com ele para gerar o espelho. Ambas usam
   ativos já existentes mas não explorados (tools de contexto que hoje evaporam;
   event log hoje só usado para performance). São pré-requisito do temperamento.
2. **Decisão de interface** — não construir ainda, mas *decidir*, porque ela
   trava o temperamento e tem efeito dominó. Adiar a decisão é adiar o conceito.
3. **Decisão de arquitetura de agentes** — orquestra plural vs. maestro único
   com tools. Define a escala de tudo que vem na Camada 3.

Nenhuma das três é "continuar o roadmap atual". As três são reconhecer que o
roadmap atual leva a um bom assistente — e que o conceito pede mais.

---

*Status: reconciliação crítica. A distância entre conceito e realidade é real,
está nas Camadas 2–4, e forma uma cadeia de dependências, não três lacunas
soltas.*
