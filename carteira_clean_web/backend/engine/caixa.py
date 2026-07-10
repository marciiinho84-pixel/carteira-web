"""
engine/caixa.py — Caixa derivado da Carteira Gerida (partida dobrada na projeção).

Não é uma conta persistida: é reconstruído a cada cálculo a partir do próprio
event log, para que COMPRA/VENDA (movimentações internas, financiadas pelo
caixa) deixem de vazar como retorno no TWR. Nenhum ticker é caso especial —
CAIXA FIC FUNC participa da partida dobrada como qualquer outro ativo.
"""

from collections import defaultdict
from datetime import date

from .constantes import COMPRAS, VENDAS, PROVENTOS, FLUXOS_EXTERNOS


def delta_caixa_evento(ev: dict, ativos: dict) -> float:
    """Variação de caixa (perímetro Gerida) produzida por 1 evento; 0.0 se irrelevante."""
    tipo = ev["tipo"]
    valor = abs(ev["valor"] or 0)
    composite = ativos.get(ev["ativo"], {}).get("composite", "Gerida")

    if composite == "FUNCEF":
        return 0.0
    if tipo == "SALDO_INICIAL":
        return 0.0
    if tipo == "BONIFICACAO":
        return 0.0
    if tipo in FLUXOS_EXTERNOS:
        sinal = 1 if tipo == "APORTE_EXTERNO" else -1
        return sinal * valor
    if tipo in COMPRAS:
        return -valor
    if tipo in VENDAS:
        return valor
    if tipo in PROVENTOS:
        return valor
    return 0.0


def calc_saldo_caixa_diario(
    eventos: list, ativos: dict, datas: list, aportes_inferidos: list = None
) -> dict:
    """Replay standalone {data: saldo_caixa_acumulado} — uso em testes/debug.

    Espelha o wiring real (eventos + aportes_inferidos), mas não faz o rollover
    de fim de semana/feriado — assume que as datas dos eventos já estão no
    conjunto `datas` (essa lógica vive só em twr.calc_evolucao_diaria).
    """
    aportes_por_data = defaultdict(float)
    for ap in aportes_inferidos or []:
        aportes_por_data[ap["data"]] += ap["valor"]

    eventos_por_data = defaultdict(list)
    for ev in eventos:
        eventos_por_data[ev["data"]].append(ev)

    saldo = 0.0
    resultado = {}
    for d in datas:
        for ev in eventos_por_data.get(d, []):
            saldo += delta_caixa_evento(ev, ativos)
        saldo += aportes_por_data.get(d, 0.0)
        resultado[d] = saldo
    return resultado
