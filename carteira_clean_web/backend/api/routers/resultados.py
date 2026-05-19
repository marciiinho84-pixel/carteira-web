"""
GET /api/v1/posicoes
GET /api/v1/evolucao?from=...&to=...
GET /api/v1/carteira-rv
GET /api/v1/atribuicao?mes=...
GET /api/v1/meta
GET /api/v1/dashboard
GET /api/v1/precos/{ticker}?from=...&to=...

Todos leem o cache do engine — sem recalcular.
"""

import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.schemas import (
    PosicaoOut, VendaOut, EvolucaoDiariaOut, AlertaOut,
    DashboardOut, MetaOut, AtribuicaoOut, CarteiraRVOut,
)
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO
from carteira_clean_web.backend.engine.ir_mensal import calc_ir_mensal
from carteira_clean_web.backend.engine.utils import (
    preco_em, status_liquidacao, data_liquidacao,
    status_liquidacao_d1, data_liquidacao_d1,
)

router = APIRouter(tags=["Resultados"])


def _exige_cache():
    if not engine_cache.esta_calculado():
        raise HTTPException(
            503,
            "Engine ainda não calculado. Chame POST /api/v1/calcular primeiro."
        )
    return engine_cache.get_estado()


# ─── Posições ────────────────────────────────────────────────────

@router.get("/posicoes", response_model=list[PosicaoOut])
def posicoes():
    """Foto atual de todas as posições com P&L."""
    estado = _exige_cache()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    pat_gerida = 0
    pat_funcef = 0
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        pat_gerida = ult["patrimonio_gerida"]
        pat_funcef = ult["patrimonio_funcef"]

    # Dia útil anterior para var_dia
    d_minus_1 = pd.bdate_range(end=hoje, periods=2)[0].date()

    resultado = []
    for tkr in sorted(posicoes_dict.keys()):
        p = posicoes_dict[tkr]
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")
        composite = info.get("composite", "Gerida")

        if p.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue

        preco_atual = None
        if familia in COTIZADO_PUBLICO:
            preco_atual = preco_em(precos_pub.get(tkr, {}), hoje)
        if preco_atual is None:
            preco_atual = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)

        if familia in AGREGADO_PRIVADO:
            valor_atual = preco_atual if preco_atual else p.custo_total
        else:
            valor_atual = p.qtd * preco_atual if preco_atual else p.custo_total

        pnl = valor_atual - p.custo_total
        pnl_pct = pnl / p.custo_total if p.custo_total > 0 else 0

        # var_dia: (preço_hoje - preço_d-1) / preço_d-1, aplicado ao qtd atual
        var_dia = var_dia_pct = None
        if familia in COTIZADO_PUBLICO and preco_atual is not None:
            p_d1 = preco_em(precos_pub.get(tkr, {}), d_minus_1)
            if p_d1 and p_d1 > 0:
                var_dia_pct = (preco_atual - p_d1) / p_d1
                var_dia = p.qtd * (preco_atual - p_d1)
        elif preco_atual is not None and p.qtd > 0:
            p_d1 = preco_em(precos_man.get(tkr, {}), d_minus_1, max_lookback_dias=10)
            if p_d1 and p_d1 > 0:
                if familia in AGREGADO_PRIVADO:
                    var_dia_pct = (preco_atual - p_d1) / p_d1
                    var_dia = preco_atual - p_d1
                else:
                    var_dia_pct = (preco_atual - p_d1) / p_d1
                    var_dia = p.qtd * (preco_atual - p_d1)

        resultado.append(PosicaoOut(
            ticker=tkr,
            classe=info.get("classe"),
            familia=familia,
            composite=composite,
            qtd=p.qtd,
            custo_total=p.custo_total,
            custo_medio=p.custo_medio,
            preco_atual=preco_atual,
            valor_atual=valor_atual,
            pnl=pnl,
            pnl_pct=pnl_pct,
            var_dia=round(var_dia, 2) if var_dia is not None else None,
            var_dia_pct=round(var_dia_pct, 6) if var_dia_pct is not None else None,
        ))
    return resultado


# ─── Evolução diária ──────────────────────────────────────────────

@router.get("/evolucao", response_model=list[EvolucaoDiariaOut])
def evolucao(
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
):
    """Série temporal de patrimônio + TWR + benchmarks."""
    estado = _exige_cache()
    df = estado["df_evo"]
    if df.empty:
        return []
    if from_:
        df = df[df["data"] >= from_]
    if to:
        df = df[df["data"] <= to]
    return [
        EvolucaoDiariaOut(
            data=row.data,
            patrimonio_gerida=row.patrimonio_gerida,
            patrimonio_funcef=row.patrimonio_funcef,
            patrimonio_total=row.patrimonio_total,
            patrimonio_rv=row.patrimonio_rv,
            twr_gerida=row.twr_gerida,
            twr_total=row.twr_total,
            twr_rv=row.twr_rv,
            cdi_acum=row.cdi_acum,
            ipca_acum=row.ipca_acum,
            ibov_acum=row.ibov_acum,
            sp500_brl_acum=row.sp500_brl_acum,
        )
        for row in df.itertuples(index=False)
    ]


# ─── Dashboard ────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardOut)
def dashboard():
    """KPIs executivos: patrimônio, TWR, benchmarks, P&L, alertas."""
    estado = _exige_cache()
    df = estado["df_evo"]
    if df.empty:
        raise HTTPException(503, "Sem dados de evolução calculados")
    ult = df.iloc[-1]
    n = len(df)
    twr_gerida = ult["twr_gerida"]
    twr_total = ult["twr_total"]
    twr_rv = ult.get("twr_rv", 0)
    cdi_ytd = ult["cdi_acum"]
    ibov_ytd = ult["ibov_acum"]
    sp500_brl = ult["sp500_brl_acum"]
    excesso = twr_gerida - cdi_ytd
    twr_ann = (1 + twr_gerida) ** (252 / n) - 1 if n > 0 else 0
    twr_daily = df["twr_gerida"].diff().fillna(0)
    std = twr_daily.std()
    sharpe = (twr_ann - cdi_ytd) / (std * np.sqrt(252)) if std > 0 else 0
    pnl = sum(v["pnl"] for v in estado["vendas_rv"])
    alertas = [AlertaOut(nivel=a[0], ativo=a[1], mensagem=a[2]) for a in estado["alertas"]]

    # var_dia: diferença entre última e penúltima linha do df_evo
    var_dia = var_dia_pct = None
    if n >= 2:
        pat_hoje = ult["patrimonio_total"]
        pat_d1 = df.iloc[-2]["patrimonio_total"]
        if pat_d1 > 0:
            var_dia = round(pat_hoje - pat_d1, 2)
            var_dia_pct = round((pat_hoje - pat_d1) / pat_d1, 6)

    # drawdown máximo
    drawdown_max = drawdown_max_data = None
    if "drawdown" in df.columns and not df["drawdown"].isna().all():
        idx_min = df["drawdown"].idxmin()
        drawdown_max = round(df.loc[idx_min, "drawdown"], 6)
        drawdown_max_data = str(df.loc[idx_min, "data"])

    return DashboardOut(
        patrimonio_total=ult["patrimonio_total"],
        patrimonio_gerida=ult["patrimonio_gerida"],
        patrimonio_funcef=ult["patrimonio_funcef"],
        patrimonio_rv=ult["patrimonio_rv"],
        twr_gerida_ytd=twr_gerida,
        twr_total_ytd=twr_total,
        twr_rv_ytd=twr_rv,
        cdi_ytd=cdi_ytd,
        ibov_ytd=ibov_ytd,
        sp500_brl_ytd=sp500_brl,
        excesso_cdi=excesso,
        sharpe=round(sharpe, 4),
        pnl_vendas_rv=round(pnl, 2),
        n_alertas=len(alertas),
        alertas=alertas,
        var_dia=var_dia,
        var_dia_pct=var_dia_pct,
        drawdown_max=drawdown_max,
        drawdown_max_data=drawdown_max_data,
    )


# ─── Carteira RV ──────────────────────────────────────────────────

@router.get("/carteira-rv", response_model=CarteiraRVOut)
def carteira_rv():
    """Estação operacional de RV: caixa, calendário D+2, setores, performance."""
    estado = _exige_cache()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    eventos = estado["eventos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    import pandas as pd

    # Caixa atual
    caixa_atual = 0.0
    p_fic = posicoes_dict.get("CAIXA FIC FUNC")
    if p_fic and p_fic.qtd > 0:
        cota = preco_em(precos_man.get("CAIXA FIC FUNC", {}), hoje, max_lookback_dias=60)
        if cota:
            caixa_atual = p_fic.qtd * cota

    # Liquidações próximas (D+2, 5 dias úteis)
    proximos_5_du = pd.bdate_range(start=hoje, periods=6).date
    pendentes = []
    entrando_5d = saindo_5d = 0.0
    saldo_running = caixa_atual

    evs_pendentes = []
    for ev in eventos:
        familia = ativos.get(ev["ativo"], {}).get("familia", "")
        # RV cotizado: D+2
        if familia in COTIZADO_PUBLICO:
            st = status_liquidacao(ev, hoje)
            if st == "LIQUIDADO":
                continue
            d_liq = data_liquidacao(ev["data"])
            prazo = "D+2"
        # Fundo CP (FIC FUNC): D+1, apenas COMPRA/VENDA
        elif familia == "Fundo CP" and ev["tipo"] in ("COMPRA", "VENDA"):
            st = status_liquidacao_d1(ev, hoje)
            if st == "LIQUIDADO":
                continue
            d_liq = data_liquidacao_d1(ev["data"])
            prazo = "D+1"
        else:
            continue
        if d_liq not in proximos_5_du:
            continue
        valor = abs(ev["valor"] or 0)
        impacto = valor if st == "PENDENTE_SAIDA" else -valor
        evs_pendentes.append((d_liq, ev, impacto, prazo))

    evs_pendentes.sort(key=lambda x: (x[0], x[1]["data"]))
    for d_liq, ev, impacto, prazo in evs_pendentes:
        if impacto > 0:
            entrando_5d += impacto
        else:
            saindo_5d += abs(impacto)
        saldo_running += impacto
        pendentes.append({
            "liquidacao": str(d_liq),
            "trade": str(ev["data"]),
            "tipo": ev["tipo"],
            "ativo": ev["ativo"],
            "qtd": ev["qtd"],
            "valor": abs(ev["valor"] or 0),
            "impacto": impacto,
            "prazo": prazo,
            "saldo_projetado": round(saldo_running, 2),
        })

    # Distribuição setorial
    setor_valores = defaultdict(lambda: {"valor": 0, "n": 0, "ativos": []})
    total_rv = 0.0
    for tkr, p in posicoes_dict.items():
        info = ativos.get(tkr, {})
        if info.get("familia") not in COTIZADO_PUBLICO or p.qtd < 1e-9:
            continue
        preco = preco_em(precos_pub.get(tkr, {}), hoje)
        if preco is None:
            preco = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)
        valor = p.qtd * preco if preco else p.custo_total
        setor = info.get("setor", "Outros")
        setor_valores[setor]["valor"] += valor
        setor_valores[setor]["n"] += 1
        setor_valores[setor]["ativos"].append(tkr)
        total_rv += valor

    setores = [
        {
            "setor": setor,
            "valor": round(info["valor"], 2),
            "pct_rv": round(info["valor"] / total_rv, 6) if total_rv > 0 else 0,
            "n_ativos": info["n"],
            "ativos": sorted(info["ativos"]),
        }
        for setor, info in sorted(setor_valores.items(), key=lambda x: -x[1]["valor"])
    ]

    twr_rv = ibov_ytd = sp500_brl_ytd = 0.0
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        twr_rv = ult.get("twr_rv", 0)
        ibov_ytd = ult.get("ibov_acum", 0)
        sp500_brl_ytd = ult.get("sp500_brl_acum", 0)

    return CarteiraRVOut(
        caixa_atual=round(caixa_atual, 2),
        entrando_5d=round(entrando_5d, 2),
        saindo_5d=round(saindo_5d, 2),
        saldo_projetado=round(caixa_atual + entrando_5d - saindo_5d, 2),
        pendentes=pendentes,
        setores=setores,
        twr_rv=twr_rv,
        ibov_ytd=ibov_ytd,
        sp500_brl_ytd=sp500_brl_ytd,
    )


# ─── Atribuição mensal ────────────────────────────────────────────

@router.get("/atribuicao", response_model=list[AtribuicaoOut])
def atribuicao(mes: Optional[str] = Query(None, description="Formato YYYY-MM")):
    """Atribuição mensal (long format: mês × ativo). Filtro opcional por mês."""
    estado = _exige_cache()
    df = estado["df_atrib"]
    if df.empty:
        return []
    if mes:
        df = df[df["mes"] == mes]
    return [
        AtribuicaoOut(
            mes=row.mes,
            composite=row.composite,
            ativo=row.ativo,
            retorno_ativo=row.retorno_ativo,
            peso_medio=row.peso_medio,
            contribuicao=row.contribuicao,
            benchmark=row.benchmark if hasattr(row, "benchmark") else None,
        )
        for row in df.itertuples(index=False)
    ]


# ─── Relatório de vendas ──────────────────────────────────────────

@router.get("/vendas", response_model=list[VendaOut])
def vendas():
    """Todas as vendas de RV com P&L realizado."""
    estado = _exige_cache()
    return [
        VendaOut(
            data=v["data"],
            ticker=v["ticker"],
            qtd_vendida=v["qtd_vendida"],
            preco_venda=v["preco_venda"],
            custo_medio=v["custo_medio"],
            valor_recebido=v["valor_recebido"],
            pnl=v["pnl"],
            pnl_pct=v["pnl_pct"],
        )
        for v in sorted(estado["vendas_rv"], key=lambda x: x["data"])
    ]


# ─── IR Mensal ────────────────────────────────────────────────────

@router.get("/ir-mensal")
def ir_mensal():
    """Estimativa de IR mensal sobre vendas de RV com regras de isenção."""
    estado = _exige_cache()
    return calc_ir_mensal(estado["vendas_rv"], estado["ativos"])


# ─── Meta / Projeção ──────────────────────────────────────────────

@router.get("/meta", response_model=MetaOut)
def meta():
    """Projeção ano-a-ano até atingir R$ 3MM."""
    estado = _exige_cache()
    df = estado["df_evo"]
    if df.empty:
        raise HTTPException(503, "Sem dados de evolução")

    META = 3_000_000.0
    APORTE_FUNCEF_MES = 6_392.0
    APORTE_GERIDA_MARCO = 10_000.0
    APORTE_GERIDA_OUTUBRO = 10_000.0
    aporte_anual = 12 * APORTE_FUNCEF_MES + APORTE_GERIDA_MARCO + APORTE_GERIDA_OUTUBRO

    ult = df.iloc[-1]
    n = len(df)
    pat_atual = ult["patrimonio_total"]
    twr_ytd = ult["twr_total"]
    twr_anualizado = (1 + twr_ytd) ** (252 / n) - 1 if n > 0 else 0

    ano_atual = ult["data"].year
    pat_proj = pat_atual
    projecao = [{"ano": ano_atual, "aporte": 0, "twr": twr_anualizado,
                 "patrimonio": round(pat_proj, 2), "pct_meta": round(pat_proj / META, 4)}]
    for offset in range(1, 31):
        pat_proj = pat_proj * (1 + twr_anualizado) + aporte_anual
        projecao.append({
            "ano": ano_atual + offset,
            "aporte": aporte_anual,
            "twr": round(twr_anualizado, 6),
            "patrimonio": round(pat_proj, 2),
            "pct_meta": round(pat_proj / META, 4),
        })
        if pat_proj >= META:
            break

    return MetaOut(
        patrimonio_atual=round(pat_atual, 2),
        twr_anualizado=round(twr_anualizado, 6),
        aporte_anual=aporte_anual,
        meta=META,
        projecao=projecao,
    )


# ─── Série de preços de um ticker ─────────────────────────────────

@router.get("/precos/{ticker}")
def precos_ticker(
    ticker: str,
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
):
    """Série histórica de preços de um ativo (públicos + manuais combinados)."""
    estado = _exige_cache()
    ticker = ticker.upper()
    precos_pub = estado.get("precos_publicos", {}).get(ticker, {})
    precos_man = estado.get("precos_manuais", {}).get(ticker, {})
    todos = {**precos_man, **precos_pub}  # público prevalece sobre manual

    if not todos:
        raise HTTPException(404, f"Sem preços para '{ticker}'")

    serie = sorted(
        [{"data": str(d), "valor": v, "fonte": "publico" if d in precos_pub else "manual"}
         for d, v in todos.items()],
        key=lambda x: x["data"],
    )
    if from_:
        serie = [s for s in serie if s["data"] >= str(from_)]
    if to:
        serie = [s for s in serie if s["data"] <= str(to)]
    return {"ticker": ticker, "n": len(serie), "precos": serie}
