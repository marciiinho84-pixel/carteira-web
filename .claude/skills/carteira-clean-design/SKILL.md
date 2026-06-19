---
name: carteira-clean-design
description: |
  Sistema de design para o projeto Carteira Clean.
  ATIVAR ao criar ou modificar qualquer interface visual:
  páginas Streamlit, gráficos Plotly, tabelas, cards de
  métricas, dashboards. Palavras-chave que ativam esta
  skill: Dashboard, Carteira RV, Posições, Evolução,
  gráfico, tabela, cor, estilo, layout, design, visual.
  Esta skill define paleta de cores TradingView-inspired,
  formatação monetária brasileira, configuração Plotly e
  padrões de componentes específicos da ferramenta.
---

# Carteira Clean — Design System

## Filosofia
Inspirado no TradingView: dados em primeiro plano,
interface mínima ao redor. Sofisticação e confiança —
ferramenta de alguém que leva finanças a sério.
Densidade alta, mas organizada. Cada elemento tem função.

## Paleta de Cores

```python
# Backgrounds
BG_PRIMARY   = "#0F1117"  # fundo principal
BG_SECONDARY = "#1C2333"  # cards e superfícies
BG_TERTIARY  = "#252D3D"  # bordas internas

# Dados financeiros (NUNCA saturados)
COLOR_POSITIVE = "#26A69A"  # verde teal (TradingView)
COLOR_NEGATIVE = "#EF5350"  # vermelho suave (TradingView)
COLOR_NEUTRAL  = "#6366F1"  # índigo para neutros
COLOR_ALERT    = "#F59E0B"  # âmbar para alertas
COLOR_INFO     = "#3B82F6"  # azul para informações

# Texto
TEXT_PRIMARY   = "#D1D4DC"  # texto principal
TEXT_SECONDARY = "#787B86"  # labels e legendas
TEXT_MUTED     = "#4B5563"  # texto atenuado
```

## Formatação Numérica — OBRIGATÓRIA

Sempre usar estas funções. NUNCA exibir números brutos.

```python
def fmt_brl(v: float) -> str:
    """R$ 1.234.567,89"""
    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

def fmt_pct(v: float, sign=True) -> str:
    """+43,32% ou -4,21%"""
    s = "+" if v > 0 and sign else ""
    return f"{s}{v:.2f}%".replace(".", ",")

def fmt_pct_html(v: float) -> str:
    """Com cor automática para uso em markdown/HTML"""
    cor = "#26A69A" if v >= 0 else "#EF5350"
    s = "+" if v > 0 else ""
    return f'<span style="color:{cor};font-weight:600">{s}{v:.2f}%</span>'.replace(".", ",")

def fmt_k(v: float) -> str:
    """1,4M ou 142,3k para espaços pequenos"""
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M".replace(".", ",")
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}k".replace(".", ",")
    return fmt_brl(v)
```

## CSS Global (injetar no topo de cada página)

```python
CSS_GLOBAL = """
<style>
.main .block-container { padding-top: 1rem; max-width: 1200px; }

[data-testid="metric-container"] {
    background: #1C2333;
    border: 1px solid #252D3D;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="metric-container"] label {
    color: #787B86 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="metric-container"] [data-testid="metric-value"] {
    color: #D1D4DC !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.85rem;
    font-weight: 500;
    color: #787B86;
}
.stTabs [aria-selected="true"] { color: #6366F1; }

div[data-testid="stExpander"] {
    border: 1px solid #252D3D;
    border-radius: 8px;
}
</style>
"""
```

## Configuração Padrão Plotly

```python
def plotly_layout(**kwargs) -> dict:
    """Layout base para todos os gráficos"""
    base = dict(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#0F1117",
        font=dict(family="Inter,system-ui,sans-serif",
                  color="#D1D4DC", size=12),
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(bgcolor="rgba(28,35,51,0.8)",
                    bordercolor="#252D3D", borderwidth=1),
        xaxis=dict(gridcolor="#1C2333", linecolor="#252D3D",
                   tickfont=dict(color="#787B86")),
        yaxis=dict(gridcolor="#1C2333", linecolor="#252D3D",
                   tickfont=dict(color="#787B86")),
        hoverlabel=dict(bgcolor="#1C2333", bordercolor="#252D3D",
                        font_color="#D1D4DC"),
    )
    base.update(kwargs)
    return base

# Sequência de cores para séries múltiplas
CORES_SERIES = ["#6366F1", "#26A69A", "#F59E0B", "#EF5350",
                "#8B5CF6", "#3B82F6", "#EC4899"]

# Gráfico de linha de performance (TWR vs benchmarks)
# - Positivo acima de zero: preencher com #26A69A opacity 0.1
# - Linha principal: #6366F1 (índigo)
# - CDI: #787B86 (cinza, linha tracejada)
# - IBOV: #F59E0B (âmbar)
```

## Hierarquia Visual no Dashboard

NÍVEL 1 — Métricas Hero (tamanho grande, topo)
Patrimônio Total | TWR YTD | vs CDI
NÍVEL 2 — Gráfico Central (ocupa 60-70% da largura)
Evolução do patrimônio OU performance vs benchmarks
NÍVEL 3 — Métricas secundárias (colunas menores)
Alocação | Drawdown | Caixa disponível
NÍVEL 4 — Tabelas e detalhes (parte inferior)
Alertas | Últimos eventos

## Anti-padrões — NUNCA fazer

❌ Verde #00FF00 ou vermelho #FF0000 — sempre usar as cores definidas
❌ Números sem formatação brasileira
❌ Gráfico Plotly sem configurar template e paper_bgcolor
❌ st.write() para exibir dados financeiros
❌ Mais de 4 cores diferentes no mesmo gráfico
❌ Tabelas sem largura proporcional às colunas
❌ Misturar unidades (% e R$ na mesma coluna sem separação)
❌ Fundo branco em qualquer componente principal
❌ st.metric() sem o CSS_GLOBAL injetado antes
