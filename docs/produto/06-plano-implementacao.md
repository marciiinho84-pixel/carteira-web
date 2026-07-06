# Plano Mestre — App Minha Carteira

*Visão macro do projeto. Onde estamos, o que falta, por que decidimos X.*
*Detalhes de execução: ver 07-prompts-implementacao.md (Fases 1-5).*
*Polimento em andamento: ver polimento/*.md*

---

## Estado atual (26/06/2026)

| Camada | Status |
|---|---|
| 1a — endógeno | ✅ Event sourcing, TWR, Brinson-Fachler, 38 ativos, backup GCS |
| 1b — exógeno | ✅ Setoriais B3, fundamentos yfinance, macro BCB, eventos corporativos |
| 2 — declarada | ✅ IPS v1.0 + bloco_ips, teses, diário, risco, aporte/caixa |
| 2 — inferida | ✅ Perfil comportamental, dito-vs-feito, 5 vieses nomeados |
| 3 — maestro | ✅ ~40 tools MCP, orquestra funcional |
| 4 — interface | ✅ React (Next.js), 10 páginas, Sala de Comando, Maestro |
| — polimento | 🟡 Em andamento |

**Infraestrutura:**
- VM `carteira-clean` (e2-small, us-central1-a, 25GB disco, 2GB swap permanente)
- Docker: 6 containers (backend, frontend/Streamlit, nextjs, mcp, caddy, postgres)
- Auth: Google OAuth (NextAuth.js), JWT 30 dias
- Deploy automático: push master → GitHub Actions → VM via IAP
- Crons: cotações 21h30, fundamentos 22h15, macro 22h20, backup pg_dump 22h, Focus seg 12h, DNS 3h

---

## Princípios (governam todo o projeto)

**Aprender.** O sistema aprende sobre o mundo (1b) e sobre o usuário (2).

**Prova fiduciária.** Toda observação carrega sua proveniência. Interface torna rastreabilidade visível.

**Interface conectada.** Tudo clicável leva ao detalhe. Sem becos sem saída.

**Níveis de automação:**
| Nível | Nome | Default |
|---|---|---|
| L1 | Informar | — |
| **L2** | **Aconselhar** | **Sim** |
| L3 | Propor | — |
| L4 | Executar sob política | — |

Configurável por bloco IPS. L5 não existe.

---

## Fases — status

| Fase | Fatias | Status | Detalhes |
|---|---|---|---|
| 1 — Substrato exógeno | 1, 2, 3 | ✅ | 07-historico, seção Fase 1 |
| 2 — Disciplinas de gestão | 4, 5, 6, 7 | ✅ | 07-historico, seção Fase 2 |
| 3 — Inferência comportamental | 8, 9, 8b | ✅ | 07-historico, seção Fase 3 |
| 4 — Instrumentistas | 10, 11, 12, 13, glossário | ✅ | 07-historico, seção Fase 4 |
| 5 — Interface React | 14, 15, 16, 16.1, 17 | ✅ | 07-historico, seção Fase 5 |
| — Polimento | — | 🟡 | polimento/*.md |
| 6 — Temperamento + mobile | 18, 19 | 🔜 | 07, seção Fases futuras |
| 7 — Extensões | 20-23 | — | 07, seção Fases futuras |

---

## Decisões fechadas

| # | Decisão | Escolha | Justificativa |
|---|---|---|---|
| D1 | Fonte de dados | yfinance + BCB (grátis) | APIs pagas avaliadas e adiadas |
| D2 | Arquitetura agentes | Tools sob maestro | 1 usuário, complexidade não se justifica |
| D4 | Generative UI | SSE customizado + Anthropic direto | CopilotKit previsto mas não usado |
| D5 | Banco | PostgreSQL Docker na VM | Cloud SQL adiado (custo) |
| D6 | Auth | Google OAuth (NextAuth.js) | Magic link descartado (UX ruim) |
| D9 | Matriz macro→setor | Estática editável (15 seeds) | — |
| D10 | Gráficos | Plotly HTML interativo, pandas puro | — |

## Decisões abertas

| # | Decisão | Impacta |
|---|---|---|
| D7 | Pertinência configurada + aprendida | Fatia 19 |
| D11 | Mobile: PWA vs. nativo | Fatia 18 |

---

## Protocolo de execução

1. Conceito (01) é a constituição — nunca contrariar.
2. Brief no chat antes de código.
3. Deploy é na VM GCP. Push → GitHub Actions → deploy automático.
4. Streamlit em paralelo até validação manual completa.
5. Auditoria grep antes de declarar migração completa.
6. Polimento: ver polimento/*.md para cada frente.

---

*Próxima ação: Polimento do Maestro (polimento/01-maestro.md)*
