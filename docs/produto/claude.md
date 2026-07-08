# CLAUDE.md — App Minha Carteira

*Instruções para o Claude Code. Lido em toda sessão.*

---

## Sobre o projeto

App Minha Carteira — sistema self-hosted de gestão de portfólio
de investimentos pessoais. Economista brasileiro, investidor
individual. Metáfora orquestral: usuário = maestro/compositor,
~40 tools MCP = instrumentistas, IA orquestradora = maestro.

Conceito central: duas lentes acopladas — "janela para fora"
(contexto de mercado) + "espelho para dentro" (padrões
comportamentais do investidor). A decisão é sempre do usuário.

---

## Stack e infra

| Componente | Detalhe |
|---|---|
| Backend | FastAPI, porta 8000 |
| Frontend React | Next.js em Docker, porta 3000 |
| Frontend legado | Streamlit, porta 8501 (paralelo em /streamlit/) |
| MCP | FastMCP, porta 8001, ~40 tools, Bearer token |
| Banco | **PostgreSQL** em Docker (NÃO SQLite) |
| Proxy | Caddy (HTTPS, Let's Encrypt, basic auth) |
| Auth | Google OAuth (NextAuth.js), whitelist marciiinho84@gmail.com, JWT 30 dias |
| VM | `carteira-clean`, e2-small, us-central1-a, IP 34.122.120.77, 25GB disco, 2GB swap |
| DNS | minhacarteira.duckdns.org |
| Backup | pg_dump → GCS gs://carteira-backup-474073, cron 22h UTC |

## Deploy — REGRAS CRÍTICAS

**O ambiente de produção é EXCLUSIVAMENTE a VM GCP `carteira-clean`.**
Nunca fazer deploy no servidor local. Todo deploy:
1. Confirmar hostname da VM antes de agir
2. Validar pela URL pública (minhacarteira.duckdns.org) depois

**Deploy automático:** push no master → GitHub Actions (.github/workflows/deploy.yml)
→ SSH via IAP → git pull + docker compose build + up -d.
Usa Workload Identity Federation (sem secrets no GitHub).

**⚠️ O workflow deve rebuildar TODOS os containers**, não só nextjs.
Mudanças no backend não chegam à VM se o workflow só faz build do nextjs.

**Deploy manual (quando necessário):**
```bash
gcloud compute ssh carteira-clean --zone=us-central1-a --tunnel-through-iap -- \
  "cd /home/marciiinho84/carteira-web && git pull && sudo docker compose build --no-cache && sudo docker compose up -d"
```

**SSH:** exclusivamente via IAP tunnel. Porta 22 NÃO está aberta.
```bash
gcloud compute ssh carteira-clean --zone=us-central1-a --tunnel-through-iap
```

## Verificação de sincronismo VM ↔ GitHub

Endpoint público (sem auth, sem SSH) que expõe o commit git rodando na VM:

```
GET https://minhacarteira.duckdns.org/api/status/deploy
```

Retorna `git_commit_hash`, `git_commit_date`, `git_commit_message` (do HEAD
no momento do build da imagem Docker), `deployed_at` (timestamp do build) e
`status` (health check simples do banco). Só metadado — nenhum dado de
portfólio, credencial ou path interno.

Uso: comparar `git_commit_hash` com `git rev-parse HEAD` do master local/GitHub
para confirmar que o deploy foi aplicado. Pode ser chamado do Cowork ou
qualquer ferramenta externa via `fetch` simples, sem precisar de SSH na VM.

Implementação: `carteira_clean_web/backend/api/main.py` (rota `status_deploy`),
`scripts/generate_build_info.py` (roda no build da imagem e grava
`/app/build_info.json` com o HEAD do `.git` copiado para o contexto de build).

## Banco de dados

- **PostgreSQL** no container `carteira-web-postgres-1`
- Migrations Alembic (0001-0008). Rodar com:
  `sudo docker exec carteira-web-backend-1 alembic upgrade head`
- Tabela de eventos: `eventos` (não "events"). Coluna `ativo` tem ticker direto
- **NUNCA usar sqlite3.connect()** — tudo via SQLAlchemy/session.py
- Constraint UNIQUE em séries temporais (ticker, data) para prevenir duplicatas

## Crons na VM

| Horário (UTC) | O que faz |
|---|---|
| 03:00 | Duck DNS renewal |
| 21:30 | Coleta cotações (yfinance) |
| 22:00 | Backup pg_dump → GCS |
| 22:15 | Coleta fundamentos (yfinance) |
| 22:20 | Coleta macro (BCB SGS) |
| Seg 12:00 | Focus BCB (Olinda) |

## IPS — Classificação de ativos

**Fonte de verdade: coluna `bloco_ips` na tabela `ativos` do PostgreSQL.**
Consultar com: `SELECT ticker, bloco_ips FROM ativos ORDER BY bloco_ips;`

| Bloco | Alvo | Banda | Benchmark |
|---|---|---|---|
| SWING_TRADE | 30% | ±10pp | IBOV |
| GROWTH | 20% | ±10pp | Nasdaq BRL |
| DEFENSIVOS | 20% | ±5pp | Ouro BRL |
| RENDA_FIXA | 30% | ±5pp | CDI |
| FORA_IPS | — | — | — |

**FUNCEF fica FORA da atribuição IPS.** Composite="FUNCEF".
Não mostrar o que não se controla.

## Documentação do projeto

```
docs/produto/
├── 01-conceito.md          ← constituição (raramente muda)
├── 02-estrutura.md         ← arquitetura
├── 03-leituras-x-estrutura.md
├── 04-reconciliacao.md
├── IPS.md
├── 06-plano-implementacao.md  ← plano mestre (onde estamos, decisões)
├── 07-prompts-implementacao.md ← registro histórico (Fases 1-5 congeladas, 6-7 futuras)
└── polimento/
    ├── 00-indice.md        ← índice das frentes de polimento
    ├── 01-maestro.md       ← polimento do Maestro (atual)
    └── ...                 ← páginas (criadas quando iniciar)
```

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them.
- If a simpler approach exists, say so.
- If something is unclear, stop and ask.

## 2. Simplicity First

**Minimum code that solves the problem.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No speculative "flexibility".
- If 200 lines could be 50, rewrite.

## 3. Surgical Changes

**Touch only what you must.**

- Don't "improve" adjacent code.
- Match existing style.
- Remove only what YOUR changes made unused.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

For multi-step tasks: [Step] → verify: [check]

## 5. Fluxos de registro — Carteira

### Registrar COMPRA

**Caso A — Dinheiro NOVO (recurso externo):**
1. Registrar `APORTE_EXTERNO` no ativo recebedor (ex: CAIXA FIC FUNC)
2. Registrar `COMPRA` com checkbox "Descontar do FIC FUNC" DESMARCADO

**Caso B — Dinheiro já na carteira:**
1. Registrar `COMPRA` com checkbox "Descontar do FIC FUNC" MARCADO
   (auto-cria RESGATE do FIC FUNC)

### Mapeamento técnico

| Tipo | Efeito no TWR |
|---|---|
| APORTE_EXTERNO | fluxo positivo (neutro para performance) |
| RESGATE_EXTERNO | fluxo negativo |
| CONTRIBUICAO | fluxo para carteira FUNCEF |
| COMPRA | transferência interna (sem efeito no fluxo) |

`FLUXOS_EXTERNOS = {"CONTRIBUICAO", "RESGATE_EXTERNO", "APORTE_EXTERNO"}`

## 6. Níveis de automação

| Nível | Nome | Default |
|---|---|---|
| L1 | Informar | — |
| **L2** | **Aconselhar** | **Sim** |
| L3 | Propor | — |
| L4 | Executar sob política | — |

Configurável por bloco IPS. L5 não existe.
Tools de escrita do Maestro: L2 com confirmação (propõe, mostra, usuário aprova antes de gravar).

## 7. O que NÃO fazer

- NÃO usar sqlite3 — tudo via SQLAlchemy/PostgreSQL
- NÃO fazer deploy no servidor local — só VM GCP
- NÃO desligar o Streamlit sem aval explícito do Márcio
- NÃO remover arquivos de páginas removidas do navbar (tools MCP continuam)
- NÃO fabricar dados no Maestro — reportar quando falta dado
- NÃO recomendar compra/venda — reportar fatos
- NÃO tratar FUNCEF como parte da carteira gerida
