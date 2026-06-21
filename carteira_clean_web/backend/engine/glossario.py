"""
engine/glossario.py — Glossário de indicadores (referência do doc 07).

Dados estáticos que o maestro pode citar em resposta a perguntas
como 'o que é P/L?' ou 'o que é disposition effect?'.
"""
from __future__ import annotations

GLOSSARIO: dict[str, dict] = {
    # ── Fundamentalistas ──────────────────────────────────────────────────────
    "PL": {
        "nome":        "P/L (Preço/Lucro)",
        "categoria":   "fundamentalista",
        "subcategoria": "valuation",
        "o_que_e":     "Quantos anos de lucro atual o mercado paga pela ação. Preço ÷ Lucro por Ação.",
        "como_interpretar": "Baixo (< 10) pode indicar subvalorização ou problema; alto (> 25) pode indicar crescimento esperado ou sobrevalorização. Comparar com o setor e com o próprio histórico.",
    },
    "PVP": {
        "nome":        "P/VP (Preço/Valor Patrimonial)",
        "categoria":   "fundamentalista",
        "subcategoria": "valuation",
        "o_que_e":     "Quanto o mercado paga por cada R$1 de patrimônio líquido da empresa.",
        "como_interpretar": "P/VP < 1 sugere que o mercado avalia abaixo do patrimônio contábil. P/VP > 3 é comum em tech/crescimento. Útil para bancos e empresas intensivas em ativos.",
    },
    "EV_EBITDA": {
        "nome":        "EV/EBITDA",
        "categoria":   "fundamentalista",
        "subcategoria": "valuation",
        "o_que_e":     "Valor da empresa inteira (incluindo dívida) dividido pelo lucro operacional antes de juros, impostos, depreciação e amortização.",
        "como_interpretar": "Métrica mais limpa que P/L porque ignora estrutura de capital. EV/EBITDA < 6 costuma ser barato; > 15 caro. Comparar dentro do mesmo setor.",
    },
    "ROE": {
        "nome":        "ROE (Return on Equity)",
        "categoria":   "fundamentalista",
        "subcategoria": "rentabilidade",
        "o_que_e":     "Lucro líquido ÷ Patrimônio Líquido. Quanto a empresa gera de retorno sobre o capital dos acionistas.",
        "como_interpretar": "ROE > 15% é sinal de eficiência. ROE muito alto (> 40%) pode ser alavancagem, não eficiência — checar Dív.Líq/EBITDA junto.",
    },
    "ROIC": {
        "nome":        "ROIC (Return on Invested Capital)",
        "categoria":   "fundamentalista",
        "subcategoria": "rentabilidade",
        "o_que_e":     "Lucro operacional (NOPAT) ÷ Capital investido. Retorno sobre TODO o capital empregado (próprio + dívida).",
        "como_interpretar": "Mais completo que ROE porque inclui a dívida. ROIC > custo de capital (WACC) = empresa gera valor. ROIC < WACC = destrói valor.",
    },
    "MARGEM_EBITDA": {
        "nome":        "Margem EBITDA",
        "categoria":   "fundamentalista",
        "subcategoria": "rentabilidade",
        "o_que_e":     "EBITDA ÷ Receita Líquida. Quanto da receita sobra como lucro operacional.",
        "como_interpretar": "Mede eficiência operacional. Varia muito por setor (tech > 30%, varejo < 10%). Tendência importa mais que valor absoluto.",
    },
    "MARGEM_LIQUIDA": {
        "nome":        "Margem Líquida",
        "categoria":   "fundamentalista",
        "subcategoria": "rentabilidade",
        "o_que_e":     "Lucro Líquido ÷ Receita Líquida. Quanto da receita vira lucro de fato para o acionista.",
        "como_interpretar": "Inclui efeito de impostos e juros. Margem líquida caindo enquanto margem EBITDA está estável pode indicar aumento de dívida.",
    },
    "DIV_LIQ_EBITDA": {
        "nome":        "Dív.Líq/EBITDA",
        "categoria":   "fundamentalista",
        "subcategoria": "saude_financeira",
        "o_que_e":     "(Dívida bruta - Caixa) ÷ EBITDA. Quantos anos de lucro operacional para pagar a dívida líquida.",
        "como_interpretar": "< 1x: pouca dívida. 1-3x: saudável. > 3x: alavancagem elevada. > 5x: risco alto. Utilities podem operar com 3-4x pelo fluxo previsível.",
    },
    "DY": {
        "nome":        "DY (Dividend Yield)",
        "categoria":   "fundamentalista",
        "subcategoria": "proventos",
        "o_que_e":     "Dividendos pagos por ação nos últimos 12 meses ÷ Preço atual. Rendimento em dividendos.",
        "como_interpretar": "DY > 6% é atrativo para renda passiva, mas DY muito alto pode indicar queda no preço ou dividendo não sustentável. Verificar payout.",
    },
    "LPA": {
        "nome":        "LPA (Lucro por Ação)",
        "categoria":   "fundamentalista",
        "subcategoria": "proventos",
        "o_que_e":     "Lucro líquido ÷ Número de ações. Quanto cada ação 'ganhou'.",
        "como_interpretar": "Útil para comparar evolução do lucro ao longo do tempo. Crescimento consistente do LPA é sinal positivo.",
    },
    "VPA": {
        "nome":        "VPA (Valor Patrimonial por Ação)",
        "categoria":   "fundamentalista",
        "subcategoria": "proventos",
        "o_que_e":     "Patrimônio líquido ÷ Número de ações. Quanto de patrimônio cada ação representa.",
        "como_interpretar": "Base do cálculo do P/VP. VPA crescente indica que a empresa acumula patrimônio.",
    },
    # ── Técnicos ──────────────────────────────────────────────────────────────
    "MM20": {
        "nome":        "MM 20 (Média Móvel 20 dias)",
        "categoria":   "tecnico",
        "subcategoria": "medias_moveis",
        "o_que_e":     "Média dos preços de fechamento dos últimos 20 pregões. Tendência de curto prazo.",
        "como_interpretar": "Preço acima da MM20 = tendência de curto prazo em alta. Cruzamento abaixo = possível reversão.",
    },
    "MM50": {
        "nome":        "MM 50 (Média Móvel 50 dias)",
        "categoria":   "tecnico",
        "subcategoria": "medias_moveis",
        "o_que_e":     "Média de 50 pregões. Tendência de médio prazo.",
        "como_interpretar": "Cruzamento da MM20 acima da MM50 = 'golden cross' (sinal de alta). MM20 abaixo da MM50 = 'death cross' (sinal de baixa).",
    },
    "MM200": {
        "nome":        "MM 200 (Média Móvel 200 dias)",
        "categoria":   "tecnico",
        "subcategoria": "medias_moveis",
        "o_que_e":     "Média de 200 pregões. Tendência de longo prazo. Referência principal.",
        "como_interpretar": "Preço acima da MM200 = tendência primária de alta. Abaixo = tendência primária de baixa.",
    },
    "RSI": {
        "nome":        "RSI 14 (Índice de Força Relativa)",
        "categoria":   "tecnico",
        "subcategoria": "osciladores",
        "o_que_e":     "Mede a velocidade e magnitude dos movimentos de preço nos últimos 14 dias. Oscila entre 0 e 100.",
        "como_interpretar": "RSI > 70: sobrecomprado. RSI < 30: sobrevendido. Entre 30-70: zona neutra. Divergência (preço sobe mas RSI cai) é sinal de alerta.",
    },
    "MACD": {
        "nome":        "MACD (12, 26, 9)",
        "categoria":   "tecnico",
        "subcategoria": "osciladores",
        "o_que_e":     "Diferença entre duas EMAs (12 e 26 períodos), com linha de sinal (EMA de 9 do MACD).",
        "como_interpretar": "MACD cruzando acima da linha de sinal = momentum de alta. Histograma positivo = força compradora predomina.",
    },
    "BOLLINGER": {
        "nome":        "Bandas de Bollinger (20, 2)",
        "categoria":   "tecnico",
        "subcategoria": "osciladores",
        "o_que_e":     "Duas bandas a 2 desvios-padrão da MM20. Medem volatilidade.",
        "como_interpretar": "Preço tocando banda superior = esticado para cima. Inferior = esticado para baixo. Squeeze (bandas estreitando) = volatilidade comprimida, explosão iminente.",
    },
    "SUPORTE": {
        "nome":        "Suporte",
        "categoria":   "tecnico",
        "subcategoria": "suporte_resistencia",
        "o_que_e":     "Nível de preço onde historicamente compradores entram e o preço para de cair.",
        "como_interpretar": "Bom ponto de entrada com confirmação de outros indicadores. Se perdido, vira resistência — sinal de fraqueza.",
    },
    "RESISTENCIA": {
        "nome":        "Resistência",
        "categoria":   "tecnico",
        "subcategoria": "suporte_resistencia",
        "o_que_e":     "Nível de preço onde historicamente vendedores entram e o preço para de subir.",
        "como_interpretar": "Alvo natural para quem está comprado. Se rompida, vira suporte — sinal de força.",
    },
    "RATING_TECNICO": {
        "nome":        "Rating Técnico (-1 a +1)",
        "categoria":   "tecnico",
        "subcategoria": "sistema_votacao",
        "o_que_e":     "Média dos votos de todos os indicadores. Cada um vota -1 (venda), 0 (neutro) ou +1 (compra).",
        "como_interpretar": "Rating > +0.5: confluência forte de compra. < -0.5: confluência forte de venda. Próximo de 0: sinais mistos. Não é 'compre/venda' — é 'quantos indicadores concordam'.",
    },
    # ── Comportamentais ───────────────────────────────────────────────────────
    "efeito_disposicao": {
        "nome":        "Efeito Disposição (Disposition Effect)",
        "categoria":   "comportamental",
        "subcategoria": "vieses",
        "o_que_e":     "Tendência de vender posições ganhadoras cedo demais e segurar posições perdedoras tempo demais. É o viés mais estudado e custoso em finanças comportamentais.",
        "como_interpretar": "Se o ratio holding_perda/holding_ganho for > 2x, você está segurando perdedores muito mais tempo que ganhadores. Pergunte-se: 'se essa posição não tivesse prejuízo, eu ainda estaria nela?'",
    },
    "overtrading": {
        "nome":        "Overtrading (Giro Excessivo)",
        "categoria":   "comportamental",
        "subcategoria": "vieses",
        "o_que_e":     "Operar com frequência excessiva em relação ao horizonte declarado. Giro alto corrói retorno via custos e impostos.",
        "como_interpretar": "Turnover > 50% em blocos de horizonte longo (Growth, Defensivos) é inconsistente com a tese. Swing Trade pode ter turnover alto — é esperado. O contexto do bloco importa.",
    },
    "subdiversificacao": {
        "nome":        "Sub-diversificação",
        "categoria":   "comportamental",
        "subcategoria": "vieses",
        "o_que_e":     "Concentrar patrimônio em poucos ativos, aumentando risco específico sem necessidade.",
        "como_interpretar": "HHI > 15: concentrado. Top-1 > 25% do patrimônio: risco alto de ativo individual. Diversificação não exige 50 ativos — mas 1 ativo com 25% é risco evitável.",
    },
    "clustering_temporal": {
        "nome":        "Clustering Temporal",
        "categoria":   "comportamental",
        "subcategoria": "vieses",
        "o_que_e":     "Agrupar muitas operações em curto período, frequentemente por impulso ou reação emocional a notícias/movimentos de mercado.",
        "como_interpretar": "Meses com operações muito acima da média merecem revisão: houve evento macro que justificou, ou foi reação emocional? O diário de decisão ajuda a distinguir.",
    },
    "trend_chasing": {
        "nome":        "Trend Chasing (Seguir Tendência Tardiamente)",
        "categoria":   "comportamental",
        "subcategoria": "vieses",
        "o_que_e":     "Comprar após altas recentes (seguindo a tendência) e obter retornos ruins no período seguinte. Entrar quando o 'trem já passou'.",
        "como_interpretar": "Se consistentemente compra ativos que subiram >10% no mês anterior e o retorno pós-compra é negativo, indica entrada tardia. O padrão sistemático é o sinal — não toda compra em alta é errada.",
    },
}


def consultar(termo: str) -> dict | None:
    """Busca no glossário por chave exata ou por substring do nome/categoria."""
    termo_lower = termo.lower().replace(" ", "_").replace("/", "_")
    # Chave exata
    if termo_lower in GLOSSARIO:
        return GLOSSARIO[termo_lower]
    # Busca parcial
    for chave, entrada in GLOSSARIO.items():
        if (termo_lower in chave or
                termo_lower in entrada["nome"].lower() or
                termo_lower in entrada.get("subcategoria", "").lower()):
            return entrada
    return None


def listar_por_categoria(categoria: str | None = None) -> list[dict]:
    if categoria is None:
        return list(GLOSSARIO.values())
    return [e for e in GLOSSARIO.values() if e["categoria"] == categoria.lower()]
