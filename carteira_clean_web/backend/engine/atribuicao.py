"""
engine/atribuicao.py — Atribuição mensal (long format: mês × ativo).

Lógica copiada de calc_atribuicao_mensal() em atualizar_carteira.py.
Sem alteração de comportamento.
"""

from collections import defaultdict
from datetime import date

import pandas as pd

from .constantes import DATA_INICIO, COTIZADO_PUBLICO, AGREGADO_PRIVADO, COMPRAS, VENDAS
from .posicoes import Posicao
from .utils import preco_em, bdate_range

# Benchmark composto da IPS para o composite Gerida
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

    eventos_por_data = defaultdict(list)
    for ev in eventos:
        eventos_por_data[ev["data"]].append(ev)

    posicoes = defaultdict(Posicao)
    valores_diarios = {}

    def get_preco(tkr, d):
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")
        preco = None
        if familia in COTIZADO_PUBLICO and tkr in precos_pub:
            preco = preco_em(precos_pub[tkr], d)
        if preco is None:
            preco = preco_em(precos_man.get(tkr, {}), d, max_lookback_dias=60)
        return preco, familia

    for d in datas_uteis:
        for ev in eventos_por_data.get(d, []):
            tkr = ev["ativo"]
            tipo = ev["tipo"]
            p = posicoes[tkr]
            qtd = ev["qtd"] or 0
            valor = ev["valor"] or 0
            if tipo in COMPRAS or tipo == "CONTRIBUICAO":
                p.qtd += qtd
                p.custo_total += abs(valor)
            elif tipo in VENDAS and p.qtd > 1e-9:
                cm = p.custo_medio
                p.custo_total -= cm * qtd
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

    # patrimônio médio por (mes, composite) — usado para TOTAL_CARTEIRA ponderado
    pat_por_mes = {}  # {(mes_str, composite): float}

    for ano, mes in meses:
        mes_str = f"{ano}-{mes:02d}"
        dias_mes = [d for d in datas_uteis if d.year == ano and d.month == mes]
        if not dias_mes:
            continue
        d_ini = dias_mes[0]
        d_fim = dias_mes[-1]

        pat_medio_gerida = 0
        pat_medio_funcef = 0
        for d in dias_mes:
            pat_d_g = 0
            pat_d_f = 0
            for tkr in set(t for (_, t) in valores_diarios.keys()):
                composite = ativos.get(tkr, {}).get("composite", "Gerida")
                v = valores_diarios.get((d, tkr), 0)
                if composite == "FUNCEF":
                    pat_d_f += v
                else:
                    pat_d_g += v
            pat_medio_gerida += pat_d_g
            pat_medio_funcef += pat_d_f
        pat_medio_gerida /= len(dias_mes)
        pat_medio_funcef /= len(dias_mes)

        pat_por_mes[(mes_str, "Gerida")] = pat_medio_gerida
        pat_por_mes[(mes_str, "FUNCEF")] = pat_medio_funcef

        ativos_mes = set(t for d in dias_mes for (dt, t) in valores_diarios.keys() if dt == d)
        for tkr in sorted(ativos_mes):
            v_ini = valores_diarios.get((d_ini, tkr), 0)
            v_fim = valores_diarios.get((d_fim, tkr), 0)
            if v_ini == 0 and v_fim == 0:
                continue
            preco_ini, _ = get_preco(tkr, d_ini)
            preco_fim, _ = get_preco(tkr, d_fim)
            if preco_ini and preco_fim and preco_ini > 0:
                retorno = preco_fim / preco_ini - 1
            else:
                retorno = 0
            peso_medio = (v_ini + v_fim) / 2
            composite = ativos.get(tkr, {}).get("composite", "Gerida")
            denom = pat_medio_gerida if composite == "Gerida" else pat_medio_funcef
            peso_pct = peso_medio / denom if denom > 0 else 0
            contribuicao = retorno * peso_pct
            bench = ativos.get(tkr, {}).get("benchmark", "")
            bloco = ativos.get(tkr, {}).get("bloco_ips")
            linhas.append({
                "mes": mes_str,
                "composite": composite,
                "ativo": tkr,
                "retorno_ativo": retorno,
                "peso_medio": peso_pct,
                "contribuicao": contribuicao,
                "benchmark": bench,
                "bloco_ips": bloco,
            })

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
