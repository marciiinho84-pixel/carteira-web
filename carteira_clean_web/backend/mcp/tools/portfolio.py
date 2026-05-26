"""
MCP Tools: obter_posicoes, obter_performance

Lêem do cache em memória (sem recalcular).
"""

from datetime import timedelta

import pandas as pd
from collections import defaultdict

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO
from carteira_clean_web.backend.engine.utils import preco_em
from carteira_clean_web.backend.mcp.schemas import (
    PorClasse, Resumo, Posicao, ResultadoPosicoes,
    RetornoBenchmark, Risco, ResultadoPerformance,
)


def fn_obter_posicoes() -> dict:
    """Retorna todas as posições ativas com P&L e alertas."""
    # MCP server roda em processo separado — tentar carregar do disco se memória vazia
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()

    if not engine_cache.esta_calculado():
        return {
            "erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."
        }

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    patrimonio_total = 0.0
    patrimonio_gerida = 0.0
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        patrimonio_total = ult["patrimonio_total"]
        patrimonio_gerida = ult["patrimonio_gerida"]

    # ── Montar lista de posições ativas ────────────────────────────
    posicoes_raw = []
    for tkr in sorted(posicoes_dict.keys()):
        p = posicoes_dict[tkr]
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")

        # Ignorar posições zeradas (exceto AGREGADO_PRIVADO que tem valor sem qtd)
        if p.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue

        # Preço atual
        preco_atual = None
        if familia in COTIZADO_PUBLICO:
            preco_atual = preco_em(precos_pub.get(tkr, {}), hoje)
        if preco_atual is None:
            preco_atual = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)

        # Valor atual
        if familia in AGREGADO_PRIVADO:
            valor_atual = preco_atual if preco_atual else p.custo_total
        else:
            valor_atual = p.qtd * preco_atual if preco_atual else p.custo_total

        preco_atual = preco_atual if preco_atual else 0.0

        posicoes_raw.append({
            "ticker": tkr,
            "classe": info.get("classe", "—"),
            "familia": familia,
            "setor": info.get("setor", "—"),
            "composite": info.get("composite", "Gerida"),
            "qtd": p.qtd,
            "preco_atual": preco_atual,
            "valor_atual": valor_atual,
            "custo_total": p.custo_total,
            "custo_medio": p.custo_medio,
        })

    # Ordenar por valor DESC para determinar maior posição
    posicoes_raw.sort(key=lambda x: -x["valor_atual"])

    if not posicoes_raw:
        return {"erro": "Nenhuma posição ativa encontrada."}

    maior_valor = posicoes_raw[0]["valor_atual"] if posicoes_raw else 0.0

    # ── Resumo por classe ──────────────────────────────────────────
    por_classe: dict[str, float] = defaultdict(float)
    for p in posicoes_raw:
        por_classe[p["classe"]] += p["valor_atual"]

    total_posicoes = sum(por_classe.values())

    resumo_por_classe = {
        cls: PorClasse(
            valor=round(val, 2),
            pct=round(val / patrimonio_total * 100, 2) if patrimonio_total > 0 else 0.0,
        )
        for cls, val in sorted(por_classe.items(), key=lambda x: -x[1])
    }

    # P&L total (soma de todas as posições)
    custo_total_carteira = sum(p["custo_total"] for p in posicoes_raw)
    pl_total_reais = total_posicoes - custo_total_carteira
    pl_total_pct = (pl_total_reais / custo_total_carteira * 100) if custo_total_carteira > 0 else 0.0

    resumo = Resumo(
        por_classe=resumo_por_classe,
        total_posicoes_ativas=len(posicoes_raw),
        pl_total_reais=round(pl_total_reais, 2),
        pl_total_pct=round(pl_total_pct, 4),
    )

    # ── Construir objetos Posicao ──────────────────────────────────
    posicoes_out = []
    for p in posicoes_raw:
        cm = p["custo_medio"]
        preco = p["preco_atual"]
        pl_pct = ((preco - cm) / cm * 100) if cm and cm > 0 else None
        pl_reais = p["valor_atual"] - p["custo_total"]
        pct_carteira = (p["valor_atual"] / patrimonio_total * 100) if patrimonio_total > 0 else 0.0

        posicoes_out.append(Posicao(
            ticker=p["ticker"],
            nome=p["ticker"],  # nome = ticker (não há campo nome separado)
            classe=p["classe"],
            setor=p["setor"],
            composite=p["composite"],
            qtd=round(p["qtd"], 6),
            preco_atual=round(preco, 4),
            valor_atual=round(p["valor_atual"], 2),
            custo_medio=round(cm, 4) if cm else None,
            pl_percentual=round(pl_pct, 4) if pl_pct is not None else None,
            pl_reais=round(pl_reais, 2),
            pct_carteira=round(pct_carteira, 2),
            maior_posicao=(p["valor_atual"] >= maior_valor * 0.9999),
        ))

    # ── Alertas automáticos ────────────────────────────────────────
    alertas = []

    # Caixa FIC FUNC sempre informado
    caixa_fic = next((p for p in posicoes_raw if p["ticker"] == "CAIXA FIC FUNC"), None)
    if caixa_fic:
        alertas.append(f"💰 Caixa FIC FUNC disponível: R$ {caixa_fic['valor_atual']:,.2f}")

    # Concentração por ativo (> 80% do total)
    for p in posicoes_raw:
        pct = p["valor_atual"] / patrimonio_total * 100 if patrimonio_total > 0 else 0
        if pct > 80:
            alertas.append(
                f"⚠️ {p['ticker']} representa {pct:.1f}% do patrimônio total"
            )

    # Concentração por classe (> 50% da classe)
    for p in posicoes_raw:
        total_classe = por_classe.get(p["classe"], 0)
        if total_classe > 0:
            pct_cls = p["valor_atual"] / total_classe * 100
            if pct_cls > 50 and len([x for x in posicoes_raw if x["classe"] == p["classe"]]) > 1:
                alertas.append(
                    f"⚠️ {p['ticker']} é {pct_cls:.1f}% da classe {p['classe']}"
                )

    # Patrimônio abaixo do patamar
    if patrimonio_total < 1_350_000:
        alertas.append(
            f"📉 Patrimônio total (R$ {patrimonio_total:,.0f}) abaixo do patamar de R$ 1.350.000"
        )

    resultado = ResultadoPosicoes(
        data_referencia=str(hoje),
        patrimonio_total=round(patrimonio_total, 2),
        resumo=resumo,
        posicoes=posicoes_out,
        alertas=alertas,
    )
    return resultado.model_dump()


# ── TOOL 2 ────────────────────────────────────────────────────────

_PERIODOS_VALIDOS = {"ytd", "1m", "3m", "6m", "1a"}


def fn_obter_performance(periodo: str = "ytd", benchmark: str = "ambos") -> dict:
    """Retorna performance da carteira no período comparada com benchmarks."""
    # Normalizar inputs
    periodo = periodo.lower().strip()
    benchmark = benchmark.upper().strip()
    if periodo not in _PERIODOS_VALIDOS:
        return {"erro": f"Período inválido: '{periodo}'. Use: ytd, 1m, 3m, 6m, 1a"}

    # Garantir cache carregado
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    estado = engine_cache.get_estado()
    df_evo = estado["df_evo"]
    if df_evo.empty:
        return {"erro": "Série de evolução vazia — recalcule a carteira."}

    hoje = estado["hoje"]

    # ── Determinar data de início desejada ────────────────────────
    if periodo == "ytd":
        data_ini_desejada = df_evo["data"].iloc[0]  # primeiro dia disponível
    elif periodo == "1m":
        data_ini_desejada = hoje - timedelta(days=30)
    elif periodo == "3m":
        data_ini_desejada = hoje - timedelta(days=90)
    elif periodo == "6m":
        data_ini_desejada = hoje - timedelta(days=180)
    else:  # "1a"
        data_ini_desejada = hoje - timedelta(days=365)

    # Ajustar para o dia útil mais próximo disponível na série
    datas_disponiveis = list(df_evo["data"])
    datas_disponiveis_sorted = sorted(datas_disponiveis)

    if periodo == "ytd":
        # YTD sempre usa o início da série — sem ajuste
        data_inicio_real = datas_disponiveis_sorted[0]
        periodo_efetivo = "ytd"
    elif data_ini_desejada <= datas_disponiveis_sorted[0]:
        # Período maior que dados disponíveis — usar o máximo disponível
        data_inicio_real = datas_disponiveis_sorted[0]
        periodo_efetivo = f"máximo disponível ({datas_disponiveis_sorted[0]} até {data_fim_real})"
    else:
        # Encontrar data mais próxima disponível (anterior ou igual à desejada)
        candidatos = [d for d in datas_disponiveis_sorted if d <= data_ini_desejada]
        data_inicio_real = candidatos[-1] if candidatos else datas_disponiveis_sorted[0]
        periodo_efetivo = periodo

    data_fim_real = datas_disponiveis_sorted[-1]

    # ── Filtrar série para o período ──────────────────────────────
    mask = (df_evo["data"] >= data_inicio_real) & (df_evo["data"] <= data_fim_real)
    df_periodo = df_evo[mask].copy()

    if df_periodo.empty or len(df_periodo) < 2:
        return {"erro": "Dados insuficientes para o período solicitado."}

    # ── Cálculo TWR sub-período ───────────────────────────────────
    # twr_cum é acumulado desde o início da série. Para sub-período:
    # twr_subp = (1 + twr_cum_fim) / (1 + twr_cum_inicio_anterior) - 1
    # Usamos a linha ANTERIOR ao início do período como base
    idx_inicio = df_evo[df_evo["data"] == data_inicio_real].index[0]

    if idx_inicio > 0:
        row_base = df_evo.loc[idx_inicio - 1]
    else:
        # Início da série — base é 0
        row_base = None

    row_fim = df_periodo.iloc[-1]

    def _retorno_subperiodo(col_cum: str) -> float:
        v_fim = float(row_fim[col_cum])
        if row_base is not None:
            v_base = float(row_base[col_cum])
            return (1 + v_fim) / (1 + v_base) - 1
        return v_fim

    twr_gerida = _retorno_subperiodo("twr_gerida")
    cdi_subp = _retorno_subperiodo("cdi_acum")
    ibov_subp = _retorno_subperiodo("ibov_acum")

    # ── Dias positivos / negativos (baseado no patrimônio_gerida) ─
    pat = df_periodo["patrimonio_gerida"]
    retornos_diarios = pat.pct_change().dropna()
    dias_positivos = int((retornos_diarios > 0).sum())
    dias_negativos = int((retornos_diarios < 0).sum())
    dias_uteis = len(df_periodo)

    # ── Drawdown máximo no período ────────────────────────────────
    drawdown_max = float(df_periodo["drawdown"].min()) if "drawdown" in df_periodo.columns else 0.0

    # ── Benchmarks solicitados ────────────────────────────────────
    benchmarks_out = {}
    incluir_cdi = benchmark in ("CDI", "AMBOS")
    incluir_ibov = benchmark in ("IBOV", "AMBOS")

    if incluir_cdi and cdi_subp != 0:
        benchmarks_out["CDI"] = RetornoBenchmark(
            retorno_pct=round(cdi_subp * 100, 4),
            alpha_pct=round((twr_gerida - cdi_subp) * 100, 4),
            ganhando=twr_gerida > cdi_subp,
        )
    elif incluir_cdi:
        benchmarks_out["CDI"] = RetornoBenchmark(
            retorno_pct=0.0, alpha_pct=0.0, ganhando=False
        )

    if incluir_ibov:
        benchmarks_out["IBOV"] = RetornoBenchmark(
            retorno_pct=round(ibov_subp * 100, 4),
            alpha_pct=round((twr_gerida - ibov_subp) * 100, 4),
            ganhando=twr_gerida > ibov_subp,
        )

    resultado = ResultadoPerformance(
        periodo=periodo,
        periodo_efetivo=periodo_efetivo,
        data_inicio=str(data_inicio_real),
        data_fim=str(data_fim_real),
        dias_uteis=dias_uteis,
        twr_gerida_pct=round(twr_gerida * 100, 4),
        benchmarks=benchmarks_out,
        risco=Risco(
            drawdown_max_pct=round(drawdown_max * 100, 4),
            dias_positivos=dias_positivos,
            dias_negativos=dias_negativos,
        ),
    )
    return resultado.model_dump()
