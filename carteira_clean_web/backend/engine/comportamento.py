"""
engine/comportamento.py — Inferência comportamental sobre o event log (Fatia 8).

Lê o histórico de eventos e calcula padrões de comportamento do investidor:
turnover real, holding period, frequência de operações e concentração.
Não interpreta — apenas computa. A interpretação é do maestro/Fatia 9.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, stdev

from carteira_clean_web.backend.engine.aderencia_ips import _BLOCO_MAP

# Horizonte declarado por bloco IPS (em dias) — fonte: IPS v1.0
_HORIZONTE_BLOCO: dict[str, dict] = {
    "SWING_TRADE": {"label": "semanas a meses",   "min": 7,   "max": 180},
    "GROWTH":      {"label": "multi-ano",          "min": 365, "max": None},
    "DEFENSIVOS":  {"label": "médio-longo prazo",  "min": 180, "max": None},
    "RENDA_FIXA":  {"label": "até vencimento",     "min": 0,   "max": None},
}


def calcular_turnover(
    eventos: list[dict],
    valor_por_bloco: dict[str, float],
    periodo_ini: date,
    periodo_fim: date,
) -> dict[str, dict]:
    """
    Turnover por bloco IPS = valor vendas no período / patrimônio atual do bloco.

    Args:
        eventos:         list de dicts com campos data, ativo, tipo, valor
        valor_por_bloco: {bloco: valor_atual_rs} — snapshot das posições atuais
        periodo_ini/fim: janela de análise
    """
    vendas_bloco: dict[str, float] = defaultdict(float)
    for ev in eventos:
        if ev.get("tipo") != "VENDA":
            continue
        d = ev["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if not (periodo_ini <= d <= periodo_fim):
            continue
        bloco = _BLOCO_MAP.get(ev.get("ativo", ""), "FORA_IPS")
        vendas_bloco[bloco] += abs(ev.get("valor", 0.0))

    resultado: dict[str, dict] = {}
    todos_blocos = set(list(vendas_bloco) + list(valor_por_bloco))
    for bloco in todos_blocos:
        if bloco == "FORA_IPS":
            continue
        vendas = vendas_bloco.get(bloco, 0.0)
        pat = valor_por_bloco.get(bloco, 0.0)
        turnover = (vendas / pat) if pat > 0 else None
        resultado[bloco] = {
            "valor_vendas_rs": round(vendas, 2),
            "patrimonio_bloco_rs": round(pat, 2),
            "turnover_pct": round(turnover * 100, 1) if turnover is not None else None,
            "periodo": f"{periodo_ini} a {periodo_fim}",
        }
    return resultado


def calcular_holding_period(
    eventos: list[dict],
    hoje: date,
) -> dict[str, dict]:
    """
    Holding period médio por bloco IPS.
    Posições encerradas: data_venda − data_compra (FIFO).
    Posições abertas: hoje − data_compra.
    """
    compras: dict[str, list[date]] = defaultdict(list)
    vendas: dict[str, list[date]] = defaultdict(list)

    for ev in eventos:
        ativo = ev.get("ativo", "")
        tipo = ev.get("tipo", "")
        d = ev["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if tipo == "COMPRA":
            compras[ativo].append(d)
        elif tipo == "VENDA":
            vendas[ativo].append(d)

    abertos: dict[str, list[int]] = defaultdict(list)
    encerrados: dict[str, list[int]] = defaultdict(list)

    for ativo in compras:
        bloco = _BLOCO_MAP.get(ativo, "FORA_IPS")
        if bloco == "FORA_IPS":
            continue
        vendas_ord = sorted(vendas.get(ativo, []))
        for comp in sorted(compras[ativo]):
            matched = next((v for v in vendas_ord if v >= comp), None)
            if matched:
                vendas_ord.remove(matched)
                encerrados[bloco].append((matched - comp).days)
            else:
                abertos[bloco].append((hoje - comp).days)

    resultado: dict[str, dict] = {}
    for bloco in set(list(abertos) + list(encerrados)):
        ab = abertos.get(bloco, [])
        enc = encerrados.get(bloco, [])
        todos = ab + enc
        h = _HORIZONTE_BLOCO.get(bloco, {})
        resultado[bloco] = {
            "media_dias": round(mean(todos), 0) if todos else None,
            "media_abertos_dias": round(mean(ab), 0) if ab else None,
            "media_encerrados_dias": round(mean(enc), 0) if enc else None,
            "n_abertas": len(ab),
            "n_encerradas": len(enc),
            "horizonte_declarado": h.get("label"),
            "horizonte_min_dias": h.get("min"),
            "horizonte_max_dias": h.get("max"),
        }
    return resultado


def calcular_frequencia(
    eventos: list[dict],
    periodo_ini: date,
    periodo_fim: date,
) -> dict:
    """
    Frequência mensal de operações (COMPRA + VENDA) na janela dada.
    Detecta tendência e picos (> média + 2σ).
    """
    ops_mes: dict[str, int] = defaultdict(int)
    for ev in eventos:
        if ev.get("tipo") not in ("COMPRA", "VENDA"):
            continue
        d = ev["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if not (periodo_ini <= d <= periodo_fim):
            continue
        ops_mes[f"{d.year}-{d.month:02d}"] += 1

    if not ops_mes:
        return {"por_mes": {}, "media_mensal": None, "picos": [], "tendencia": "sem dados"}

    vals = list(ops_mes.values())
    media = mean(vals)
    dp = stdev(vals) if len(vals) > 1 else 0.0
    limiar = media + 2 * dp
    picos = [m for m, c in ops_mes.items() if c > limiar]

    meses_ord = sorted(ops_mes)
    if len(meses_ord) >= 6:
        rec = mean([ops_mes[m] for m in meses_ord[-3:]])
        ant = mean([ops_mes[m] for m in meses_ord[-6:-3]])
        if rec > ant * 1.2:
            tendencia = "acelerando"
        elif rec < ant * 0.8:
            tendencia = "desacelerando"
        else:
            tendencia = "estavel"
    else:
        tendencia = "insuficiente"

    return {
        "por_mes": dict(sorted(ops_mes.items())),
        "media_mensal": round(media, 1),
        "desvio_padrao": round(dp, 1),
        "limiar_pico": round(limiar, 1),
        "picos": picos,
        "tendencia": tendencia,
        "total_operacoes": sum(vals),
    }


def calcular_concentracao(
    valor_por_ticker: dict[str, float],
    composite_por_ticker: dict[str, str],
) -> dict:
    """
    Concentração individual na Carteira Gerida.
    Retorna top-5 posições e HHI simplificado (soma dos quadrados dos pesos × 100).
    HHI < 5 = baixo / 5–10 = médio / >10 = alto.
    """
    gerida = {
        t: v for t, v in valor_por_ticker.items()
        if composite_por_ticker.get(t) == "Gerida" and v > 0
    }
    patrimônio = sum(gerida.values())
    if patrimônio <= 0:
        return {}

    pesos = {t: v / patrimônio for t, v in gerida.items()}
    top5 = sorted(pesos.items(), key=lambda x: -x[1])[:5]
    hhi = round(sum(w ** 2 for w in pesos.values()) * 100, 2)

    return {
        "top5": [{"ticker": t, "peso_pct": round(w * 100, 1)} for t, w in top5],
        "hhi": hhi,
        "hhi_nivel": "baixo" if hhi < 5 else "medio" if hhi < 10 else "alto",
        "patrimonio_gerida_rs": round(patrimônio, 2),
        "n_ativos": len(gerida),
    }
