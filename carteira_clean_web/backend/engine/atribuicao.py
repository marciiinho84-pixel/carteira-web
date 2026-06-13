"""
engine/atribuicao.py — Atribuição mensal (long format: mês × ativo).

Modelo: contribuição diária ponderada no tempo.
  contribuicao_d = peso_d × retorno_d
  peso_d         = valor_{d-1, tkr} / patrimônio_composite_{d-1}
  retorno_d      = preco_exec / preco_{d-1} (dias de venda)
                 | preco_d   / preco_{d-1} (demais dias)

Convenção de trade:
  VENDA  no dia d → retorno usa preco de execução (pmp das vendas do dia)
  COMPRA no dia d → posição nova começa a contribuir em d+1
                    (v_{d-1} não inclui as novas cotas, naturalmente)
"""

import logging
from collections import defaultdict
from datetime import date

import pandas as pd

from .constantes import DATA_INICIO, COTIZADO_PUBLICO, AGREGADO_PRIVADO, COMPRAS, VENDAS
from .posicoes import Posicao
from .utils import preco_em, bdate_range

logger = logging.getLogger(__name__)

_BENCH_GERIDA = "30%IBOV+20%NasdaqBRL+20%OuroBRL+30%CDI"
_BENCH_FUNCEF = "CDI"


def calc_atribuicao_mensal(
    eventos: list,
    ativos: dict,
    precos_pub: dict,
    precos_man: dict,
    data_fim: date,
) -> pd.DataFrame:
    linhas = []
    datas_uteis = bdate_range(DATA_INICIO, data_fim)
    if not datas_uteis:
        return pd.DataFrame()

    meses = sorted(set((d.year, d.month) for d in datas_uteis))
    idx_map = {d: i for i, d in enumerate(datas_uteis)}

    eventos_por_data = defaultdict(list)
    for ev in eventos:
        eventos_por_data[ev["data"]].append(ev)

    posicoes = defaultdict(Posicao)
    valores_diarios: dict = {}   # {(d, tkr): float}
    preco_exec: dict = {}        # {(d, tkr): float} — pmp das vendas no dia

    def get_preco(tkr, d):
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")
        preco = None
        if familia in COTIZADO_PUBLICO and tkr in precos_pub:
            preco = preco_em(precos_pub[tkr], d)
        if preco is None:
            preco = preco_em(precos_man.get(tkr, {}), d, max_lookback_dias=60)
        return preco, familia

    # ── Passe 1: replay eventos → valores_diarios e preco_exec ──────────────
    for d in datas_uteis:
        evs_d = eventos_por_data.get(d, [])

        # Preço médio ponderado das vendas (pmp) neste dia
        venda_qtd: dict = defaultdict(float)
        venda_vlr: dict = defaultdict(float)
        for ev in evs_d:
            if ev["tipo"] in VENDAS:
                qtd = ev["qtd"] or 0
                vlr = abs(ev["valor"] or 0)
                if qtd > 0:
                    venda_qtd[ev["ativo"]] += qtd
                    venda_vlr[ev["ativo"]] += vlr
        for tkr, qtd_total in venda_qtd.items():
            if qtd_total > 0:
                preco_exec[(d, tkr)] = venda_vlr[tkr] / qtd_total

        # Atualizar posições
        for ev in evs_d:
            tkr = ev["ativo"]
            tipo = ev["tipo"]
            p = posicoes[tkr]
            qtd = ev["qtd"] or 0
            valor = ev["valor"] or 0
            if tipo in COMPRAS or tipo == "CONTRIBUICAO":
                p.qtd += qtd
                p.custo_total += abs(valor)
            elif tipo in VENDAS and p.qtd > 1e-9:
                p.custo_total -= p.custo_medio * qtd
                p.qtd -= qtd
                if abs(p.qtd) < 1e-6:
                    p.qtd = 0.0
                    p.custo_total = 0.0

        for tkr, p in posicoes.items():
            preco, familia = get_preco(tkr, d)
            if familia in AGREGADO_PRIVADO:
                valor_pos = preco if preco else 0
            elif p.qtd > 1e-9:
                valor_pos = p.qtd * preco if preco else p.custo_total
            else:
                continue
            valores_diarios[(d, tkr)] = valor_pos

    # ── Pré-computar patrimônio diário por composite ─────────────────────────
    all_tkrs = set(t for (_, t) in valores_diarios)
    tkr_composite = {tkr: ativos.get(tkr, {}).get("composite", "Gerida") for tkr in all_tkrs}

    pat_comp_daily: dict = {}
    for d in datas_uteis:
        for comp in ("Gerida", "FUNCEF"):
            pat_comp_daily[(d, comp)] = sum(
                valores_diarios.get((d, t), 0.0)
                for t in all_tkrs if tkr_composite.get(t) == comp
            )

    # ── Patrimônio médio por (mes, composite) ────────────────────────────────
    pat_por_mes: dict = {}
    for ano, mes in meses:
        mes_str = f"{ano}-{mes:02d}"
        dias_mes = [d for d in datas_uteis if d.year == ano and d.month == mes]
        if not dias_mes:
            continue
        for comp in ("Gerida", "FUNCEF"):
            pat_por_mes[(mes_str, comp)] = (
                sum(pat_comp_daily.get((d, comp), 0.0) for d in dias_mes) / len(dias_mes)
            )

    # ── Passe 2: contribuição diária por ativo por mês ───────────────────────
    for ano, mes in meses:
        mes_str = f"{ano}-{mes:02d}"
        dias_mes = [d for d in datas_uteis if d.year == ano and d.month == mes]
        if not dias_mes:
            continue

        ativos_mes = set(t for d in dias_mes for (dt, t) in valores_diarios if dt == d)

        for tkr in sorted(ativos_mes):
            composite = tkr_composite.get(tkr, "Gerida")

            contribuicao_total = 0.0
            retorno_composto = 1.0
            soma_pesos = 0.0
            n_dias = len(dias_mes)

            for d in dias_mes:
                d_idx = idx_map[d]
                if d_idx == 0:
                    # Primeiro dia útil de todo o histórico — sem d-1
                    continue
                d_ant = datas_uteis[d_idx - 1]

                v_ant = valores_diarios.get((d_ant, tkr), 0.0)
                if v_ant <= 0:
                    continue  # sem posição em d-1 → peso zero, contribuição zero

                pat_comp_ant = pat_comp_daily.get((d_ant, composite), 0.0)
                peso_d = v_ant / pat_comp_ant if pat_comp_ant > 0 else 0.0

                # Retorno do dia: execução em VENDA, mercado nos demais
                if (d, tkr) in preco_exec:
                    p_ant, _ = get_preco(tkr, d_ant)
                    if p_ant and p_ant > 0:
                        retorno_d = preco_exec[(d, tkr)] / p_ant - 1
                    else:
                        retorno_d = 0.0
                else:
                    p_d, _ = get_preco(tkr, d)
                    p_ant, _ = get_preco(tkr, d_ant)
                    if p_d and p_ant and p_ant > 0:
                        retorno_d = p_d / p_ant - 1
                    else:
                        retorno_d = 0.0

                contribuicao_total += peso_d * retorno_d
                retorno_composto *= (1 + retorno_d)
                soma_pesos += peso_d

            retorno_ativo = retorno_composto - 1
            peso_medio = soma_pesos / n_dias if n_dias > 0 else 0.0

            if contribuicao_total == 0.0 and peso_medio == 0.0:
                continue

            linhas.append({
                "mes": mes_str,
                "composite": composite,
                "ativo": tkr,
                "retorno_ativo": retorno_ativo,
                "peso_medio": peso_medio,
                "contribuicao": contribuicao_total,
                "benchmark": ativos.get(tkr, {}).get("benchmark", ""),
                "bloco_ips": ativos.get(tkr, {}).get("bloco_ips"),
            })

        # Validação: soma contribuições ≈ retorno do composite (estimado sem fluxos)
        linhas_mes = [l for l in linhas if l["mes"] == mes_str]
        if linhas_mes:
            df_chk = pd.DataFrame(linhas_mes)
            for comp in ("Gerida", "FUNCEF"):
                soma = df_chk[df_chk["composite"] == comp]["contribuicao"].sum()
                ret_comp = 1.0
                for d in dias_mes:
                    d_idx = idx_map[d]
                    if d_idx == 0:
                        continue
                    d_ant = datas_uteis[d_idx - 1]
                    p_d = pat_comp_daily.get((d, comp), 0.0)
                    p_ant = pat_comp_daily.get((d_ant, comp), 0.0)
                    if p_ant > 0:
                        ret_comp *= p_d / p_ant
                ret_comp -= 1
                if abs(soma - ret_comp) > 0.0005:
                    logger.warning(
                        "atribuicao %s/%s: soma_contrib=%.4f twr_aprox=%.4f diff=%.4f",
                        mes_str, comp, soma, ret_comp, abs(soma - ret_comp),
                    )

    # ── Linhas TOTAL por (mes, composite) e TOTAL_CARTEIRA por mes ──────────
    if linhas:
        df_ind = pd.DataFrame(linhas)

        for (mes_str, composite), grp in df_ind.groupby(["mes", "composite"]):
            contr = grp["contribuicao"].sum()
            bench = _BENCH_FUNCEF if composite == "FUNCEF" else _BENCH_GERIDA
            linhas.append({
                "mes": mes_str,
                "composite": composite,
                "ativo": "TOTAL",
                "retorno_ativo": contr,
                "peso_medio": 1.0,
                "contribuicao": contr,
                "benchmark": bench,
                "bloco_ips": None,
            })

        for mes_str, grp in df_ind.groupby("mes"):
            pat_g = pat_por_mes.get((mes_str, "Gerida"), 0.0)
            pat_f = pat_por_mes.get((mes_str, "FUNCEF"), 0.0)
            pat_total = pat_g + pat_f
            ret_g = grp[grp["composite"] == "Gerida"]["contribuicao"].sum()
            ret_f = grp[grp["composite"] == "FUNCEF"]["contribuicao"].sum()
            if pat_total > 0:
                retorno_carteira = (ret_g * pat_g + ret_f * pat_f) / pat_total
            else:
                retorno_carteira = ret_g + ret_f
            linhas.append({
                "mes": mes_str,
                "composite": "TOTAL_CARTEIRA",
                "ativo": "TOTAL",
                "retorno_ativo": retorno_carteira,
                "peso_medio": 1.0,
                "contribuicao": retorno_carteira,
                "benchmark": _BENCH_GERIDA,
                "bloco_ips": None,
            })

    return pd.DataFrame(linhas)
