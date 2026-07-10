"""
GET /api/v1/posicoes
GET /api/v1/evolucao?from=...&to=...
GET /api/v1/carteira-rv
GET /api/v1/atribuicao?mes=...
GET /api/v1/atribuicao-mensal?mes=...&composite=...&bloco_ips=...
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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.deps import get_db
from carteira_clean_web.backend.api.schemas import (
    PosicaoOut, VendaOut, EvolucaoDiariaOut, AlertaOut,
    DashboardOut, MetaOut, AtribuicaoOut, CarteiraRVOut, BrissonFachlerOut,
)
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO, DATA_INICIO
from carteira_clean_web.backend.engine.ir_mensal import calc_ir_mensal
from carteira_clean_web.backend.engine.utils import (
    preco_em, status_liquidacao, data_liquidacao,
    status_liquidacao_d1, data_liquidacao_d1,
)
from carteira_clean_web.backend.engine.valorizacao import valorizar_posicao

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
def posicoes(db: Session = Depends(get_db)):
    """Foto atual de todas as posições com P&L."""
    from carteira_clean_web.backend.db.models import Ativo as AtivoDB
    estado = _exige_cache()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    # Carrega ultima_reconciliacao_lci para ativos LCI/LCA
    _rec_lci_map = {
        row.ticker: row.ultima_reconciliacao_lci
        for row in db.query(AtivoDB).filter(
            AtivoDB.ultima_reconciliacao_lci.isnot(None)
        ).all()
    }

    pat_gerida = 0
    pat_funcef = 0
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        pat_gerida = ult["patrimonio_gerida"]
        pat_funcef = ult["patrimonio_funcef"]

    # Yield projetado por ativo
    proventos_dict = estado.get("proventos", {})
    meses_periodo = max((hoje - DATA_INICIO).days / 30.44, 1.0)

    resultado = []
    for tkr in sorted(posicoes_dict.keys()):
        p = posicoes_dict[tkr]
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")
        composite = info.get("composite", "Gerida")

        v = valorizar_posicao(p, tkr, ativos, precos_pub, precos_man, hoje)
        _is_agregado = v["is_agregado"]

        if p.qtd < 1e-9 and not _is_agregado:
            continue

        preco_atual = v["preco_atual"]
        valor_atual = v["valor_atual"]

        pnl = valor_atual - p.custo_total
        pnl_pct = pnl / p.custo_total if p.custo_total > 0 else 0

        # var_dia: re-ancora d_minus_1 à data real do preco_atual (não ao calendário hoje)
        # Evita var_dia=0% quando preco_atual vem de lookback para o mesmo dia que d_minus_1.
        var_dia = var_dia_pct = None
        if familia in COTIZADO_PUBLICO and preco_atual is not None:
            serie_pub = precos_pub.get(tkr, {})
            datas_pub = sorted(dt for dt in serie_pub if dt <= hoje)
            if datas_pub:
                data_real = datas_pub[-1]
                d_minus_1 = pd.bdate_range(end=data_real, periods=2)[0].date()
                p_d1 = preco_em(serie_pub, d_minus_1)
                if p_d1 and p_d1 > 0:
                    var_dia_pct = (preco_atual - p_d1) / p_d1
                    var_dia = p.qtd * (preco_atual - p_d1)
        elif preco_atual is not None and p.qtd > 0:
            serie_man = precos_man.get(tkr, {})
            datas_man = sorted(dt for dt in serie_man if dt <= hoje)
            if datas_man:
                data_real = datas_man[-1]
                d_minus_1 = pd.bdate_range(end=data_real, periods=2)[0].date()
                p_d1 = preco_em(serie_man, d_minus_1, max_lookback_dias=10)
                if p_d1 and p_d1 > 0:
                    if _is_agregado:
                        var_dia_pct = (preco_atual - p_d1) / p_d1
                        var_dia = preco_atual - p_d1
                    else:
                        var_dia_pct = (preco_atual - p_d1) / p_d1
                        var_dia = p.qtd * (preco_atual - p_d1)

        # yield projetado 12m para este ativo
        prov_ativo = proventos_dict.get(tkr, 0.0)
        if prov_ativo > 0 and valor_atual > 0:
            yield_12m_ativo = round((prov_ativo * (12.0 / meses_periodo)) / valor_atual, 6)
        else:
            yield_12m_ativo = 0.0

        # Badge de staleness para LCI/LCA
        alerta_reconciliacao = None
        if _is_agregado:
            ultima_rec = _rec_lci_map.get(tkr)
            if ultima_rec is not None:
                from datetime import timedelta as _td
                dias_sem_rec = (hoje - ultima_rec).days
                if dias_sem_rec > 180:
                    meses = dias_sem_rec // 30
                    alerta_reconciliacao = {
                        "dias": dias_sem_rec,
                        "mensagem": f"sem reconciliação há {meses} meses",
                    }

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
            yield_12m=yield_12m_ativo,
            alerta_reconciliacao=alerta_reconciliacao,
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
            caixa=getattr(row, "caixa", 0.0),
            twr_gerida=row.twr_gerida,
            twr_total=row.twr_total,
            twr_rv=row.twr_rv,
            cdi_acum=row.cdi_acum,
            ipca_acum=row.ipca_acum,
            ibov_acum=row.ibov_acum,
            sp500_brl_acum=row.sp500_brl_acum,
            nasdaq_brl_acum=getattr(row, "nasdaq_brl_acum", 0.0),
            ouro_brl_acum=getattr(row, "ouro_brl_acum", 0.0),
            drawdown=round(float(row.drawdown), 6) if hasattr(row, "drawdown") else None,
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

    # fluxo externo no dia (APORTE_EXTERNO − RESGATE_EXTERNO)
    from datetime import date as _date
    _hoje_d = ult["data"] if isinstance(ult["data"], _date) else pd.Timestamp(ult["data"]).date()
    _fluxo = 0.0
    for ev in estado["eventos"]:
        if ev["data"] == _hoje_d:
            if ev["tipo"] == "APORTE_EXTERNO":
                _fluxo += abs(ev["valor"] or 0)
            elif ev["tipo"] == "RESGATE_EXTERNO":
                _fluxo -= abs(ev["valor"] or 0)
    fluxo_dia = round(_fluxo, 2) if _fluxo != 0.0 else None
    var_mercado_dia = round(var_dia - (_fluxo), 2) if var_dia is not None else None

    # drawdown máximo
    drawdown_max = drawdown_max_data = None
    if "drawdown" in df.columns and not df["drawdown"].isna().all():
        idx_min = df["drawdown"].idxmin()
        drawdown_max = round(df.loc[idx_min, "drawdown"], 6)
        drawdown_max_data = str(df.loc[idx_min, "data"])

    # volatilidade anualizada da Gerida
    twr_daily = df["twr_gerida"].diff().fillna(0)
    vol_anualizada = float(twr_daily.std() * np.sqrt(252)) if len(df) > 1 else 0.0

    # beta da Gerida vs IBOV
    beta_ibov = None
    if n >= 20:
        ibov_daily = df["ibov_acum"].diff().fillna(0)
        ibov_var = float(ibov_daily.var())
        if ibov_var > 0:
            cov_matrix = np.cov(twr_daily.values, ibov_daily.values)
            beta_ibov = round(float(cov_matrix[0, 1] / ibov_var), 4)

    # yield projetado 12m (baseado em proventos do event log)
    proventos_dict = estado.get("proventos", {})
    meses_periodo = max((estado["hoje"] - DATA_INICIO).days / 30.44, 1.0)
    renda_anual_est = sum(v * (12.0 / meses_periodo) for v in proventos_dict.values() if v > 0)
    pat_total = ult["patrimonio_total"]
    pat_gerida = ult["patrimonio_gerida"]
    yield_12m = round(renda_anual_est / pat_total, 6) if pat_total > 0 else 0.0
    yield_12m_gerida = round(renda_anual_est / pat_gerida, 6) if pat_gerida > 0 else 0.0
    proventos_30d = round(renda_anual_est / 12, 2)

    # Vencimentos RF (de estado["ativos"] que tem data_vencimento após recálculo)
    hoje_date = estado["hoje"]
    posicoes_dict = estado["posicoes"]
    precos_man = estado.get("precos_manuais", {})
    vencimentos_rf = []
    for tkr, info in estado["ativos"].items():
        dv = info.get("data_vencimento")
        if dv is None:
            continue
        if isinstance(dv, str):
            from datetime import date as date_cls
            dv = date_cls.fromisoformat(dv)
        dias_rest = (dv - hoje_date).days
        # Valor atual via posição
        p = posicoes_dict.get(tkr)
        val = None
        if p:
            familia = info.get("familia", "")
            if familia in AGREGADO_PRIVADO:
                preco = preco_em(precos_man.get(tkr, {}), hoje_date, max_lookback_dias=60)
                val = preco if preco else p.custo_total
            else:
                val = p.custo_total
        vencimentos_rf.append({
            "ticker": tkr,
            "familia": info.get("familia"),
            "data_vencimento": str(dv),
            "dias_restantes": dias_rest,
            "valor_atual": round(val, 2) if val else None,
            "alerta": "CRITICO" if dias_rest <= 30 else ("ATENCAO" if dias_rest <= 90 else "OK"),
        })
    vencimentos_rf.sort(key=lambda x: x["data_vencimento"])

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
        var_mercado_dia=var_mercado_dia,
        fluxo_dia=fluxo_dia,
        drawdown_max=drawdown_max,
        drawdown_max_data=drawdown_max_data,
        vol_anualizada=round(vol_anualizada, 6),
        beta_ibov=beta_ibov,
        yield_12m=yield_12m,
        yield_12m_gerida=yield_12m_gerida,
        renda_anual_est=round(renda_anual_est, 2),
        proventos_30d=proventos_30d,
        vencimentos_rf=vencimentos_rf,
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
        valor = valorizar_posicao(p, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]
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

def _atrib_rows(df) -> list[AtribuicaoOut]:
    return [
        AtribuicaoOut(
            mes=row.mes,
            composite=row.composite,
            ativo=row.ativo,
            retorno_ativo=row.retorno_ativo,
            peso_medio=row.peso_medio,
            contribuicao=row.contribuicao,
            benchmark=getattr(row, "benchmark", None),
            bloco_ips=getattr(row, "bloco_ips", None),
        )
        for row in df.itertuples(index=False)
    ]


@router.get("/atribuicao", response_model=list[AtribuicaoOut])
def atribuicao(mes: Optional[str] = Query(None, description="Formato YYYY-MM")):
    """Atribuição mensal (long format: mês × ativo). Filtro opcional por mês."""
    estado = _exige_cache()
    df = estado["df_atrib"]
    if df.empty:
        return []
    if mes:
        df = df[df["mes"] == mes]
    return _atrib_rows(df)


@router.get("/atribuicao-mensal", response_model=list[AtribuicaoOut])
def atribuicao_mensal(
    mes: Optional[str] = Query(None, description="Formato YYYY-MM"),
    composite: Optional[str] = Query(None, description="Gerida / FUNCEF / TOTAL_CARTEIRA"),
    bloco_ips: Optional[str] = Query(None, description="SWING_TRADE / GROWTH / RENDA_FIXA / DEFENSIVOS / FORA_IPS"),
):
    """Atribuição mensal com filtros por mês, composite e bloco IPS. Inclui linhas TOTAL."""
    estado = _exige_cache()
    df = estado["df_atrib"]
    if df.empty:
        return []
    if mes:
        df = df[df["mes"] == mes]
    if composite:
        df = df[df["composite"] == composite]
    if bloco_ips:
        df = df[df["bloco_ips"].fillna("") == bloco_ips]
    return _atrib_rows(df)


@router.get("/brinson-fachler", response_model=list[BrissonFachlerOut])
def brinson_fachler(
    mes: Optional[str] = Query(None, description="Formato YYYY-MM"),
    bloco_ips: Optional[str] = Query(None, description="SWING_TRADE / GROWTH / DEFENSIVOS / RENDA_FIXA / TOTAL"),
):
    """Decomposição Brinson-Fachler por bloco IPS. Inclui linha TOTAL por mês."""
    estado = _exige_cache()
    df = estado.get("df_bf")
    if df is None or df.empty:
        return []
    if mes:
        df = df[df["mes"] == mes]
    if bloco_ips:
        df = df[df["bloco_ips"] == bloco_ips]
    return [
        BrissonFachlerOut(
            mes=row.mes,
            bloco_ips=row.bloco_ips,
            w_real=float(row.w_real),
            w_alvo=float(row.w_alvo),
            R_real_bloco=float(row.R_real_bloco),
            R_bench_bloco=float(row.R_bench_bloco),
            R_bench_total=float(row.R_bench_total),
            efeito_alocacao=float(row.efeito_alocacao),
            efeito_selecao=float(row.efeito_selecao),
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


# ─── Proventos projetados ─────────────────────────────────────────

@router.get("/proventos-projetados")
def proventos_projetados():
    """Histórico de proventos pagos + projeção para os próximos 12 meses.
    Baseado exclusivamente no event log — sem scraping externo."""
    from collections import defaultdict
    from carteira_clean_web.backend.engine.constantes import PROVENTOS

    estado = _exige_cache()
    eventos = estado["eventos"]
    ativos_info = estado["ativos"]
    hoje = estado["hoje"]
    meses_periodo = max((hoje - DATA_INICIO).days / 30.44, 1.0)

    tipos_prov = PROVENTOS  # DIVIDENDO, JCP, RENDIMENTO, AMORTIZACAO
    prov_events = [e for e in eventos if e["tipo"] in tipos_prov]

    # Histórico (já recebido)
    historico = []
    total_hist = 0.0
    prov_por_ativo = defaultdict(float)
    for ev in prov_events:
        familia = ativos_info.get(ev["ativo"], {}).get("familia", "")
        historico.append({
            "data": str(ev["data"]),
            "ativo": ev["ativo"],
            "familia": familia,
            "tipo": ev["tipo"],
            "valor": round(ev["valor"] or 0, 2),
            "status": "REALIZADO",
        })
        total_hist += ev["valor"] or 0
        prov_por_ativo[ev["ativo"]] += ev["valor"] or 0

    # Projeção: média mensal × 12 meses à frente
    projecao = []
    total_proj_12m = 0.0
    for tkr, total in prov_por_ativo.items():
        if total <= 0:
            continue
        mensal = total / meses_periodo
        familia = ativos_info.get(tkr, {}).get("familia", "")
        for offset in range(1, 13):
            proj_ano = hoje.year + (hoje.month - 1 + offset) // 12
            proj_mes = (hoje.month - 1 + offset) % 12 + 1
            projecao.append({
                "data": f"{proj_ano}-{proj_mes:02d}-01",
                "ativo": tkr,
                "familia": familia,
                "tipo": "PROJEÇÃO",
                "valor": round(mensal, 2),
                "status": "PROJETADO*",
            })
            total_proj_12m += mensal

    return {
        "historico": sorted(historico, key=lambda x: x["data"], reverse=True),
        "projecao": sorted(projecao, key=lambda x: x["data"]),
        "total_historico": round(total_hist, 2),
        "total_projetado_12m": round(total_proj_12m, 2),
        "meses_base": round(meses_periodo, 1),
        "aviso": "Projeção baseada em histórico — dados anunciados serão adicionados quando disponíveis.",
    }


# ─── Meta / Projeção ──────────────────────────────────────────────

@router.get("/meta", response_model=MetaOut)
def meta():
    """Projeção ano-a-ano até atingir R$ 3MM."""
    estado = _exige_cache()
    df = estado["df_evo"]
    if df.empty:
        raise HTTPException(503, "Sem dados de evolução")

    META = 3_000_000.0

    # Aporte anual calculado dinamicamente dos últimos 12 meses de eventos reais.
    # Tipos elegíveis: CONTRIBUICAO (FUNCEF) + APORTE_EXTERNO (carteira gerida).
    # Se histórico < 6 meses, extrapola proporcionalmente.
    TIPOS_APORTE = {"CONTRIBUICAO", "APORTE_EXTERNO"}
    from datetime import timedelta as _td
    eventos_cache = estado.get("eventos", [])
    hoje_date = estado["hoje"]
    janela_inicio = hoje_date - _td(days=366)
    eventos_aporte = [
        ev for ev in eventos_cache
        if ev.get("tipo") in TIPOS_APORTE and ev.get("data") >= janela_inicio
    ]
    if eventos_aporte:
        total_12m = sum(abs(ev["valor"] or 0) for ev in eventos_aporte)
        meses_unicos = len({
            f"{ev['data'].year}-{ev['data'].month:02d}" for ev in eventos_aporte
        })
        if meses_unicos >= 6:
            aporte_anual = total_12m * (12 / meses_unicos)
        else:
            # poucos meses — usa média × 12
            aporte_anual = (total_12m / meses_unicos) * 12
    else:
        # fallback: constante histórica
        aporte_anual = 12 * 6_392.0 + 10_000.0 + 10_000.0

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
