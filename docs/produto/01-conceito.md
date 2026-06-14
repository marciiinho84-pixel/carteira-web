# App Inteligente de Gestão de Investimentos — CONCEITO

*O que o app é e por quê. Camada estável: muda pouco com o tempo.*
*A estrutura técnica deriva deste documento e vive em arquivo separado.*

---

## 1. A dor de origem

Ferramentas fragmentadas. Investidor 10 não cobre fundos nem previdência;
TradingView é essencialmente renda variável; nenhum tem IA generativa dentro
da carteira. Falta um lugar onde caiba **tudo** e onde se possa, ao mesmo
tempo, ver o todo e tratar cada tipo de investimento por sua própria estratégia.

## 2. A tese central — duas lentes acopladas

O app é, simultaneamente:

- **Janela para fora** — consolida tudo e contextualiza com o mundo.
- **Espelho para dentro** — devolve verdades sobre a própria carteira e os
  próprios padrões de decisão.

Afirmação de design forte: **as duas lentes só têm valor acopladas.** O
movimento característico não é informar nem analisar — é **traduzir**: cada
evento do mundo chega refratado pela lente de quem o usuário é; cada padrão
interno é checado contra o que o mundo faz.

## 3. Como o app conhece o usuário — falar E inferir

Duas fontes que convivem e podem divergir:

- O que o usuário **conta** (teses, objetivos por balde, apetite a risco).
- O que o app **infere** do comportamento (giro, concentração, padrões).

A **divergência entre o dito e o feito** é o material mais valioso. Consolidador
só vê comportamento; chat genérico só ouve a fala. O app, por acoplar as duas
lentes, põe as duas em confronto.

## 4. O temperamento do app

Fala **no momento em que algo surge, desde que pertinente e fundamentado.**
Urgência de mercado com disciplina de evidência. O default é falar; o silêncio
é que precisa se justificar.

- **Fundamentado**: há dados que sustentam, ou não há.
- **Pertinente**: depende de conhecer o usuário — é relação, não propriedade da
  observação.

## 5. Princípios de comportamento (a "alma")

- **A decisão é sempre do usuário.** O app afia o raciocínio; não prescreve.
- **Agentes reportam fatos; não provocam nem evitam divergência.** Convergência
  e divergência são igualmente legítimas. Neutralidade quanto ao resultado,
  fidelidade ao fato.
- **Instrumentistas são independentes.** Cada um reporta ao maestro sem ouvir os
  outros — a independência protege a fidelidade de cada leitura (um não
  contamina o outro).
- **Apresenta, não filtra.** A curadoria de relevância é do usuário.
- **Sem agenda própria.** Nenhuma camada tem viés sobre o que o usuário deveria
  concluir.

## 6. Metáfora estruturante — a orquestra

- **Usuário** = compositor + regente: escreve a tese e dá o enter na execução.
- **Agentes especializados** = instrumentistas: cada um (fundamentalista,
  técnico, setorial) reporta fielmente o que seu instrumento mostra.
- **IA orquestradora** = maestro: organiza e traz os insights ao usuário; é a
  camada com quem ele conversa.

Caráter do sistema:

- **A orquestra nunca para** — ensaio contínuo (trabalho de fundo) para o show
  diário (o pregão).
- **Mais jazz que concerto** — teses mudam; mudanças de estratégia são
  comunicadas, discutidas e estressadas com o maestro. Improviso disciplinado
  dentro da tese do usuário.

## 7. Disciplinas de gestão (o processo do gestor)

Nenhuma é feature de IA — são compromissos escritos que transformam a IA de
comentarista em **auditora**: o maestro cobra coerência com o que o usuário
assinou. Resposta definitiva à fronteira regulatória: o app nunca recomenda,
cobra coerência com a política do próprio usuário.

1. **IPS (Política de Investimento escrita)** — alocação-alvo por balde, bandas,
   regras de rebalanceamento, limites de concentração. Torna "pertinente"
   objetivo: pertinente = o que viola ou ameaça a política.
2. **Teses com critérios de invalidação pré-registrados** — toda posição nasce
   com "o que me provaria errado". Instrumentistas vigiam condições de
   invalidação, não notícias soltas. Elimina mover a trave.
3. **Diário de decisão** — no momento do enter: racional, cenário esperado,
   convicção. É o lado "dito" do dito-vs-feito (§3); habilita post-mortem de
   processo, não de resultado.
4. **Risco ex-ante** — exposição efetiva por fator (diversificação real entre
   baldes), orçamento de drawdown, escala de liquidez, cenários de stress
   permanentes sobre a carteira viva.
5. **Atribuição de performance (Brinson)** — retorno vem de alocação ou de
   seleção? Verdade que o espelho deve contar cedo.
6. **Disciplina de aporte e caixa** — regra escrita para aportes (programado vs.
   oportunístico com critério) e monitoramento de cash drag.

## 8. Decisões de conceito em aberto

- **Pertinência: configurada ou aprendida** — parcialmente resolvida pela IPS
  (§7.1): violações de política são pertinência objetiva; o refinamento fino
  segue aprendido com feedback.
- **Fronteira regulatória** — mitigada pelo §7 (cobrar coerência ≠ recomendar);
  permanece relevante se o app servir a terceiros.

---

*Status: conceito macro consolidado.*
