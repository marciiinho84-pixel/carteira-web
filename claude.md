# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
[Step] → verify: [check]

[Step] → verify: [check]

[Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## 5. Carteira Clean — Fluxos e UX de Registro

### Como registrar uma COMPRA de ativo

**Caso A — Dinheiro NOVO (recurso externo que entra na carteira):**

1. Registrar `APORTE_EXTERNO` no ativo recebedor (ex: CAIXA FIC FUNC), com o valor do aporte
2. Registrar `COMPRA` do ativo-alvo com o checkbox **"Descontar do FIC FUNC" DESMARCADO**

> Por quê: O `APORTE_EXTERNO` é processado por `twr.py` como fluxo externo (denominador do TWR). Isso isola o capital novo da rentabilidade real da carteira — sem distorção de performance.

**Caso B — Dinheiro já na carteira (FIC FUNC ou proventos de venda):**

1. Registrar `COMPRA` do ativo-alvo com o checkbox **"Descontar do FIC FUNC" MARCADO**
   - O sistema auto-cria um `RESGATE` do FIC FUNC na mesma data e valor

> Por quê: É uma transferência interna — nenhum capital externo entra na carteira, então não há fluxo a registrar.

### Mapeamento técnico

| Tipo de evento | Família válida | Efeito no TWR |
|---|---|---|
| `APORTE_EXTERNO` | qualquer | fluxo positivo no denominador (neutro para performance) |
| `RESGATE_EXTERNO` | qualquer | fluxo negativo no denominador |
| `CONTRIBUICAO` | FUNCEF | fluxo para carteira FUNCEF |
| `COMPRA` | qualquer | transferência interna (sem efeito no fluxo externo) |

**Regra chave:** `FLUXOS_EXTERNOS = {"CONTRIBUICAO", "RESGATE_EXTERNO", "APORTE_EXTERNO"}` — processados diretamente em `twr.py` linhas 115-122, independente de qualquer cutoff de data em `inferencia.py`.
