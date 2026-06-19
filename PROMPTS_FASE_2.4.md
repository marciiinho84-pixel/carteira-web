# 🎯 Prompts para Claude Code — Fase 2.4 expandida

Total: **6 fases sequenciais** cobrindo as 3 correções pendentes + os 15 itens aprovados.

**Como usar:**
1. Copie e cole **uma fase por vez** no chat do Claude Code
2. Aguarde o relatório de conclusão
3. Valide os resultados
4. Só então cole a próxima

**Não pule fases.** Cada uma constrói sobre a anterior.

---

## 📋 Índice das fases

| Fase | Conteúdo | Esforço | Itens |
|---|---|---|---|
| [Fase 0](#fase-0) | Correções pendentes do MVP | 3-4h | 3 correções |
| [Fase 1](#fase-1) | Proteção crítica (backup + Var dia + IR mensal) | 5-6h | 1, 2, 3 |
| [Fase 2](#fase-2) | Usabilidade básica (mobile + export) | 4h | 4, 5 |
| [Fase 3](#fase-3) | Métricas de risco e retorno | 4h | 6, 7, 8, 9 |
| [Fase 4](#fase-4) | Integrações externas (proventos + RF venc) | 7h | 10, 11 |
| [Fase 5](#fase-5) | Polimento e features avançadas | 10h | 12, 13, 14, 15 |

---

<a name="fase-0"></a>
## 🔧 FASE 0 — Correções pendentes do MVP

**Pré-requisito:** estar no estado pós-Fase 2.3 (commits b62054d e b677da5).

**Cole isto no Claude Code:**

```
Execute as 3 correções identificadas nos testes de usabilidade,
na ordem abaixo. Reporte ao concluir cada uma antes da próxima.

═══════════════════════════════════════════════════════════
CORREÇÃO 1 — Edição e exclusão de eventos
═══════════════════════════════════════════════════════════

Adicione na página "Novo Evento" uma segunda seção
"✏️ Corrigir / Remover Evento":

1. Tabela com os últimos 20 eventos (mais recentes primeiro)
   Colunas: Data | Ativo | Tipo | Qtd | Valor | Observação | Ações

2. Cada linha com 2 botões:
   ✏️ Editar — abre formulário pré-preenchido. Ao salvar,
              substitui o evento e recalcula o engine.
   🗑️ Excluir — pede confirmação "Tem certeza? Essa ação
                recalculará toda a carteira."

3. Regras de segurança:
   - Não permitir excluir SALDO_INICIAL
   - Aviso se edição alterar Tipo (ex: COMPRA → VENDA)

4. Endpoints já existem (PATCH/DELETE /api/v1/eventos/{id})

Validação: refaça o Cenário 8 dos testes de usabilidade.
Lance COMPRA DIVO11 com valor errado R$ 9.999, edite para
R$ 999, confirme que custo médio recalcula.

═══════════════════════════════════════════════════════════
CORREÇÃO 2 — Cadastro de novo ativo via UI
═══════════════════════════════════════════════════════════

Em "Configurações → CAD_ATIVOS", adicione acima da tabela
um formulário expansível "➕ Cadastrar novo ativo":

Campos obrigatórios:
  Ticker     texto, uppercase automático
  Classe     dropdown: Renda Variável | Renda Fixa |
             Multimercado | Previdência
  Família    dropdown: Ação BR | BDR | BDR de ETF |
             ETF BR | Fundo CP | Fundo de Pensão |
             Fundo Indexado | Tesouro Direto |
             Letra de Crédito
  Setor      texto livre
  Composite  dropdown: Gerida | FUNCEF

Campos opcionais: Indexador | Benchmark | Observação

Validações:
- Ticker não pode duplicar (verifica contra banco)
- Mensagem após salvar: "BBAS3 cadastrado. Disponível
  em Novo Evento."

Endpoint já existe (POST /api/v1/ativos).

Validação: refaça o Cenário 2.

═══════════════════════════════════════════════════════════
CORREÇÃO 3 — D+1 para FIC FUNC no Calendário
═══════════════════════════════════════════════════════════

O Calendário D+2 da CARTEIRA_RV hoje rastreia apenas
famílias COTIZADO_PUBLICO.

Ajustes:
1. Incluir CAIXA FIC FUNC (família "Fundo CP") no calendário
   com prazo D+1 (fundos liquidam em 1 dia útil)

2. Diferenciar visualmente:
   "🔴 COMPRA EMBJ3   −R$ 1.510  [D+2]"
   "🟢 RESGATE FIC    +R$ 2.951  [D+1]"

3. Manter as cotas (R$, não em quantidade)

Validação: refaça o Cenário 6.

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "correções usabilidade: edição eventos,
   cadastro ativo, D+1 FIC FUNC"

2. Confirme: 32/32 regressões passando, 105 eventos,
   P&L R$ +3.629,15.

3. Reporte resultado dos 3 cenários revalidados (2, 6, 8).
```

---

<a name="fase-1"></a>
## 🛡️ FASE 1 — Proteção crítica

**Cobre:** Item 1 (backup) + Item 2 (var dia) + Item 3 (IR mensal)

**Cole isto no Claude Code:**

```
Implemente os 3 itens de proteção crítica nessa ordem.
Reporte ao concluir cada um antes da próxima.

═══════════════════════════════════════════════════════════
ITEM 1 — Backup automático do SQLite
═══════════════════════════════════════════════════════════

1. Crie script backend/scripts/backup.py que:
   - Copia o banco SQLite para ~/Carteira/backups/
   - Nomeia como carteira-YYYYMMDD-HHMMSS.db
   - Mantém apenas os últimos 30 backups (apaga mais antigos)
   - Loga ação em backend/logs/backup.log

2. Trigger automático:
   - Executa ao iniciar o Streamlit (1x por dia, se ainda
     não houver backup do dia atual)
   - Não bloqueia inicialização se falhar

3. Botão manual na aba Configurações → Sistema:
   "💾 Fazer backup agora" + lista dos últimos 5 backups
   com data/hora e tamanho

4. Documente em README como o user pode configurar sync
   externo (Google Drive, Dropbox via rclone) — apenas
   instruções, não implementa.

Validação:
- Iniciar Streamlit cria backup em ~/Carteira/backups/
- Botão manual cria backup imediato
- Lista mostra backups ordenados por data desc

═══════════════════════════════════════════════════════════
ITEM 2 — Variação no dia (D-1 vs hoje)
═══════════════════════════════════════════════════════════

1. Lógica no engine:
   - Para cada ativo: var_dia = (preço_hoje - preço_d-1) / preço_d-1
   - Para o total: var_dia_carteira = (patrim_hoje - patrim_d-1) / patrim_d-1
   - "D-1" = último dia útil anterior ao último cache disponível

2. Exibição no Dashboard:
   - Novo KPI grande no topo: "Variação Hoje: +R$ 2.340 (+0,17%)"
   - Setinha ↑ verde ou ↓ vermelho
   - Quando não houver D-1 (1º cálculo): mostra "—"

3. Exibição em Posições:
   - Nova coluna "Var dia" entre "Preço Atual" e "Valor"
   - Cor verde positivo / vermelho negativo
   - Formato: "+R$ 0,52 (+1,8%)"

4. API:
   - GET /api/v1/dashboard inclui campo var_dia
   - GET /api/v1/posicoes inclui var_dia por ativo

Validação:
- Em modo --no-api, var_dia = 0 (sem preço D-1 disponível)
- Em modo API ligada, var_dia calcula corretamente

═══════════════════════════════════════════════════════════
ITEM 3 — IR mensal estimado sobre vendas
═══════════════════════════════════════════════════════════

REGRAS DE TRIBUTAÇÃO BR (aplicar exatamente):

Pool de cálculo:
- "Comum" = Ação BR + BDR + ETF (mesmo pool para
  compensação)
- Não considerar day-trade separadamente nesta versão

Isenção mensal (apenas Ações BR):
- Se TODAS as vendas do mês forem de Ação BR E
  volume total das vendas < R$ 20.000:
  → ISENTO
- Se mês tem qualquer venda de BDR ou ETF: TRIBUTÁVEL
- Se mês tem só Ação BR mas vendeu >= R$ 20.000: TRIBUTÁVEL

Cálculo:
- Lucro tributável do mês = soma P&L positivos
- Pode compensar com prejuízo acumulado (saldo anterior)
- IR = 15% × (lucro_tributável - prejuízo_compensado)
- Se lucro - compensação < 0: vira novo prejuízo acumulado

DARF:
- Código 6015
- Vencimento: último dia útil do mês seguinte
- Só gera DARF se IR > R$ 10,00 (regra Receita)

Implementação:

1. Função no engine: calc_ir_mensal(eventos, ativos)
   Retorna: {mes: {volume_vendas, lucro_bruto, lucro_compensado,
            ir_devido, prejuizo_acumulado, status}}

2. Endpoint: GET /api/v1/ir-mensal

3. UI em "Vendas Realizadas":
   Painel destaque mês atual:
   ┌─────────────────────────────────────────────┐
   │ IMPOSTO DE RENDA — MAIO/2026                │
   │ Volume vendas:    R$ 4.082,50 (Ações BR)    │
   │ Status:           ISENTO ✓                  │
   │ IR a pagar:       R$ 0,00                   │
   │ Prejuízo acum.:   R$ 0,00                   │
   └─────────────────────────────────────────────┘

   Histórico mensal abaixo (tabela):
   Mês | Volume | Lucro | Compensação | IR | Status

4. Alerta:
   - Se houver IR a pagar este mês: card destaque no
     Dashboard com vencimento DARF
   - "DARF R$ X vence em DD/MM (último dia útil)"

Validação:
- Maio/2026: R$ 4.082,50 em vendas (PETR4 + PRIO3 + PLPL3)
  Todas Ações BR, < R$ 20k → ISENTO
- Janeiro/2026: R$ 1.800 BSLV39 (BDR)
  Tem BDR → TRIBUTÁVEL. Lucro R$ 300,10 → IR R$ 45,02

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.4 bloco 1: backup, var dia, IR mensal"
2. Confirme: 32/32 regressões passando
3. Mande print de cada uma das 3 novas funcionalidades:
   - Lista de backups na Configurações
   - Var dia no Dashboard e em Posições
   - Painel de IR em Vendas Realizadas
```

---

<a name="fase-2"></a>
## 📱 FASE 2 — Usabilidade básica

**Cobre:** Item 4 (mobile) + Item 5 (export)

**Cole isto no Claude Code:**

```
Implemente os 2 itens de usabilidade nessa ordem.

═══════════════════════════════════════════════════════════
ITEM 4 — Responsividade mobile
═══════════════════════════════════════════════════════════

1. Configure o app para mobile-friendly:
   - .streamlit/config.toml com layout configurável
   - Adicione meta viewport correto

2. Valide cada uma das 8 páginas em viewport 375px
   (iPhone padrão):

   ☐ Dashboard
   ☐ Carteira RV
   ☐ Posições
   ☐ Novo Evento
   ☐ Vendas Realizadas
   ☐ Meta Patrimônio
   ☐ Evolução
   ☐ Configurações

3. Ajustes esperados em mobile:
   - Sidebar colapsa por padrão (Streamlit já faz)
   - KPIs em coluna única (não 4 lado a lado)
   - Treemap: redimensionar com altura mínima 300px
   - Tabelas com scroll horizontal indicado (banda lateral)
   - Gráficos Plotly: use responsive=True
   - Botões grandes (mínimo 44x44px — padrão Apple)

4. NÃO crie design alternativo mobile-only. Apenas garanta
   que o layout existente se ajusta bem em telas pequenas.

Validação:
- Use ferramenta de desenvolvedor do navegador (Ctrl+Shift+M
  no Firefox/Chrome) para simular iPhone
- Cada página deve ser navegável sem zoom horizontal
- Documente em screenshots quais ajustes foram necessários

═══════════════════════════════════════════════════════════
ITEM 5 — Exportação CSV/Excel
═══════════════════════════════════════════════════════════

Adicione botão "📥 Exportar" nas seguintes tabelas:

1. Posições (todas as posições atuais)
2. Vendas Realizadas
3. Eventos (na página "Novo Evento", seção corrigir)
4. Evolução (série temporal completa)
5. Atribuição Mensal (após implementação Fase 3)
6. CAD_ATIVOS (em Configurações)

Para cada botão, oferecer 2 formatos:
- 📄 CSV (encoding UTF-8 com BOM para abrir bem no Excel BR)
- 📊 XLSX (com formatação básica)

Nome do arquivo: {tabela}_{YYYY-MM-DD}.csv

Use:
- pandas.to_csv() para CSV
- openpyxl para XLSX

Validação:
- Exportar Posições gera arquivo válido
- Abre corretamente no LibreOffice Calc
- Caracteres acentuados aparecem certos
- Datas no formato brasileiro (dd/mm/yyyy)
- Valores em R$ com vírgula decimal

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.4 bloco 2: mobile responsivo, export CSV/Excel"
2. 32/32 regressões passando
3. Mande:
   - Screenshot de 3 páginas em viewport mobile
   - Print de um arquivo exportado aberto no LibreOffice
```

---

<a name="fase-3"></a>
## 📊 FASE 3 — Métricas de risco e retorno

**Cobre:** Item 6 (drawdown) + Item 7 (volatilidade) + Item 8 (beta) + Item 9 (yield)

**Cole isto no Claude Code:**

```
Implemente as 4 métricas de risco e retorno. As três primeiras
são cálculo direto sobre o engine existente (rápidas). O yield
projetado tem mais complexidade.

═══════════════════════════════════════════════════════════
ITEM 6 — Drawdown máximo histórico
═══════════════════════════════════════════════════════════

1. Drawdown já é calculado no engine (df_evo["drawdown"]).
   Só precisa exibir.

2. Adicione no Dashboard, novo card:
   "Drawdown máximo YTD: −X,XX% (em DD/MM/AAAA)"

3. Adicione na página Evolução:
   - Gráfico "underwater" (drawdown ao longo do tempo)
   - Área preenchida em vermelho abaixo de zero
   - Eixo Y em %, X em data

4. API: GET /api/v1/dashboard já retorna drawdown_max e
   drawdown_max_data — exporte se ainda não estiver.

Validação:
- Card aparece no Dashboard
- Gráfico underwater na Evolução
- Valor bate com cálculo manual sobre df_evo

═══════════════════════════════════════════════════════════
ITEM 7 — Volatilidade anualizada
═══════════════════════════════════════════════════════════

1. Calcular no engine:
   vol_diaria = std(retornos_diarios_gerida)
   vol_anualizada = vol_diaria * sqrt(252)

2. Adicionar no Dashboard:
   Card "Volatilidade anualizada: XX,X% a.a."
   Comparação: "IBOV ~25% a.a. típico"

3. Calcule também separadamente para a Carteira RV
   isolada (sub-portfolio).

Validação:
- Card aparece
- Em modo --no-api, volatilidade da Gerida pode ser baixa
  (preços RV constantes) — esperado
- Com APIs ligadas, valor deve ser razoável (10-25%)

═══════════════════════════════════════════════════════════
ITEM 8 — Beta vs IBOV
═══════════════════════════════════════════════════════════

1. Calcular:
   beta = Cov(retornos_gerida, retornos_ibov) / Var(retornos_ibov)

   Usar janela YTD (todos os dias úteis desde 02/01/2026).
   Se houver menos de 20 observações: mostrar "—" (amostra pequena).

2. Adicionar no Dashboard:
   Card "Beta vs IBOV: X,XX"
   Interpretação textual:
   - beta < 0.5 → "Defensiva"
   - beta 0.5-0.8 → "Moderada"
   - beta 0.8-1.2 → "Alinhada ao mercado"
   - beta > 1.2 → "Agressiva"

3. Calcule também o beta da Carteira RV isolada vs IBOV.

Validação:
- Card aparece
- Em modo --no-api, beta pode ser 0 ou pequeno (preços RV não variam)
- Com APIs ligadas, beta da Gerida deve ser baixo (~0,2-0,4)
  por causa do peso grande do FIC FUNC/LCI/OURO

═══════════════════════════════════════════════════════════
ITEM 9 — Yield projetado do portfolio
═══════════════════════════════════════════════════════════

LÓGICA DE CÁLCULO POR ATIVO:

Renda Variável (Ações BR, BDR, ETF):
- yield_realizado_12m = proventos_pagos_ultimos_12m / preco_atual
- Como temos apenas ~4,5 meses de histórico, anualize:
  yield_projetado = (proventos_pagos_no_periodo / preco_atual) * (12 / meses_disponíveis)
- Se ativo tem 0 proventos no histórico: yield = 0 (informativo)

Renda Fixa:
- CAIXA LCI: yield contratado se conhecido (vai no Indexador
  do CAD_ATIVOS). Para esta carteira, usar CDI atualizado.
- CAIXA FIC FUNC: yield realizado = (valor_atual - valor_aplicado) / valor_aplicado, anualizado
- C6 RENDA+: IPCA + cupom (consultar do CAD_ATIVOS se houver)

Outros:
- FUNCEF: 0% (não distribui, retorno é via valorização da cota)
- CAIXA OURO: 0% (não distribui)

CÁLCULO TOTAL DO PORTFOLIO:
yield_carteira = Σ (peso_ativo × yield_ativo)

EXIBIÇÃO:

1. Card no Dashboard:
   "Yield projetado 12m: X,XX% a.a."
   "Renda passiva estimada: R$ XX.XXX/ano (R$ X.XXX/mês)"

2. Tabela na página Posições — adicionar coluna
   "Yield 12m" entre "P&L %" e "Concentração"

Validação:
- Card aparece com valor razoável
- Para FUNCEF: yield = 0%
- Para LCI: yield ~ CDI atual
- Para PETR4 (alta paga dividendos): yield estimado entre 5-15%

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.4 bloco 3: drawdown, vol, beta, yield"
2. 32/32 regressões passando
3. Print do Dashboard com os 4 novos cards aparecendo
```

---

<a name="fase-4"></a>
## 📅 FASE 4 — Integrações externas

**Cobre:** Item 10 (proventos esperados) + Item 11 (vencimentos RF)

**Cole isto no Claude Code:**

```
Implemente as duas integrações externas. O Item 10 é o mais
complexo do roadmap (depende de fonte externa).

═══════════════════════════════════════════════════════════
ITEM 11 — Vencimentos de Renda Fixa em destaque
═══════════════════════════════════════════════════════════

(Faça este PRIMEIRO — é mais simples e independente.)

1. Adicionar coluna `data_vencimento` na tabela `ativos`
   (alembic migration), tipo DATE nullable.

2. Popular para LCI no banco:
   UPDATE ativos SET data_vencimento = '2028-10-03'
   WHERE ticker = 'CAIXA LCI';

   (Outros ativos da carteira atual não têm vencimento.
    Demais Letras de Crédito futuras devem ter campo
    preenchido no cadastro.)

3. Adicionar no formulário "Cadastrar novo ativo"
   (Configurações):
   - Campo "Data de vencimento" (opcional, só aparece se
     família = Letra de Crédito, Tesouro Direto ou
     Fundo Indexado)

4. Adicionar na página de edição de ativo:
   - Mesmo campo data_vencimento

5. Card permanente no Dashboard:
   ┌──────────────────────────────────────────┐
   │ PRÓXIMOS VENCIMENTOS RF                  │
   │ ─────────────────────────────────────    │
   │ CAIXA LCI    870 dias    03/10/2028      │
   │              R$ 28.818,56 brutos          │
   └──────────────────────────────────────────┘

6. Alerta automático:
   - Quando faltarem ≤ 90 dias: card em amarelo
   - Quando faltarem ≤ 30 dias: card em vermelho com
     mensagem "Decidir reinvestir ou usar o recurso"

Validação:
- Card aparece no Dashboard
- LCI mostra "870 dias" (cálculo automático)

═══════════════════════════════════════════════════════════
ITEM 10 — Calendário de proventos esperados
═══════════════════════════════════════════════════════════

ABORDAGEM EM 2 PARTES:

Parte A — Proventos já anunciados (não-pagos ainda):
Buscar em fonte externa proventos com data-com no futuro
ou data-ex próxima.

Fontes possíveis (avalie qual é mais estável):
- statusinvest.com.br (scraping)
- API da B3 (oficial — complexo)
- Investidor10 (scraping)

Crie módulo backend/engine/proventos_externos.py:
- buscar_proventos_anunciados(ticker) → lista de dicts
  {data_com, data_ex, data_pagamento, valor_por_acao, tipo}
- Cache local (não chamar API toda hora)

Parte B — Proventos projetados (estatística histórica):
Para cada ativo da Carteira RV:
- Pegar proventos pagos no mesmo mês ano anterior
- Ajustar pela qtd atual de ações
- Projetar como "esperado" no próximo mês equivalente

EXIBIÇÃO:

Nova página/seção "📅 Calendário de Proventos":

Tabela com:
| Data Pgto. | Ativo | Tipo | Por ação | Total | Status |
| 25/05/2026 | ITUB3 | JCP  | R$ 0,21  | R$ 8,40 | Anunciado |
| 15/06/2026 | PETR4 | DIV  | R$ 0,50* | R$ —    | Projetado* |

Onde:
- "Anunciado" = dados da fonte externa
- "Projetado*" = baseado em histórico (marcar com asterisco)

Card no Dashboard:
"Próximos proventos: 3 anunciados nos próximos 30 dias
 Total esperado: R$ XX,XX"

OBSERVAÇÕES IMPORTANTES:
- Se a integração externa falhar, mostrar mensagem clara:
  "Fonte indisponível — usando apenas projeções históricas"
- NÃO incluir como receita garantida no Dashboard principal
  (proventos são estimativas)

Validação:
- Página/seção criada
- Pelo menos 1 ativo com provento exibido
- Se fonte falhar, fallback funciona

═══════════════════════════════════════════════════════════
ENCERRAMENTO
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.4 bloco 4: vencimentos RF, proventos esperados"
2. 32/32 regressões passando
3. Reporte:
   - Qual fonte de proventos foi escolhida e por quê
   - Funciona offline (fallback)?
   - Prints da página de proventos e card de vencimentos RF
```

---

<a name="fase-5"></a>
## 🎨 FASE 5 — Polimento e features avançadas

**Cobre:** Item 12 (dark mode) + Item 13 (diário) + Item 14 (correlação) + Item 15 (what-if)

**Cole isto no Claude Code:**

```
Implemente os 4 itens de polimento/avançado nessa ordem
(do mais simples ao mais complexo).

═══════════════════════════════════════════════════════════
ITEM 12 — Dark mode
═══════════════════════════════════════════════════════════

1. Adicione toggle 🌙/☀️ na sidebar (topo)

2. Use o sistema de tema do Streamlit (config.toml +
   st.set_page_config) ou st_theme se preciso de mais controle.

3. Persista a preferência no session_state ou cookie.

4. Ajustes nos gráficos Plotly:
   - Detectar tema ativo
   - Aplicar paleta apropriada (escuro = fundo grafite)

Validação:
- Toggle funciona em todas as 8 páginas
- Gráficos respeitam o tema escolhido
- Preferência persiste entre páginas

═══════════════════════════════════════════════════════════
ITEM 13 — Decision journal
═══════════════════════════════════════════════════════════

1. Nova tabela `decisoes`:
   - id (PK)
   - data_decisao (DATE)
   - evento_id (FK opcional → eventos.id)
   - ativo (FK ativos.ticker)
   - acao (COMPRA / VENDA / MANTER / OBSERVAR)
   - tese (TEXT — texto livre)
   - expectativa_retorno_pct (FLOAT — opcional)
   - horizonte (curto / medio / longo)
   - revisao_em (DATE — quando lembrar de revisar)
   - resultado_revisao (TEXT — preenchido depois)
   - notas (TEXT — anotações pós-revisão)

2. Migration alembic + endpoint REST completo

3. Interface — nova página "📓 Diário de Decisões":

   Seção 1 — Cadastrar nova decisão:
   - Botão "✏️ Nova decisão"
   - Form com todos os campos acima

   Seção 2 — Decisões aguardando revisão:
   - Lista de decisões cuja `revisao_em` <= hoje
   - Botão "Revisar agora"
   - Form para preencher resultado_revisao + notas

   Seção 3 — Histórico:
   - Tabela com todas as decisões
   - Filtros: por ativo, por ação, por horizonte

4. Integração no formulário de eventos:
   - Após salvar COMPRA, perguntar:
     "Deseja registrar sua tese para esta compra?"
   - Se sim, abre o form de decisão pré-preenchido

5. Notificação no Dashboard:
   - Se houver decisões aguardando revisão:
     Card "3 decisões aguardam revisão"
     Link para a página

Validação:
- Criar decisão funciona
- Revisão de decisão antiga funciona
- Notificação aparece quando aplicável

═══════════════════════════════════════════════════════════
ITEM 14 — Análise de correlação entre ativos
═══════════════════════════════════════════════════════════

1. Nova página "🔗 Correlação":

2. Matriz de correlação:
   - Pegar retornos diários de todos os ativos da Carteira RV
     (apenas ativos com preço público — yfinance/manual)
   - Calcular matriz de correlação (pearson) sobre janela
     escolhida pelo user (3m, 6m, YTD)
   - Renderizar como heatmap Plotly:
     - Escala: -1 (vermelho intenso) a +1 (verde intenso)
     - Diagonal = 1 (cinza claro)
     - Anotações com o valor em cada célula

3. Insights automáticos abaixo da matriz:
   - "Pares mais correlacionados (risco de concentração):"
     Lista os top 3 com correlação > 0,6
   - "Pares mais diversificadores:"
     Lista os top 3 com correlação < 0,2 ou negativa

4. Filtros:
   - Janela: 3m / 6m / YTD
   - Apenas RV / RV + RF / Tudo

5. Aviso:
   - Se houver menos de 30 observações: "Amostra pequena,
     correlações podem ser instáveis"

Validação:
- Heatmap renderiza corretamente
- Insights aparecem
- EMBJ3 + BAER39 esperado: correlação > 0,5 (mesmo setor)

═══════════════════════════════════════════════════════════
ITEM 15 — Cenários what-if simples
═══════════════════════════════════════════════════════════

Nova página "🔮 Simulação de Cenários":

Cenários pré-definidos (cards clicáveis):

1. 📉 Crash do IBOV (-20%):
   - Impacto estimado = peso_RV × beta × -20%
   - Mostra: "Patrimônio cairia de R$ X para R$ Y (-Z%)"

2. 📈 Alta forte do IBOV (+20%):
   - Espelho do anterior

3. 💵 Dólar +15%:
   - Beneficia BDRs (são em USD via custódia BR)
   - Impacto = peso_BDR × +15%

4. 💵 Dólar -15%:
   - Espelho

5. 🏦 Selic sobe para 16%:
   - Beneficia LCI/FIC FUNC/Renda+
   - Penaliza ações (impacto via beta)

6. 🏦 Selic cai para 8%:
   - Espelho

Permita cenário customizado:
- Sliders para: IBOV (%), USD (%), Selic (%)
- Calcula impacto em tempo real

Apresentação:
- Card com patrimônio "antes" (real atual)
- Card com patrimônio "depois" (simulado)
- Diferença em R$ e %
- Decomposição: quanto vem de cada classe de ativo

Validação:
- Cenários pré-definidos funcionam
- Cenário customizado responsivo
- Cálculo usa beta calculado no Item 8

═══════════════════════════════════════════════════════════
ENCERRAMENTO FINAL DA FASE 2.4
═══════════════════════════════════════════════════════════

1. git commit -am "fase 2.4 bloco 5: dark mode, diário, correlação, what-if"

2. Estado consolidado:
   - 32/32 regressões passando ✓
   - Ferramenta com 11 páginas funcionais
   - Backup automático ativo
   - Mobile responsivo
   - Métricas: drawdown, vol, beta, yield, IR mensal
   - Calendário proventos + vencimentos RF
   - Diário de decisões + correlação + simulação

3. Reporte sumário final:
   - Total de linhas de código adicionadas
   - Páginas implementadas
   - Endpoints REST disponíveis
   - Próximo passo proposto (Fase 2.5 — deploy/PWA?)
```

---

## 🎯 Sequência sugerida de execução

```
HOJE
  └─ Fase 0 (3-4h)         — Correções pendentes
       └─ Validar
            └─ Fase 1 (5-6h)   — Proteção crítica
                 └─ Validar
                      └─ Fase 2 (4h)   — Usabilidade
                           └─ Validar
                                └─ Fase 3 (4h)   — Métricas
                                     └─ Validar
                                          └─ Fase 4 (7h)  — Integrações
                                               └─ Validar
                                                    └─ Fase 5 (10h) — Polimento
```

**Total estimado:** ~33-34 horas de trabalho do Claude Code. Pode levar 2-3 sessões dependendo de quanto contexto ele acumula.

## 💡 Dica entre fases

Após cada fase, antes de partir para a próxima:

1. Rode o teste de regressão (deve ser 32/32 ainda)
2. Abra o Streamlit e clique nas funcionalidades novas
3. Faça commit Git (se o Claude Code já não fez)
4. Anote bugs cosméticos para corrigir em batch no final

---

Quando quiser começar, copie a **Fase 0** e cole no Claude Code. Boa sorte! 🚀
