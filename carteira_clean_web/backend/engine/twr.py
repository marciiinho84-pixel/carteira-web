"""
engine/twr.py — Evolução diária + TWR Modified Dietz simplificado + benchmarks.

Lógica copiada de calc_evolucao_diaria() e calc_twr_e_benchmarks()
em atualizar_carteira.py. Sem alteração de comportamento.
"""

import logging
from collections import defaultdict
from datetime import date

import pandas as pd

from .constantes import (
    DATA_INICIO,
    COTIZADO_PUBLICO,
    COTIZADO_PRIVADO,
    AGREGADO_PRIVADO,
    COMPRAS,
    VENDAS,
    FLUXOS_EXTERNOS,
)
from .posicoes import Posicao
from .precos import carregar_benchmarks_da_tabela
from .utils import preco_em

log = logging.getLogger("engine.twr")

# Benchmarks validados via tabela na Fase A (antes do corte de produção)
_BENCHMARKS_FASE_A = frozenset({"CDI", "IBOV", "SP500", "USDBRL", "IPCA"})


def _comparar_benchmarks(benchmarks_pkl: dict, benchmarks_tabela: dict) -> dict:
    """Compara pkl vs tabela para os 5 benchmarks existentes (Fase A).

    Returns:
        ok, divergentes, ausentes_tab, ausentes_pkl, detalhes:
        detalhes = [(categoria, nome, dt, v_pkl, v_tab, rel_ou_None)]
    """
    ok = div = aus_tab = aus_pkl = 0
    detalhes: list = []
    for nome in sorted(_BENCHMARKS_FASE_A):
        s_pkl = benchmarks_pkl.get(nome, {})
        s_tab = benchmarks_tabela.get(nome, {})
        for dt in sorted(set(s_pkl) | set(s_tab)):
            v_p = s_pkl.get(dt)
            v_t = s_tab.get(dt)
            if v_p is None:
                aus_pkl += 1
                detalhes.append(("AUSENTE_PKL", nome, dt, None, v_t, None))
            elif v_t is None:
                aus_tab += 1
                detalhes.append(("AUSENTE_TAB", nome, dt, v_p, None, None))
            else:
                rel = abs(v_p - v_t) / abs(v_p) if abs(v_p) > 1e-12 else 0.0
                if rel <= 1e-5:
                    ok += 1
                else:
                    div += 1
                    detalhes.append(("DIVERGENTE", nome, dt, v_p, v_t, rel))
    return {
        "ok": ok, "divergentes": div,
        "ausentes_tab": aus_tab, "ausentes_pkl": aus_pkl,
        "detalhes": detalhes,
    }


def calc_evolucao_diaria(
    eventos: list,
    ativos: dict,
    precos_publicos: dict,
    precos_manuais: dict,
    data_fim: date,
) -> pd.DataFrame:
    datas = [d.date() for d in pd.bdate_range(start=DATA_INICIO, end=data_fim)]
    if not datas:
        return pd.DataFrame()

    eventos_por_data = defaultdict(list)
    for ev in eventos:
        eventos_por_data[ev["data"]].append(ev)

    posicoes = defaultdict(Posicao)
    linhas = []

    for d in datas:
        for ev in eventos_por_data.get(d, []):
            tkr = ev["ativo"]
            tipo = ev["tipo"]
            p = posicoes[tkr]
            qtd = ev["qtd"] or 0
            valor = ev["valor"] or 0
            if tipo in COMPRAS or tipo == "CONTRIBUICAO":
                p.qtd += qtd
                p.custo_total += abs(valor)
            elif tipo == "APORTE_EXTERNO":
                familia = ativos.get(tkr, {}).get("familia", "")
                if familia in COTIZADO_PRIVADO:
                    valor_abs = abs(valor)
                    cota = preco_em(precos_manuais.get(tkr, {}), d)
                    if cota and cota > 0 and valor_abs > 0:
                        p.qtd += valor_abs / cota
                        p.custo_total += valor_abs
            elif tipo in VENDAS and p.qtd > 1e-9:
                cm = p.custo_medio
                p.custo_total -= cm * qtd
                p.qtd -= qtd
                if abs(p.qtd) < 1e-6:
                    p.qtd = 0.0
                    p.custo_total = 0.0

        valor_gerida = 0.0
        valor_funcef = 0.0
        valor_rv = 0.0

        for tkr, p in posicoes.items():
            info = ativos.get(tkr, {})
            familia = info.get("familia", "")
            composite = info.get("composite", "Gerida")
            preco = None
            if familia in COTIZADO_PUBLICO and tkr in precos_publicos:
                preco = preco_em(precos_publicos[tkr], d)
            if preco is None:
                preco = preco_em(precos_manuais.get(tkr, {}), d, max_lookback_dias=60)
            if familia in AGREGADO_PRIVADO:
                valor_pos = preco if preco else 0
            elif p.qtd > 1e-9:
                valor_pos = p.qtd * preco if preco else p.custo_total
            else:
                continue
            if composite == "FUNCEF":
                valor_funcef += valor_pos
            else:
                valor_gerida += valor_pos
                if familia in COTIZADO_PUBLICO:
                    valor_rv += valor_pos

        linhas.append({
            "data": d,
            "patrimonio_gerida": valor_gerida,
            "patrimonio_funcef": valor_funcef,
            "patrimonio_total": valor_gerida + valor_funcef,
            "patrimonio_rv": valor_rv,
        })

    return pd.DataFrame(linhas)


def calc_twr_e_benchmarks(
    df_evo: pd.DataFrame,
    eventos: list,
    benchmarks: dict,
    aportes_inferidos: list = None,
    ativos: dict = None,
) -> pd.DataFrame:
    if df_evo.empty:
        return df_evo

    aportes_inferidos = aportes_inferidos or []
    ativos = ativos or {}

    fluxos_g = defaultdict(float)
    fluxos_f = defaultdict(float)
    fluxos_rv = defaultdict(float)

    for ev in eventos:
        if ev["tipo"] in FLUXOS_EXTERNOS:
            valor = abs(ev["valor"] or 0)
            sinal = 1 if ev["tipo"] in {"APORTE_EXTERNO", "CONTRIBUICAO"} else -1
            if ev["ativo"] == "FUNCEF":
                fluxos_f[ev["data"]] += sinal * valor
            else:
                fluxos_g[ev["data"]] += sinal * valor
        familia = ativos.get(ev["ativo"], {}).get("familia", "")
        if familia in COTIZADO_PUBLICO:
            valor = abs(ev["valor"] or 0)
            if ev["tipo"] == "COMPRA":
                fluxos_rv[ev["data"]] += valor
            elif ev["tipo"] == "VENDA":
                fluxos_rv[ev["data"]] -= valor
            elif ev["tipo"] == "SALDO_INICIAL":
                fluxos_rv[ev["data"]] += abs(ev["valor"] or 0)

    for ap in aportes_inferidos:
        fluxos_g[ap["data"]] += ap["valor"]

    df = df_evo.copy()
    df["fluxo_gerida"] = df["data"].map(lambda d: fluxos_g.get(d, 0))
    df["fluxo_funcef"] = df["data"].map(lambda d: fluxos_f.get(d, 0))
    df["fluxo_total"] = df["fluxo_gerida"] + df["fluxo_funcef"]
    df["fluxo_rv"] = df["data"].map(lambda d: fluxos_rv.get(d, 0))

    def _calc_twr_serie(patrimonio, fluxo):
        retornos = [0.0]
        for i in range(1, len(patrimonio)):
            v0 = patrimonio.iloc[i - 1]
            v1 = patrimonio.iloc[i]
            cf = fluxo.iloc[i]
            denom = v0 + cf
            r = (v1 - denom) / denom if denom > 0 else 0
            retornos.append(r)
        twr_cum = [0.0]
        for r in retornos[1:]:
            twr_cum.append((1 + twr_cum[-1]) * (1 + r) - 1)
        return twr_cum

    df["twr_gerida"] = _calc_twr_serie(df["patrimonio_gerida"], df["fluxo_gerida"])
    df["twr_total"] = _calc_twr_serie(df["patrimonio_total"], df["fluxo_total"])
    df["twr_rv"] = (
        _calc_twr_serie(df["patrimonio_rv"], df["fluxo_rv"])
        if "patrimonio_rv" in df.columns
        else 0
    )

    cdi = benchmarks.get("CDI", {})
    ipca = benchmarks.get("IPCA", {})
    ibov = benchmarks.get("IBOV", {})
    sp500 = benchmarks.get("SP500", {})
    usdbrl = benchmarks.get("USDBRL", {})

    cdi_acum, ipca_acum, ibov_acum, sp_brl_acum = [], [], [], []
    cdi_v, ipca_v = 1.0, 1.0
    ibov_base = sp_base_brl = None

    for d in df["data"]:
        if d in cdi:
            cdi_v *= 1 + cdi[d]
        cdi_acum.append(cdi_v - 1)
        if d in ipca:
            ipca_v *= 1 + ipca[d]
        ipca_acum.append(ipca_v - 1)
        ibov_p = preco_em(ibov, d)
        if ibov_base is None and ibov_p:
            ibov_base = ibov_p
        ibov_acum.append((ibov_p / ibov_base - 1) if ibov_base and ibov_p else 0)
        sp_p = preco_em(sp500, d)
        usd = preco_em(usdbrl, d)
        if sp_p and usd:
            sp_brl = sp_p * usd
            if sp_base_brl is None:
                sp_base_brl = sp_brl
            sp_brl_acum.append(sp_brl / sp_base_brl - 1)
        else:
            sp_brl_acum.append(sp_brl_acum[-1] if sp_brl_acum else 0)

    df["cdi_acum"] = cdi_acum
    df["ipca_acum"] = ipca_acum
    df["ibov_acum"] = ibov_acum
    df["sp500_brl_acum"] = sp_brl_acum

    # Drawdown da Gerida: queda % do pico histórico (sempre ≤ 0)
    max_gerida = df["patrimonio_gerida"].cummax()
    denom = max_gerida.where(max_gerida > 0, other=1.0)
    df["drawdown"] = ((df["patrimonio_gerida"] - max_gerida) / denom).clip(upper=0)

    # ── Fase A: comparação tabela vs pkl + NASDAQ/OURO via tabela ────────────
    try:
        benchmarks_tabela = carregar_benchmarks_da_tabela()

        # Comparação 5 benchmarks existentes (produção segue lendo pkl)
        stats = _comparar_benchmarks(benchmarks, benchmarks_tabela)
        total = stats["ok"] + stats["divergentes"] + stats["ausentes_tab"] + stats["ausentes_pkl"]
        if stats["divergentes"] or stats["ausentes_tab"]:
            log.warning(
                f"benchmarks Fase A — {total} pares: OK={stats['ok']}  "
                f"DIVERGENTES={stats['divergentes']}  "
                f"AUSENTES_TAB={stats['ausentes_tab']}  AUSENTES_PKL={stats['ausentes_pkl']}"
            )
            for cat, nome, dt, v_p, v_t, rel in stats["detalhes"][:20]:
                if cat == "DIVERGENTE":
                    log.warning(
                        f"  {cat} {nome} {dt}: pkl={v_p:.6g}  tab={v_t:.6g}  rel={rel:.2e}"
                    )
                elif cat == "AUSENTE_TAB":
                    log.warning(f"  {cat} {nome} {dt}: pkl={v_p:.6g}")
        else:
            log.info(f"benchmarks Fase A — {total} pares OK, 0 divergências (tabela ≡ pkl)")

        # NASDAQ e OURO: funcionalidade nova via tabela (sem corte de produção)
        nasdaq_tab = benchmarks_tabela.get("NASDAQ", {})
        ouro_tab   = benchmarks_tabela.get("OURO", {})
        usdbrl_tab = benchmarks_tabela.get("USDBRL", {})

        ndx_base_brl = ouro_base_brl = None
        nasdaq_brl_acum_: list = []
        ouro_brl_acum_: list = []

        for d in df["data"]:
            usd = preco_em(usdbrl_tab, d) or preco_em(usdbrl, d)

            ndx_p = preco_em(nasdaq_tab, d)
            if ndx_p and usd:
                ndx_brl = ndx_p * usd
                if ndx_base_brl is None:
                    ndx_base_brl = ndx_brl
                nasdaq_brl_acum_.append(ndx_brl / ndx_base_brl - 1)
            else:
                nasdaq_brl_acum_.append(nasdaq_brl_acum_[-1] if nasdaq_brl_acum_ else 0.0)

            ouro_p = preco_em(ouro_tab, d)
            if ouro_p and usd:
                ouro_brl = ouro_p * usd
                if ouro_base_brl is None:
                    ouro_base_brl = ouro_brl
                ouro_brl_acum_.append(ouro_brl / ouro_base_brl - 1)
            else:
                ouro_brl_acum_.append(ouro_brl_acum_[-1] if ouro_brl_acum_ else 0.0)

        df["nasdaq_brl_acum"] = nasdaq_brl_acum_
        df["ouro_brl_acum"]   = ouro_brl_acum_

    except Exception as e:
        log.warning(f"benchmarks Fase A: erro (não crítico) — {e}")
        df["nasdaq_brl_acum"] = 0.0
        df["ouro_brl_acum"]   = 0.0

    return df
