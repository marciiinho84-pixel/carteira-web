# Polimento — Maestro ✅ CONCLUÍDO

*Origem: conversa real do Márcio com o Maestro revelou deficiências.*
*Auto-diagnóstico do Maestro: "todas as minhas ferramentas são de*
*leitura. Vejo, analiso, sugiro — mas não registro nem vigio."*

*4 camadas executadas e validadas. Concluído em 28/06/2026.*

---

## Camada 1 — Fundação (bugs) ✅

### Bug 1.1 — Tela do ativo em branco (DetalheAtivo) ✅
**Causa:** `ativo_detalhe.py` usava `metricas_atuais` (não existe)
para extrair P/L, ROE etc. **Correção:** usar `todos_indicadores`
com as chaves reais ("P/L", "P/VP", "ROE (%)", "DY (%)",
"Margem EBITDA (%)", "Dív.Líq/EBITDA").

Gráfico em branco: componente GraficoTecnicoSSE tentava parsear SSE
e nunca achava HTML. Substituído por GraficoTecnico que chama
GET /ativos/{ticker}/grafico e renderiza iframe.

### Bug 1.2 — Gráfico técnico no chat do Maestro ✅
**Correção:** StaticFiles em /api/v1/charts/ para servir HTML Plotly.
maestro_chat.py emite evento TOOL_CALL_RESULT após cada tool. Frontend
captura e renderiza iframe inline quando o tool é grafico_tecnico.

---

## Camada 2 — Temperamento (objetividade) ✅

System prompt ajustado com seção de estilo:
- Entrar direto no assunto, sem preâmbulos cerimoniais
- Não anunciar o que vai fazer — fazer e apresentar
- Respostas concisas
- PRESERVADO: honestidade intelectual (avisar quando falta dado,
  não fabricar, distinguir dado interno de externo)

Validado: o Maestro entra direto no dado, sem cerimônia.

---

## Camada 3 — Tools de escrita L2 ✅

Nível L2 com confirmação: Maestro propõe → mostra → usuário confirma
→ grava. Proibido gravar na mesma resposta da proposta.

Tools implementadas:
- **registrar_tese** → tabela teses
- **registrar_decisao_diario** → tabela diario_decisoes
- **atualizar_tese / invalidar_tese** → teses (status INVALIDADA)
- **criar_alerta** → tabela alertas (nova)
- **verificar_alertas** → avalia cada gatilho (RSI, preço, banda_IPS,
  invalidação) e marca disparado_em
- **listar_alertas** → lista cadastrados
- **forcar_coleta** → dispara coletas sob demanda

Migration: tabela `alertas` (id, tipo, ativo, condicao, valor_gatilho,
ativo_bool, disparado_em, criado_em).

**Página Alertas** criada no navbar para consulta visual dos gatilhos.

---

## Camada 4 — Web search ✅

**Tool: pesquisar_web**

**Histórico de implementação:**
1. DuckDuckGo primeiro (gratuito) — FALHOU: DuckDuckGo bloqueia
   requisições de IP de datacenter GCP (bot-detection)
2. Migrado para **Brave Search API** — plano free 2.000 buscas/mês

**Hierarquia de fontes (system prompt), 5 tiers:**
- TIER 1 — Dados/múltiplos: tradingview, investidor10, statusinvest, fundamentus
- TIER 2 — Research: genial, btg, nord, suno, kinea
- TIER 3 — Oficiais: b3, cvm, bcb, tesouro
- TIER 4 — Notícias: infomoney, valor, bloomberglinea
- TIER 5 — Internacional (BDRs): tradingview, yahoo finance, seekingalpha

**Disciplina:** sempre citar fonte; dado de web = contexto externo
não verificado; distinguir de dado interno (banco = fonte de verdade);
nunca apresentar blog/fórum como research.

Query direcionada: "TICKER informação site:fonte.com.br"

---

## Inventário de tools (~40 após polimento)

### Carteira e posições (4)
obter_posicoes, obter_performance, obter_brinson/obter_atribuicao

### Cotação e técnico (5)
obter_cotacao, obter_sinais, analise_tecnica, grafico_tecnico, obter_diario

### Fundamentos (4)
obter_fundamentos, consultar_fundamentos, analise_fundamentalista,
comparar_multiplos/screening_fundamentalista

### Carteira — estratégia (7)
analise_aderencia_setorial, risco_carteira, disciplina_caixa,
obter_analise_rv, obter_watchlist, regime_mercado, contexto_setorial

### Comportamental (3)
perfil_comportamental, divergencias_dito_feito, vieses_comportamentais

### Macro e eventos (3)
consultar_macro, consultar_eventos_corporativos, impacto_macro

### Teses e diário (5)
consultar_teses, consultar_diario_decisoes, registrar_tese (L2),
registrar_decisao_diario (L2), atualizar_tese/invalidar_tese (L2)

### Alertas (3)
criar_alerta (L2), listar_alertas, verificar_alertas

### Utilitários (4)
noticias_ativos, consultar_glossario, forcar_coleta, pesquisar_web

---

## Lacunas conhecidas (próximas frentes, não bloqueiam)

Identificadas em sessão de teste com ITUB3:

**Ingestão de dados (destrava 4 tools que vêm vazias):**
- Peers não populados → comparar_multiplos vira tabela de 1 coluna
- consultar_eventos_corporativos vazio sistematicamente
- noticias_ativos (yfinance .news) vazio → pesquisar_web mitiga
- contexto_setorial não resolve "Bancos" (taxonomia ou índice ausente)

**Design:**
- analise_fundamentalista aplica Dív/EBITDA a banco (métrica inaplicável)
  → deveria usar Basileia, inadimplência, eficiência para setor financeiro

**Desenvolvimento novo:**
- Série histórica de múltiplos (P/L, P/VP, DY ao longo do tempo)
  → permite z-score do múltiplo vs. própria história

Estas viram frentes próprias de polimento quando priorizadas.

---

*Última atualização: 28/06/2026*
