"""
engine/caixa.py — Caixa derivado da Carteira Gerida (partida dobrada na projeção).

Não é uma conta persistida: é reconstruído a cada cálculo a partir do próprio
event log, para que COMPRA/VENDA (movimentações internas, financiadas pelo
caixa) deixem de vazar como retorno no TWR. Nenhum ticker é caso especial —
CAIXA FIC FUNC participa da partida dobrada como qualquer outro ativo.
"""

from collections import defaultdict
from datetime import date

from .constantes import COMPRAS, VENDAS, PROVENTOS, FLUXOS_EXTERNOS, COTIZADO_PRIVADO
from .utils import preco_em


def delta_caixa_evento(ev: dict, ativos: dict, precos_manuais: dict, data) -> float:
    """Variação de caixa (perímetro Gerida) produzida por 1 evento; 0.0 se irrelevante.

    APORTE_EXTERNO/RESGATE_EXTERNO cujo ticker é um ativo que o replay de
    twr.py TAMBÉM processa como perna de posição não credita/debita caixa
    aqui — a perna de posição já é o único efeito, senão dobra a contagem.
    Hoje isso só se aplica a APORTE_EXTERNO em ticker COTIZADO_PRIVADO com
    cota disponível na mesma data (mesma condição de twr.py:79-82) — é a
    única situação em que o replay compra algo via APORTE_EXTERNO.
    RESGATE_EXTERNO não tem nenhuma perna de posição em lugar nenhum do
    engine hoje, então continua sempre debitando caixa.
    """
    tipo = ev["tipo"]
    valor = abs(ev["valor"] or 0)
    tkr = ev["ativo"]
    composite = ativos.get(tkr, {}).get("composite", "Gerida")

    if composite == "FUNCEF":
        return 0.0
    if tipo == "SALDO_INICIAL":
        return 0.0
    if tipo == "BONIFICACAO":
        return 0.0
    if tipo in FLUXOS_EXTERNOS:
        if tipo == "APORTE_EXTERNO":
            familia = ativos.get(tkr, {}).get("familia", "")
            if familia in COTIZADO_PRIVADO:
                cota = preco_em(precos_manuais.get(tkr, {}), data)
                if cota and cota > 0 and valor > 0:
                    return 0.0
            return valor
        return -valor
    if tipo in COMPRAS:
        return -valor
    if tipo in VENDAS:
        return valor
    if tipo in PROVENTOS:
        return valor
    return 0.0


def calc_saldo_caixa_diario(
    eventos: list, ativos: dict, datas: list,
    precos_manuais: dict = None, aportes_inferidos: list = None,
) -> dict:
    """Replay standalone {data: saldo_caixa_acumulado} — uso em testes/debug.

    Espelha o wiring real (eventos + aportes_inferidos), mas não faz o rollover
    de fim de semana/feriado — assume que as datas dos eventos já estão no
    conjunto `datas` (essa lógica vive só em twr.calc_evolucao_diaria).
    """
    precos_manuais = precos_manuais or {}
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
            saldo += delta_caixa_evento(ev, ativos, precos_manuais, d)
        saldo += aportes_por_data.get(d, 0.0)
        resultado[d] = saldo
    return resultado
