# Brief de Implementação — Fatia Vertical 1

*Para sessão de Claude Code. Escopo fechado. Não expandir além do definido aqui.*
*Lê e respeita a constituição (01-conceito.md). Em conflito, o conceito vence.*

---

## Objetivo da fatia

Provar o **loop completo do conceito em escala mínima**: contexto externo
persistido + inferência sobre o usuário + maestro cruzando os dois numa única
observação fundamentada. Não é entregar um produto; é validar que a arquitetura
das Camadas 1b → 2 → 3 funciona de ponta a ponta. Uma observação boa = fatia
bem-sucedida.

## As três peças (mínimas)

**Peça A — Substrato exógeno (Camada 1b): índices setoriais B3.**
- Coletar e **persistir** uma seleção de índices setoriais da B3 (ex.: IMOB,
  UTIL, IEE, INDX, IFNC, ICON — os que cobrem os setores das posições atuais).
- Mesma mecânica já usada para os benchmarks (tabela append-only, coleta em
  lote, tolerância relativa, cron diário). Reaproveitar o padrão existente, não
  criar mecânica nova.
- O ponto conceitual: o contexto **sedimenta** numa tabela, não é lookup
  efêmero. Histórico diário acumula.

**Peça B — Inferência (Camada 2): concentração setorial real vs. IPS.**
- Ler as posições atuais (já classificadas por bloco IPS e por setor) do event
  log / projeções existentes.
- Calcular a concentração setorial **real** da carteira e comparar com o que a
  **IPS v1.0** declara (alvos e bandas por bloco).
- Output: por setor, exposição real vs. esperada, e o desvio (dentro/fora da
  banda).
- Reaproveitar a classificação setorial e a IPS que já existem. Não recadastrar
  nada.

**Peça C — Maestro (Camada 3): observação cruzada via nova tool MCP.**
- Nova tool MCP (sugestão de nome: `analise_aderencia_setorial`).
- Ela cruza A + B e retorna uma observação que une as duas lentes:
  *exposição setorial real vs. IPS (espelho) × desempenho recente do setor pela
  série B3 (janela)*.
- Exemplo de observação-alvo: "Bloco Growth está 6pp acima da banda superior da
  IPS, concentrado em [setor X]; o índice [setor X] recuou N% no último mês."
- A observação **reporta fatos** (princípio §5): não recomenda, não prescreve,
  não força tom. Convergência ("dentro da banda, setor estável") é resultado
  igualmente válido.

## Critérios de aceite (verificáveis)

1. Tabela de índices setoriais populada, com ≥30 dias de histórico após primeira
   coleta, seguindo o padrão das tabelas de benchmark.
2. Função de concentração setorial retorna, para cada setor com posição:
   exposição real %, alvo/banda IPS, e status (dentro/fora).
3. Tool MCP `analise_aderencia_setorial` acessível via Claude Desktop, retornando
   a observação cruzada em texto, com os números rastreáveis às peças A e B.
4. Toda métrica na observação vem de A ou B (regra anti-alucinação: nada
   estimado pelo modelo). Verificável: cada número tem origem em tool/tabela.
5. 32 testes de regressão existentes continuam passando. Nada do engine atual
   alterado.

## O que NÃO fazer nesta fatia

- NÃO integrar Partnr nem nenhuma fonte externa nova além dos índices B3.
- NÃO construir pipeline NotebookLM.
- NÃO criar múltiplos instrumentistas — esta fatia é o maestro fazendo o
  cruzamento diretamente. Orquestra plural fica para depois.
- NÃO tocar no frontend (Streamlit fica como está; saída é via MCP).
- NÃO implementar proatividade/agendamento da observação — por ora ela é
  chamada sob demanda via tool. O "ensaio contínuo" vem depois.
- NÃO alterar engine, cálculo de performance, ou schema de posições além de
  adicionar a tabela setorial.

## Fluxo de trabalho (já estabelecido)

Local primeiro → teste com dados sintéticos → commit/push → backup on-demand →
migração Alembic para a tabela setorial → validar em produção.

## Por que esta fatia (contexto para o executor)

O app hoje mede a carteira com excelência mas não *aprende* nem *cruza* contexto
externo com comportamento interno. Esta fatia instala, em miniatura, esse
cruzamento — a "tradução" que é o coração do produto. Se funcionar, escala por
repetição (mais setores, mais inferências, mais instrumentistas). Ver
01-conceito.md §2 (duas lentes) e §6 (orquestra).
