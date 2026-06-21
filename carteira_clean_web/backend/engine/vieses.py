"""
engine/vieses.py — Vieses comportamentais nomeados (Fatia 8b).

Detecta 5 vieses a partir do event log + cotações.
Apresenta fatos mensuráveis e nomeia o padrão — sem prescrever ação.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, stdev
from typing import Any


def _vies(nome: str, desc_curta: str, fato: str, detectado: bool,
          severidade: str, ref: str) -> dict:
    return {
        "nome_vies": nome,
        "descricao_curta": desc_curta,
        "fato_mensuravel": fato,
        "detectado": detectado,
        "severidade": severidade,
        "referencia_glossario": ref,
    }


def calcular_disposition_effect(
    eventos: list[dict],
    cotacoes_historico: dict[str, dict[str, float]],
) -> dict:
    """
    Efeito disposição: holding period de vendas com lucro vs. com prejuízo.
    Usa preço médio de compra calculado por FIFO vs. preço de venda registrado.
    """
    compras: dict[str, list[tuple[date, float, float]]] = defaultdict(list)  # (data, qtd, preco)
    resultados_ganho: list[float] = []
    resultados_perda: list[float] = []

    for ev in sorted(eventos, key=lambda x: x["data"]):
        ativo = ev.get("ativo", "")
        tipo = ev.get("tipo", "")
        d = ev["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        qtd = abs(ev.get("qtd") or 0.0)
        preco = ev.get("preco") or 0.0

        if tipo == "COMPRA" and qtd > 0 and preco > 0:
            compras[ativo].append((d, qtd, preco))
        elif tipo == "VENDA" and qtd > 0 and preco > 0:
            fila = compras.get(ativo, [])
            qtd_restante = qtd
            custo_total = 0.0
            dias_total = 0.0
            qtd_pareada = 0.0
            while qtd_restante > 1e-9 and fila:
                d_compra, q_compra, p_compra = fila[0]
                usar = min(qtd_restante, q_compra)
                custo_total += usar * p_compra
                dias_total += usar * (d - d_compra).days
                qtd_pareada += usar
                qtd_restante -= usar
                if usar >= q_compra - 1e-9:
                    fila.pop(0)
                else:
                    fila[0] = (d_compra, q_compra - usar, p_compra)
            if qtd_pareada > 1e-9:
                preco_medio_compra = custo_total / qtd_pareada
                holding_medio = dias_total / qtd_pareada
                lucro = preco > preco_medio_compra
                if lucro:
                    resultados_ganho.append(holding_medio)
                else:
                    resultados_perda.append(holding_medio)

    if not resultados_ganho and not resultados_perda:
        return _vies(
            "Efeito Disposição",
            "Vender ganhadores cedo e segurar perdedores.",
            "Sem posições encerradas suficientes para calcular.",
            False, "INFO",
            "glossario:efeito_disposicao",
        )

    med_ganho = mean(resultados_ganho) if resultados_ganho else None
    med_perda = mean(resultados_perda) if resultados_perda else None

    if med_ganho and med_perda:
        ratio = med_perda / med_ganho
        detectado = ratio > 2.0
        sev = "CRITICO" if ratio > 3.0 else "ATENCAO" if detectado else "INFO"
        fato = (f"Vendas com lucro: holding médio {int(med_ganho)} dias "
                f"({len(resultados_ganho)} ops). "
                f"Vendas com prejuízo: holding médio {int(med_perda)} dias "
                f"({len(resultados_perda)} ops). "
                f"Ratio perda/ganho: {ratio:.1f}x.")
    elif med_ganho:
        detectado = False
        sev = "INFO"
        fato = f"Apenas vendas com lucro ({len(resultados_ganho)} ops), holding médio {int(med_ganho)} dias. Sem vendas com prejuízo no período."
    else:
        detectado = False
        sev = "INFO"
        fato = f"Apenas vendas com prejuízo ({len(resultados_perda)} ops), holding médio {int(med_perda)} dias. Sem vendas com lucro no período."

    return _vies(
        "Efeito Disposição",
        "Vender ganhadores cedo demais e segurar perdedores tempo demais.",
        fato, detectado, sev, "glossario:efeito_disposicao",
    )


def calcular_overtrading(turnover_por_bloco: dict) -> dict:
    """Reutiliza dados de turnover da Fatia 8. Formaliza como viés nomeado."""
    blocos_longos = ("GROWTH", "DEFENSIVOS")
    violacoes = [
        (b, d["turnover_pct"])
        for b, d in turnover_por_bloco.items()
        if b in blocos_longos and d.get("turnover_pct") is not None and d["turnover_pct"] > 50
    ]
    detectado = bool(violacoes)
    if violacoes:
        desc_v = "; ".join(f"{b}: {p:.1f}%" for b, p in violacoes)
        fato = (f"Turnover em blocos de horizonte longo acima de 50%: {desc_v}. "
                f"Inconsistente com horizonte multi-ano declarado na IPS.")
        sev = "CRITICO" if any(p > 100 for _, p in violacoes) else "ATENCAO"
    else:
        partes = [f"{b}: {d.get('turnover_pct', 0) or 0:.1f}%" for b, d in turnover_por_bloco.items()]
        fato = "Turnover dentro do esperado por bloco. " + "; ".join(partes)
        sev = "INFO"
    return _vies(
        "Overtrading",
        "Giro excessivo em relação ao horizonte declarado na IPS.",
        fato, detectado, sev, "glossario:overtrading",
    )


def calcular_subdiversificacao(concentracao: dict) -> dict:
    """Reutiliza dados de concentração da Fatia 8."""
    hhi = concentracao.get("hhi", 0.0)
    top5 = concentracao.get("top5", [])
    top1_peso = top5[0]["peso_pct"] if top5 else 0.0
    detectado = hhi > 15 or top1_peso > 25
    sev = "CRITICO" if hhi > 20 or top1_peso > 30 else "ATENCAO" if detectado else "INFO"
    top5_str = ", ".join(f"{t['ticker']} {t['peso_pct']}%" for t in top5[:3])
    fato = (f"HHI: {hhi:.1f} ({concentracao.get('hhi_nivel', '?')}). "
            f"Top-1: {top1_peso:.1f}%. Top-3: {top5_str}.")
    return _vies(
        "Sub-diversificação",
        "Concentração excessiva em poucos ativos aumenta risco específico.",
        fato, detectado, sev, "glossario:subdiversificacao",
    )


def calcular_clustering_temporal(frequencia: dict) -> dict:
    """Reutiliza dados de frequência da Fatia 8."""
    picos = frequencia.get("picos", [])
    media = frequencia.get("media_mensal") or 0.0
    dp = frequencia.get("desvio_padrao") or 0.0
    tendencia = frequencia.get("tendencia", "estavel")
    detectado = bool(picos) or tendencia == "acelerando"
    sev = "ATENCAO" if detectado else "INFO"
    if picos:
        por_mes = frequencia.get("por_mes", {})
        desc_picos = ", ".join(f"{m}: {por_mes.get(m, '?')} ops" for m in picos)
        fato = (f"Picos de operações > 2σ da média detectados: {desc_picos}. "
                f"Média mensal: {media:.1f} ops (σ={dp:.1f}). Tendência: {tendencia}.")
    else:
        fato = (f"Sem picos acima de 2σ. Média: {media:.1f} ops/mês (σ={dp:.1f}). "
                f"Tendência: {tendencia}.")
    return _vies(
        "Clustering Temporal",
        "Agrupamento de operações em períodos curtos, possivelmente por impulso.",
        fato, detectado, sev, "glossario:clustering_temporal",
    )


def calcular_trend_chasing(
    eventos: list[dict],
    cotacoes_historico: dict[str, dict],
    periodo_ini: date,
    periodo_fim: date,
) -> dict:
    """
    Trend chasing: retorno do ativo 30d antes da compra vs. 30d depois.
    cotacoes_historico: {ticker: {date_str: preco}}
    """
    from datetime import timedelta

    retornos_pre: list[float] = []
    retornos_pos: list[float] = []
    n_sem_dados = 0

    for ev in eventos:
        if ev.get("tipo") != "COMPRA":
            continue
        d = ev["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        if not (periodo_ini <= d <= periodo_fim):
            continue
        ativo = ev.get("ativo", "")
        preco_compra = ev.get("preco") or 0.0
        if preco_compra <= 0:
            continue

        hist = cotacoes_historico.get(ativo, {})
        if not hist:
            n_sem_dados += 1
            continue

        # Buscar preço mais próximo -30 dias e +30 dias
        d_antes = d - timedelta(days=30)
        d_depois = d + timedelta(days=30)

        def preco_proximo(alvo: date) -> float | None:
            for delta in range(0, 10):
                for sinal in (0, -1, 1, -2, 2):
                    chave = str(alvo + timedelta(days=delta * sinal if sinal else 0))
                    if chave in hist:
                        return hist[chave]
            return None

        p_antes = preco_proximo(d_antes)
        p_depois = preco_proximo(d_depois)

        if p_antes and preco_compra > 0:
            retornos_pre.append((preco_compra / p_antes - 1) * 100)
        if p_depois and preco_compra > 0:
            retornos_pos.append((p_depois / preco_compra - 1) * 100)

    n_compras = len(retornos_pre)
    if n_compras < 3:
        fato = (f"Dados insuficientes para calcular trend chasing "
                f"({n_compras} compras com cotações, {n_sem_dados} sem histórico).")
        return _vies(
            "Trend Chasing",
            "Comprar após altas recentes, obtendo retorno ruim depois.",
            fato, False, "INFO", "glossario:trend_chasing",
        )

    med_pre = mean(retornos_pre)
    med_pos = mean(retornos_pos) if retornos_pos else None

    detectado = med_pre > 5.0 and (med_pos is not None and med_pos < 0)
    sev = "ATENCAO" if detectado else "INFO"
    pos_str = f"{med_pos:+.1f}%" if med_pos is not None else "n/d"
    fato = (f"Retorno médio 30d antes das compras: {med_pre:+.1f}% "
            f"({n_compras} compras). "
            f"Retorno médio 30d após: {pos_str}.")
    if detectado:
        fato += " Padrão consistente com entrada tardia em tendência."

    return _vies(
        "Trend Chasing",
        "Comprar após altas recentes e obter retorno ruim nos 30 dias seguintes.",
        fato, detectado, sev, "glossario:trend_chasing",
    )
