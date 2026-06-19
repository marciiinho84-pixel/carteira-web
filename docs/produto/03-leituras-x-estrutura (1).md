# Leituras × Estrutura — Compilado

*As quatro leituras trazidas e como cada uma conversa com as três camadas
propostas. Ótica macro. As camadas são hipótese de trabalho, não dogma.*

---

## As três camadas (lembrete)

1. **Substrato** — base de dados unificada (tudo num lugar, baldes + todo).
2. **Memória dupla** — o que o usuário conta + o que o app infere.
3. **Agente / maestro** — o interlocutor que traduz e convoca especialistas.

---

## Leitura 1 — Pipeline NotebookLM (Claude Code + Skill Creator + NotebookLM + Obsidian)

*Pesquisa como pipeline sob comando; offload de processamento; memória em
markdown; melhora com o uso.*

| Camada | Como conversa |
|--------|---------------|
| Substrato | Pouco direto. Obsidian como vault inspira a ideia de base local persistente, mas o app precisa de dados estruturados (preços, posições), não notas soltas. |
| Memória | **Forte.** O `claude.md` = configuração de preferências; o efeito composto (vault que enriquece) = a memória que melhora com uso. |
| Agente | **Médio.** O conceito de "skill" = capacidade modular que o agente invoca sob comando. |
| Externo | **NotebookLM** = digestão/offload de conteúdo pesado (calls, RI). Já incorporado ao conceito. |

**O que extrair:** o padrão de offload (mandar trabalho pesado para fora do
núcleo) e a ideia de capacidades modulares (skills) que o maestro aciona.

---

## Leitura 2 — Obsidian + Hermes Agent (agente autônomo)

*Agente que roda sozinho, agendado; lê uma base de conhecimento, raciocina,
escreve de volta; efeito composto em 90 dias.*

| Camada | Como conversa |
|--------|---------------|
| Substrato | **Médio.** A estrutura de pastas do vault inspira a organização da base, mas de novo: notas ≠ dados de mercado. |
| Memória | **Forte.** A base que o agente lê e escreve = a memória dupla. O efeito composto é exatamente o que se quer. |
| Agente | **Muito forte.** As 7 skills (briefing, síntese, monitor de saúde) = o ensaio contínuo da orquestra. A autonomia agendada = "a orquestra nunca para". |
| Externo | Filesystem MCP = como o agente acessa a base. Padrão de conexão. |

**O que extrair:** o modelo de autonomia agendada (trabalho de fundo que produz
sem o usuário pedir) e a ideia do agente que lê E escreve na memória.
**Ressalva:** complexidade alta; depende de framework de terceiros.

---

## Leitura 3 — `ant` CLI / Agentes gerenciados Anthropic

*API do Claude via terminal; agentes, sessões e ambientes como recursos
versionáveis; infraestrutura-como-código aplicada à IA.*

| Camada | Como conversa |
|--------|---------------|
| Substrato | Baixo. Não trata de dados de carteira. |
| Memória | **Médio.** Sessões guardam estado da conversa do lado da plataforma — um tipo de memória diferente do "tudo em markdown". |
| Agente | **Muito forte.** O modelo de *agente definido como configuração versionável* é exatamente a "constituição legível" da Camada 3. Agentes especializados = os instrumentistas. |
| Externo | Mostra a infra nativa (sem andaimes de terceiros) para rodar agentes. |

**O que extrair:** a forma nativa e versionável de definir agentes — quem é,
como se comporta, que ferramentas usa. É o candidato mais sólido para
implementar o maestro e os instrumentistas sem depender de frameworks externos.

---

## Leitura 4 — Generative UI (três padrões: Controlado / Declarativo / Aberto)

*Interface desenhada pelo agente em tempo real; espectro controle ↔
flexibilidade; protocolos MCP/A2A/AG-UI.*

| Camada | Como conversa |
|--------|---------------|
| Substrato | Baixo direto, mas a UI precisa ler a base para mostrar a carteira. |
| Memória | Baixo. |
| Agente | **Médio.** Como o maestro *mostra* (não só descreve) os insights e a divergência dos agentes. |
| Externo | **Forte — camada nova.** É a face do app: como tudo aparece na tela. Preenche a lacuna "interface". |

**O que extrair:** a interface é uma quarta preocupação que as três camadas não
cobriam. Candidata a virar uma camada própria na estrutura. A2A (agentes
conversando entre si) é diretamente relevante para o maestro coordenar os
instrumentistas.

---

## Síntese — o que as leituras sugerem para a estrutura macro

1. **Memória** é o tema mais reforçado (3 das 4 leituras). Confirma que é o
   coração diferenciador — e o mais difícil.
2. **O agente versionável** (leitura 3) é o caminho técnico mais limpo para
   maestro + instrumentistas, sem frameworks de terceiros.
3. **Autonomia agendada** (leitura 2) realiza "a orquestra nunca para".
4. **Offload de digestão** (leitura 1 / NotebookLM) tira peso do núcleo.
5. **Interface (leitura 4)** não cabe nas três camadas — provavelmente é uma
   **quarta camada** a acrescentar ao desenho.

## Pergunta macro que isso abre

As três camadas podem virar quatro (substrato → memória → agente → **interface**).
Antes de detalhar qualquer uma, vale decidir: a estrutura macro tem 3 ou 4
camadas? E a coordenação entre agentes (A2A) é parte da camada do agente ou
merece destaque próprio?

---

*Status: leituras mapeadas. Próximo: fechar o nº de camadas da estrutura macro.*
