# Polimento — Sala de Comando (usabilidade)

*Para sessão de Claude Code. Escopo fechado. Não expandir além do definido aqui.*
*Lê e respeita a constituição (01-conceito.md) e este brief. Em conflito, o conceito vence.*
*Origem: diagnóstico do Márcio em sessão de chat — "não uso muito" a Sala de Comando porque ela não é proativa.*

---

## Diagnóstico (por que esta fatia existe)

A Sala de Comando foi criada (`9c9269e`, Fatia 15) para ser a home do app — `/` e `/dashboard` redirecionam para ela. Na intenção original, ela deveria funcionar como um advisor: o maestro apontando fatos que o usuário ainda não viu. Na implementação real, a seção "Orquestra" (`sala_de_comando.py::_build_observacoes`) apenas reexibe as últimas 6 mensagens do assistente na conversa do Maestro — um replay do passado, não uma varredura de fatos novos. É por isso que a página não é usada no dia a dia: ela não avisa nada que o usuário não tenha visto sozinho.

Isto conecta diretamente com a lacuna já nomeada em `04-reconciliacao.md` e `08-relatorio-execucao-critica.md`: falta o "portão de pertinência" (Fase 6, Fatia 19) — o sistema tem os sinais (alertas, notícias, macro, técnico, fundamentalista) mas nada os filtra e apresenta como fatos novos e relevantes.

## Objetivo da fatia

Substituir a lógica da seção "Orquestra" por um **feed de fatos novos e relevantes que o usuário ainda não viu**, no lugar do replay de chat. Cada item do feed deve ser: (a) **fundamentado** — vem de uma tool/tabela real, nunca texto livre do modelo; (b) **pertinente** — afeta uma posição atual, uma tese ativa, ou um bloco fora da banda IPS; (c) **novo** — o usuário ainda não marcou como visto.

**Decisão do Márcio (2026-07-11): escopo cheio de uma vez, sem faseamento.** As 7 categorias de sinal entram juntas, e a varredura roda num **cron antes da abertura do mercado B3** — não sob demanda. Quando o app é aberto de manhã, o feed já está pronto; não há espera pelo maestro trabalhar. A antiga proposta de entrega em fases (MVP → notícias/macro → técnico/fundamentalista → cron) foi descartada em favor de entregar tudo de uma vez.

## Categorias de sinal (o que pode entrar no feed)

| Categoria | Fonte já existente | O que dispara a entrada no feed |
|---|---|---|
| Alerta disparado | tabela `alertas` + tool `verificar_alertas` | `disparado_em` preenchido e ainda não visto |
| Tese invalidada | tabela `teses` (status) | tese muda de ATIVA → INVALIDADA |
| Desvio de banda IPS | `_calc_blocos_ips` (já roda na Sala de Comando) | bloco em status ABAIXO/ACIMA que não estava assim na última visita |
| Gatilho técnico | `analise_tecnica` (votação -1/0/+1) | ativo em posição muda de rating para -1 ou +1 (venda/compra) desde a última varredura |
| Gatilho fundamentalista | `screening_fundamentalista` / `comparar_multiplos` | métrica cruza limiar relevante (ex: entra/sai de faixa de valuation) |
| Notícia relevante | `noticias_ativos` / `pesquisar_web` | notícia nova (por data de publicação) sobre ativo em posição |
| Fato macro relevante | `impacto_macro` / `regime_mercado` | evento macro com impacto mapeado para um setor com posição (via matriz_sensibilidade) |

As 3 primeiras linhas usam dado que a Sala de Comando **já calcula ou já tem em tabela** — são o caminho de menor esforço. As 4 últimas exigem rodar tools que hoje só respondem sob pergunta explícita no chat.

## As peças

**Peça A — Estado "visto/não visto".**
Sem isso, nada do resto funciona (o feed reapareceria infinitamente). Precisa de uma tabela nova, por exemplo `observacoes_feed` (id, categoria, ativo, referencia_id, conteudo, fundamentos_json, criado_em, visualizado_em). `referencia_id` aponta pra origem real (id do alerta, id da tese, etc.) — nunca um texto solto.

**Peça B — Motor de varredura e regra de pertinência.**
Uma função (não um agente novo — vive no backend, sob o maestro, mantendo D2) que roda as categorias escolhidas na Peça C e grava em `observacoes_feed` só o que for fundamentado + pertinente + novo (compara com o que já está gravado, evita duplicata).

**Peça C — Escopo de categorias.**
Fechado: as 7 categorias da tabela acima entram todas nesta entrega. Para técnico e fundamentalista, a varredura precisa guardar o "estado anterior" por ativo (rating de ontem vs. hoje) para detectar mudança — não basta olhar o valor do dia. O cron diário (Peça D) resolve isso de forma natural: cada rodada compara com a rodada anterior, sem ambiguidade de "desde quando".

**Peça D — Quando a varredura roda.**
Fechado: **cron na VM, antes da abertura do mercado B3** (pregão abre 10h BRT / 13h UTC — sugestão de horário: 12:30 UTC / 09:30 BRT, com folga; ajustar se notícias/macro ainda não tiverem atualizado a essa hora). Mesmo padrão dos outros crons documentados em `claude.md`. Fecha de vez a lacuna do "ensaio contínuo" do conceito (§6) — a orquestra toca antes de o usuário abrir o app, não quando ele pede.

Nota de custo: rodar as 7 categorias para ~38 ativos uma vez por dia (cron) é ordens de magnitude mais barato do que rodar sob demanda a cada carregamento de página — outro motivo a favor da decisão de ir direto para cron.

**Peça E — Frontend.**
Nova versão da seção "Orquestra" na Sala de Comando: cada item com badge de categoria (cores já definidas na paleta Papel & Tinta: alerta = `--warning`/`--negative` conforme severidade, notícia = `--purple-accent`, técnico/fundamentalista = `--accent`), texto do fato, badge "novo" até ser visto, botão de dispensar (marca `visualizado_em`). Manter as outras 4 seções da página como estão (KPIs, semáforos de teses, espelho comportamental, progress-to-goal) — não fazem parte deste polimento.

**Regra transversal (ver `claude.md` §8):** todo ticker/nome de ativo citado num item do feed deve ser link clicável para `/ativos/[ticker]`.

## Critérios de aceite (verificáveis)

1. A seção Orquestra nunca mais mostra texto de mensagens de chat antigas.
2. Todo item do feed é rastreável a uma linha real de `alertas`, `teses`, `_calc_blocos_ips`, `analise_tecnica`, screening, notícia ou evento macro — nenhum texto gerado livre pelo modelo sem origem (regra anti-alucinação, igual à Fatia 1).
3. Marcar um item como visto o remove do feed permanentemente (não reaparece nas próximas visitas).
4. As 7 categorias funcionam de ponta a ponta com dado real de produção — não só as 3 mais fáceis.
5. O cron pré-abertura de mercado roda sozinho na VM, sem intervenção manual, e o feed já está populado quando o usuário abre o app de manhã.
6. Todo ticker de ativo citado num item do feed é link clicável para `/ativos/[ticker]`.
7. 44 testes de regressão existentes continuam passando.

## O que NÃO fazer nesta fatia

- NÃO implementar relevância aprendida por feedback do usuário (decisão D7 continua aberta — usar regra determinística explícita, dos critérios acima).
- NÃO criar um instrumentista/agente separado para isto — é uma função do backend do maestro (mantém D2: tools sob maestro único). Ver `claude.md` §8 para o racional completo dessa decisão.
- NÃO mexer nas outras 8 páginas do polimento visual em andamento, nem nas 3 excluídas (login, configurações, novo-evento).
- NÃO alterar as demais 4 seções da Sala de Comando (KPIs, teses, comportamental, meta) — já funcionam e não fazem parte do diagnóstico.
- NÃO fabricar notícia/fato macro/gatilho técnico quando a tool correspondente não retornar nada — a ausência de sinal é um resultado válido, não motivo para inventar.
- NÃO mexer em gráficos — adiado, ver `claude.md` §8.

## Fluxo de trabalho (já estabelecido)

Brief no chat (este documento) → sessão de Claude Code → local primeiro → testar com dados sintéticos → commit/push → migração Alembic para `observacoes_feed` → validar em produção.

---

*Status: brief pronto para decisão de fase e execução. Nenhum código escrito ainda.*
