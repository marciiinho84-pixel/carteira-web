"""
engine/ir_mensal.py — Estimativa de IR mensal sobre vendas de RV.

Regras aplicadas (Lei 11.033 / IN RFB 1.585):
  Pool "Comum" = Ação BR + BDR + BDR de ETF + ETF BR (mesmo pool p/ compensação)
  Isenção mensal: apenas se TODOS os vendas do mês forem Ação BR E
                  volume total < R$ 20.000
  Alíquota: 15% sobre lucro tributável após compensação de prejuízos anteriores
  DARF Código 6015 — só gera se IR calculado > R$ 10,00
  Vencimento DARF: último dia útil do mês seguinte
"""

from collections import defaultdict
from datetime import date
from typing import Any

import pandas as pd

ALIQUOTA = 0.15
LIMITE_ISENCAO = 20_000.0
MINIMO_DARF = 10.0

# Famílias elegíveis para ISENÇÃO de R$20k (apenas Ação BR)
FAMILIA_ISENCAO = {"Ação BR"}
# Famílias RV tributáveis (não elegíveis para isenção, mas participam do pool)
FAMILIA_TRIBUTAVEL = {"BDR", "BDR de ETF", "ETF BR"}
FAMILIA_RV = FAMILIA_ISENCAO | FAMILIA_TRIBUTAVEL


def calc_ir_mensal(vendas_rv: list[dict], ativos: dict[str, Any]) -> list[dict]:
    """Calcula IR mensal estimado sobre vendas de RV.

    Args:
        vendas_rv: lista de vendas do engine (cada item tem data, ticker, pnl, valor_recebido)
        ativos: dict {ticker: info} para obter familia

    Returns:
        Lista de dicts por mês, ordenada cronologicamente:
        [{mes, volume_vendas, lucro_bruto, is_isento, prejudizo_compensado,
          lucro_tributavel, ir_devido, prejudizo_acumulado, status,
          darf_codigo, darf_vencimento, gera_darf, tickers_vendidos}]
    """
    # Agrupar vendas por mês
    por_mes: dict[str, list] = defaultdict(list)
    for v in vendas_rv:
        d = v["data"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        mes_key = d.strftime("%Y-%m")
        por_mes[mes_key].append({**v, "_data_obj": d})

    prejudizo_acumulado = 0.0
    resultado = []

    for mes in sorted(por_mes.keys()):
        vendas_mes = por_mes[mes]

        familias_mes = {ativos.get(v["ticker"], {}).get("familia", "") for v in vendas_mes}
        familias_rv_mes = familias_mes & FAMILIA_RV

        volume_vendas = sum(v["valor_recebido"] for v in vendas_mes)
        lucro_bruto = sum(max(0.0, v["pnl"]) for v in vendas_mes)
        prejuizo_mes = sum(min(0.0, v["pnl"]) for v in vendas_mes)

        # Isenção: todas Ação BR e volume < R$20k
        tem_nao_isento = bool(familias_rv_mes & FAMILIA_TRIBUTAVEL)
        is_isento = (not tem_nao_isento) and (volume_vendas < LIMITE_ISENCAO)

        if is_isento:
            # Prejuízos do mês isento NÃO compensam (não entram no pool tributável)
            ir_devido = 0.0
            prejudizo_compensado = 0.0
            lucro_tributavel = 0.0
            # Mas o prejuízo do mês isento PODE ser adicionado ao acumulado?
            # Conservador: não adiciona (isenção = fora do pool IR)
        else:
            # Lucro tributável = lucro bruto menos prejuízo acumulado anterior
            lucro_tributavel = lucro_bruto
            if prejudizo_acumulado > 0 and lucro_tributavel > 0:
                prejudizo_compensado = min(prejudizo_acumulado, lucro_tributavel)
                lucro_tributavel -= prejudizo_compensado
                prejudizo_acumulado -= prejudizo_compensado
            else:
                prejudizo_compensado = 0.0

            ir_devido = round(ALIQUOTA * lucro_tributavel, 2)

            # Prejuízo do mês aumenta o saldo acumulado
            if prejuizo_mes < 0:
                prejudizo_acumulado += abs(prejuizo_mes)

            # Se lucro tributável não cobre o IR mínimo, não gera DARF
            # (mas os prejuízos ainda acumulam e lucro < compensação → aumenta acumulado)
            if ir_devido == 0.0 and lucro_tributavel < 0:
                prejudizo_acumulado += abs(lucro_tributavel)

        status = "ISENTO" if is_isento else ("TRIBUTÁVEL" if ir_devido > 0 else "SEM LUCRO")
        gera_darf = (not is_isento) and (ir_devido >= MINIMO_DARF)
        darf_vencimento = _ultimo_du_mes_seguinte(mes) if gera_darf else None

        resultado.append({
            "mes": mes,
            "volume_vendas": round(volume_vendas, 2),
            "lucro_bruto": round(lucro_bruto, 2),
            "is_isento": is_isento,
            "prejudizo_compensado": round(prejudizo_compensado, 2),
            "lucro_tributavel": round(lucro_tributavel, 2),
            "ir_devido": ir_devido,
            "prejudizo_acumulado": round(prejudizo_acumulado, 2),
            "status": status,
            "gera_darf": gera_darf,
            "darf_codigo": "6015" if gera_darf else None,
            "darf_vencimento": str(darf_vencimento) if darf_vencimento else None,
            "tickers_vendidos": sorted({v["ticker"] for v in vendas_mes}),
        })

    return resultado


def _ultimo_du_mes_seguinte(mes_yyyymm: str) -> date:
    """Retorna o último dia útil do mês seguinte ao mes_yyyymm."""
    ano, mes = int(mes_yyyymm[:4]), int(mes_yyyymm[5:])
    if mes == 12:
        ano += 1
        mes = 1
    else:
        mes += 1
    # Fim do mês
    if mes == 12:
        fim = date(ano + 1, 1, 1) - pd.Timedelta(days=1)
    else:
        fim = date(ano, mes + 1, 1) - pd.Timedelta(days=1)
    # Último dia útil
    dus = pd.bdate_range(end=fim, periods=1)
    return dus[0].date()
