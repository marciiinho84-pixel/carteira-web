"""
engine/brinson.py — Decomposição Brinson-Fachler por bloco IPS.

Para cada (mes, bloco_ips) da Gerida:
  efeito_alocacao = (w_real - w_alvo) × (R_bench_bloco - R_bench_total)
  efeito_selecao  = w_real × (R_real_bloco - R_bench_bloco)

Identidade contábil (válida quando FORA_IPS ≈ 0):
  sum(A + S para blocos IPS) ≈ R_real_Gerida − R_bench_total
"""

import logging
from datetime import date

import pandas as pd

from .constantes import DATA_INICIO
from .precos import carregar_benchmarks_da_tabela
from .utils import preco_em, bdate_range

logger = logging.getLogger(__name__)

_IPS_ALVOS = {
    "SWING_TRADE": 0.30,
    "GROWTH":      0.20,
    "DEFENSIVOS":  0.20,
    "RENDA_FIXA":  0.30,
}

_BENCH_BLOCO = {
    "SWING_TRADE": "IBOV",
    "GROWTH":      "NASDAQ_BRL",
    "DEFENSIVOS":  "OURO_BRL",
    "RENDA_FIXA":  "CDI",
}


def _retornos_mensais(benchmarks: dict, mes_str: str, datas_uteis: list, idx_map: dict) -> dict:
    """Retornos mensais de CDI, IBOV, NasdaqBRL e OuroBRL para o mês mes_str."""
    ano, mes = int(mes_str[:4]), int(mes_str[5:7])
    dias_mes = [d for d in datas_uteis if d.year == ano and d.month == mes]
    if not dias_mes:
        return {"CDI": 0.0, "IBOV": 0.0, "NASDAQ_BRL": 0.0, "OURO_BRL": 0.0}

    d_ini = dias_mes[0]
    d_fim = dias_mes[-1]

    # Preço de referência inicial = fechamento do último dia útil do mês anterior
    ini_idx = idx_map.get(d_ini, 0)
    d_ref_ini = datas_uteis[ini_idx - 1] if ini_idx > 0 else d_ini

    cdi    = benchmarks.get("CDI",    {})
    ibov   = benchmarks.get("IBOV",   {})
    usdbrl = benchmarks.get("USDBRL", {})
    nasdaq = benchmarks.get("NASDAQ", {})
    ouro   = benchmarks.get("OURO",   {})

    # CDI: produto das taxas diárias do mês
    r_cdi = 1.0
    for d in dias_mes:
        r_cdi *= (1 + cdi.get(d, 0.0))
    r_cdi -= 1

    # IBOV: retorno preço
    p_ibov_ini = preco_em(ibov, d_ref_ini)
    p_ibov_fim = preco_em(ibov, d_fim)
    r_ibov = (p_ibov_fim / p_ibov_ini - 1) if (p_ibov_ini and p_ibov_fim) else 0.0

    # USD/BRL (para converter benchmarks em USD → BRL)
    usd_ini = preco_em(usdbrl, d_ref_ini)
    usd_fim = preco_em(usdbrl, d_fim)

    def _brl_return(price_dict):
        p_ini = preco_em(price_dict, d_ref_ini)
        p_fim = preco_em(price_dict, d_fim)
        if p_ini and p_fim and usd_ini and usd_fim:
            return (p_fim * usd_fim) / (p_ini * usd_ini) - 1
        return 0.0

    r_ndx_brl  = _brl_return(nasdaq)
    r_ouro_brl = _brl_return(ouro)

    if not (p_ibov_ini and p_ibov_fim):
        logger.warning("brinson %s: IBOV sem preço — benchmark zerando", mes_str)
    if not (usd_ini and usd_fim):
        logger.warning("brinson %s: USDBRL sem preço — NasdaqBRL/OuroBRL zerando", mes_str)

    return {
        "CDI":        r_cdi,
        "IBOV":       r_ibov,
        "NASDAQ_BRL": r_ndx_brl,
        "OURO_BRL":   r_ouro_brl,
    }


def calc_brinson_fachler(
    df_atrib: pd.DataFrame,
    data_fim: date = None,
) -> pd.DataFrame:
    """Decomposição Brinson-Fachler por bloco IPS, mês a mês.

    Parâmetros
    ----------
    df_atrib  : DataFrame de atribuição mensal (output de calc_atribuicao_mensal).
    data_fim  : data limite para bdate_range (default: date.today()).

    Retorna DataFrame com colunas:
      mes, bloco_ips, w_real, w_alvo, R_real_bloco, R_bench_bloco, R_bench_total,
      efeito_alocacao, efeito_selecao
    """
    if df_atrib is None or df_atrib.empty:
        return pd.DataFrame()

    datas_uteis = bdate_range(DATA_INICIO, data_fim or date.today())
    if not datas_uteis:
        return pd.DataFrame()
    idx_map = {d: i for i, d in enumerate(datas_uteis)}

    benchmarks = carregar_benchmarks_da_tabela()

    meses = sorted(df_atrib["mes"].unique())
    linhas = []

    for mes_str in meses:
        r_bench = _retornos_mensais(benchmarks, mes_str, datas_uteis, idx_map)
        r_cdi       = r_bench["CDI"]
        r_ibov      = r_bench["IBOV"]
        r_ndx_brl   = r_bench["NASDAQ_BRL"]
        r_ouro_brl  = r_bench["OURO_BRL"]

        # Benchmark composto IPS (pesos = alvos)
        r_bench_total = (
            _IPS_ALVOS["SWING_TRADE"] * r_ibov
            + _IPS_ALVOS["GROWTH"]      * r_ndx_brl
            + _IPS_ALVOS["DEFENSIVOS"]  * r_ouro_brl
            + _IPS_ALVOS["RENDA_FIXA"]  * r_cdi
        )

        # Benchmark por bloco
        r_bench_por_bloco = {
            "SWING_TRADE": r_ibov,
            "GROWTH":      r_ndx_brl,
            "DEFENSIVOS":  r_ouro_brl,
            "RENDA_FIXA":  r_cdi,
        }

        # Dados individuais Gerida neste mês
        df_mes = df_atrib[
            (df_atrib["mes"] == mes_str)
            & (df_atrib["composite"] == "Gerida")
            & (df_atrib["ativo"] != "TOTAL")
        ]

        # Retorno real da Gerida (linha TOTAL)
        tot = df_atrib[
            (df_atrib["mes"] == mes_str)
            & (df_atrib["composite"] == "Gerida")
            & (df_atrib["ativo"] == "TOTAL")
        ]
        R_real_gerida = float(tot.iloc[0]["contribuicao"]) if not tot.empty else 0.0

        soma_A = 0.0
        soma_S = 0.0

        for bloco, w_alvo in _IPS_ALVOS.items():
            df_bloco = df_mes[df_mes["bloco_ips"] == bloco]

            w_real       = float(df_bloco["peso_medio"].sum())
            contrib_bloco = float(df_bloco["contribuicao"].sum())
            R_real_bloco  = contrib_bloco / w_real if w_real > 1e-9 else 0.0
            R_bench_b     = r_bench_por_bloco[bloco]

            A = (w_real - w_alvo) * (R_bench_b - r_bench_total)
            S = w_real * (R_real_bloco - R_bench_b)

            soma_A += A
            soma_S += S

            linhas.append({
                "mes":             mes_str,
                "bloco_ips":       bloco,
                "w_real":          w_real,
                "w_alvo":          w_alvo,
                "R_real_bloco":    R_real_bloco,
                "R_bench_bloco":   R_bench_b,
                "R_bench_total":   r_bench_total,
                "efeito_alocacao": A,
                "efeito_selecao":  S,
            })

        # Validação da identidade contábil
        excesso_real = R_real_gerida - r_bench_total
        soma_BF      = soma_A + soma_S
        diff = abs(soma_BF - excesso_real)
        if diff > 0.0005:
            logger.warning(
                "brinson %s: soma_BF=%.4f excesso_real=%.4f diff=%.4f"
                " (possível residual FORA_IPS)",
                mes_str, soma_BF * 100, excesso_real * 100, diff * 100,
            )

        # Linha TOTAL por mês
        linhas.append({
            "mes":             mes_str,
            "bloco_ips":       "TOTAL",
            "w_real":          1.0,
            "w_alvo":          1.0,
            "R_real_bloco":    R_real_gerida,
            "R_bench_bloco":   r_bench_total,
            "R_bench_total":   r_bench_total,
            "efeito_alocacao": soma_A,
            "efeito_selecao":  soma_S,
        })

    return pd.DataFrame(linhas)
