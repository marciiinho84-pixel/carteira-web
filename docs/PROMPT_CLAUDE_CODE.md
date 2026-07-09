# Prompt para Claude Code — Redesign "Papel & Tinta"

Cole o texto abaixo no Claude Code, rodando dentro do repo `carteira-web`.

---

## PROMPT

Implemente o redesign visual "Papel & Tinta" no app Next.js deste repositório, substituindo a paleta TradingView atual (`#0F1117` / `#26A69A` / `#EF5350`) em **todas as páginas** por um sistema de papel quente com tinta terracota. Este é um **restyle completo**, não uma reescrita: mantenha 100% da lógica existente (fetch de dados, state, rotas, hooks, componentes de formulário funcionais) e troque apenas classes/estilos visuais.

### 1. Setup de fontes

Em `web/src/app/layout.tsx`, adicione ao lado do import de fonte atual:
- **Source Serif 4** (pesos 400, 600, 700) — para títulos e valores-hero (patrimônio, KPIs grandes)
- **IBM Plex Mono** (pesos 400, 500, 600) — para TODO número: preços, %, tabelas, valores monetários
- Mantenha **Inter** (ou a sans atual) para labels, nav, corpo de texto

Use `next/font/google` como já deve estar configurado para a fonte atual.

### 2. Design tokens

Crie/atualize as variáveis de cor (Tailwind config ou CSS vars em `globals.css`) com esta paleta:

```
--bg-app: #F4EEE2        (fundo geral da página)
--bg-card: #FBF6EC       (cards, painéis)
--bg-card-alt: #EFE7D8   (sidebar, inputs, hover)
--border: #DDD2BF        (bordas de card)
--border-soft: #E5DBC8   (divisores internos)
--text-primary: #2E2921  (títulos, valores)
--text-body: #3D3629     (corpo)
--text-muted: #7A7160    (labels, secundário)
--text-faint: #A69C88    (timestamps, placeholders)
--accent: #C15F3C        (terracota — cor de ação/destaque, nav ativo, CTAs)
--accent-strong: #A64E2E (texto sobre fundo accent claro)
--positive: #4A7C59      (verde-oliva — ganhos, "OK")
--negative: #B4442C      (perdas, crítico)
--warning: #C9862B       (atenção)
--purple-accent: #6C63C4 (ações secundárias específicas, ex: botão "Nova Tese")
```

Substitua todas as ocorrências de `#0F1117`, `#1A1D27`, `#2A2D3A`, `#6b7280`, `#D1D4DC`, `#26A69A`, `#EF5350`, `#F59E0B`, `#6366F1` pelos tokens equivalentes acima em cada arquivo de página.

### 3. Textura de papel (componente compartilhado)

Crie um componente `<PaperTexture />` em `web/src/components/PaperTexture.tsx` que renderiza 3 camadas absolutas (pointer-events: none, z-index acima do conteúdo mas abaixo de modais):
1. Grão fino: SVG `feTurbulence` (`type="fractalNoise"`, `baseFrequency="0.65"`, `numOctaves="3"`) colorizado para `rgba(61,54,41,0.16)` no modo claro
2. Fibras: SVG `feTurbulence` (`type="turbulence"`, `baseFrequency="0.012 0.28"`, `numOctaves="2"`) em opacidade 0.5, mesma cor
3. Vinheta de luz: `radial-gradient(ellipse 120% 90% at 38% 18%, rgba(255,252,240,0.28) 0%, rgba(255,252,240,0) 45%, rgba(93,80,58,0.10) 100%)`

Monte esse componente uma vez no layout raiz (`web/src/app/layout.tsx`) para cobrir toda a área de conteúdo — não repita por página.

### 4. Sidebar (`web/src/components/Nav.tsx`)

- Fundo `--bg-card-alt`, borda direita `--border`
- Largura fixa 216px
- Logo: quadrado 28px, radius 8px, fundo `--accent`, "C" em Source Serif 4 bold, cor `--bg-card`
- Itens de nav: ícones de linha SVG (stroke, não fill) substituindo qualquer emoji — 16×16px, stroke-width 1.5
- Item ativo: fundo `rgba(193,95,60,0.12)`, texto `--accent-strong`, weight 600
- Item inativo: texto `--text-muted`, weight 500
- Rodapé da sidebar: email do usuário + "sair", `--text-faint`, 11px

### 5. Padrão de card

Todo container que hoje é `bg-[#1A1D27] border border-[#2A2D3A] rounded-xl` vira:
`background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 1px 3px rgba(61,54,41,0.06);`

### 6. Regra de tipografia por elemento

- Valores monetários grandes (patrimônio total, hero numbers) → Source Serif 4, peso 600-700
- Qualquer número (preço, %, R$, tabelas) → IBM Plex Mono
- Títulos de seção/h1/h2 → Source Serif 4
- Texto corrido, labels, badges → Inter/sans atual

### 7. Páginas a atualizar (mesma lógica, novo visual)

Aplique os tokens e o padrão de card acima em:
- `web/src/app/dashboard/page.tsx` — hero de patrimônio em serifa + 3 KPI cards à direita + gráfico de performance + alocação IPS + métricas secundárias em linha única (sem cards aninhados) + lista de alertas
- `web/src/app/posicoes/page.tsx` — pills de filtro por bloco (`white-space: nowrap` obrigatório), tabela com badge vermelho quando P&L < -15%
- `web/src/app/sala-de-comando/page.tsx` — header com KPIs, grid 2/3+1/3 (Orquestra + Teses Ativas), grid 1/2+1/2 (Espelho Comportamental com círculo de coerência SVG + Meta R$3M com progress bar gradiente terracota)
- `web/src/app/renda-variavel/page.tsx` — KPIs de performance, tabela de caixa/liquidações, barras de distribuição setorial, sinais ativos, watchlist
- `web/src/app/maestro/page.tsx` — sidebar de conversas própria (não a Nav principal), bolhas de chat (assistente = fundo `--bg-card` + avatar terracota "M"; usuário = fundo `rgba(193,95,60,0.12)` + avatar roxo "V"), indicador de tool-call
- `web/src/app/evolucao/page.tsx` — pills de filtro de período, gráfico de área terracota, tabela mensal com accordion
- `web/src/app/meta/page.tsx` — progress bar gradiente, sliders de TWR/aporte extra com thumb terracota, gráfico de projeção
- `web/src/app/teses/page.tsx` — cards agrupados por semáforo (vermelho/amarelo/verde), badges com `white-space: nowrap`
- `web/src/app/alertas/page.tsx` — lista de gatilhos com badge de tipo colorido, estado pausado em opacidade 0.55
- `web/src/app/risco/page.tsx` — círculo/barra de HHI, tabela de exposição por bloco, top 5 ativos com mini barra de peso

Não altere: `web/src/app/configuracoes/page.tsx`, `web/src/app/login/page.tsx`, `web/src/app/novo-evento/page.tsx` — deixe para uma segunda passada (pedirei explicitamente).

### 8. QA obrigatório antes de finalizar

- Nenhum badge, pill ou label de uma palavra composta (ex: "Swing Trade", "Fora IPS", "Últimos 20") pode quebrar linha — adicione `white-space: nowrap` em todo badge/pill.
- Rode `npm run build` e corrija qualquer erro de tipo/lint introduzido pela troca de classes.
- Confira visualmente (screenshot ou preview local) as 10 páginas listadas acima antes de considerar concluído.

---

## Referência visual
As 10 telas de referência (mockups HTML fiéis, com os dados de exemplo) estão no arquivo anexo `Dashboard Redesign.dc.html` deste handoff — abra no navegador para ver cada tela pelo id da âncora (#3a Posições, #3b Sala de Comando, #3c Renda Variável, #3d Maestro, #3e Evolução, #3f Meta, #3g Teses, #3h Alertas, #3i Risco, #3j Novo Evento) e a variante #2a para o Dashboard.
