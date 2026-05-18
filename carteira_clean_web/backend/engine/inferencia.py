"""
engine/inferencia.py — Inferência de fluxos externos retroativos (caixa virtual).

Lógica copiada literalmente de inferir_fluxos_externos_retroativos()
em atualizar_carteira.py. Sem alteração de comportamento.
"""

from datetime import date, timedelta

from .constantes import (
    DATA_CAIXA_TRANSICAO,
    COTIZADO_PUBLICO,
    AGREGADO_PRIVADO,
    PROVENTOS,
)


def _data_efetiva_retroativa(ev: dict) -> date:
    """Antecipa eventos AGREGADO para o 1º dia útil do mês."""
    obs = str(ev.get("obs") or "")
    if "AGREGADO" in obs:
        d = ev["data"]
        primeiro_dia_mes = date(d.year, d.month, 1)
        while primeiro_dia_mes.weekday() >= 5:
            primeiro_dia_mes += timedelta(days=1)
        return primeiro_dia_mes
    return ev["data"]


def inferir_fluxos_externos_retroativos(
    eventos: list,
    ativos: dict,
    data_corte: date = DATA_CAIXA_TRANSICAO,
) -> tuple[list, float]:
    """
    Mantém caixa virtual da Carteira Gerida e infere APORTE_EXTERNO
    sempre que uma compra não tem cobertura de caixa.

    Returns: (lista_aportes_inferidos, saldo_residual)
    """
    saldo_virtual = 0.0
    aportes_inferidos = []

    eventos_ajustados = []
    for ev in eventos:
        ev_copy = dict(ev)
        ev_copy["_data_efetiva"] = _data_efetiva_retroativa(ev)
        eventos_ajustados.append(ev_copy)
    eventos_ajustados.sort(key=lambda e: (e["_data_efetiva"], e["linha"]))

    for ev in eventos_ajustados:
        d_efetiva = ev["_data_efetiva"]
        if d_efetiva >= data_corte:
            continue
        tkr = ev["ativo"]
        tipo = ev["tipo"]
        valor = abs(ev["valor"] or 0)
        familia = ativos.get(tkr, {}).get("familia", "")
        composite = ativos.get(tkr, {}).get("composite", "Gerida")

        if composite == "FUNCEF":
            continue
        if tipo == "SALDO_INICIAL":
            continue

        if tipo == "VENDA" and familia in COTIZADO_PUBLICO:
            saldo_virtual += valor
        elif tipo == "VENDA" and tkr == "CAIXA FIC FUNC":
            saldo_virtual += valor
        elif tipo in PROVENTOS and familia in COTIZADO_PUBLICO:
            saldo_virtual += valor
        elif tipo == "RENDIMENTO" and familia in AGREGADO_PRIVADO:
            pass
        elif tipo == "COMPRA" and familia in COTIZADO_PUBLICO:
            if saldo_virtual < valor:
                falta = valor - saldo_virtual
                aportes_inferidos.append({
                    "data": d_efetiva,
                    "valor": falta,
                    "motivo": f"COMPRA {tkr} R$ {valor:,.2f}",
                })
                saldo_virtual = 0
            else:
                saldo_virtual -= valor
        elif tipo == "COMPRA" and tkr == "CAIXA FIC FUNC":
            if saldo_virtual < valor:
                falta = valor - saldo_virtual
                aportes_inferidos.append({
                    "data": d_efetiva,
                    "valor": falta,
                    "motivo": f"APLICAÇÃO {tkr} R$ {valor:,.2f}",
                })
                saldo_virtual = 0
            else:
                saldo_virtual -= valor
        elif tipo == "COMPRA" and familia == "Tesouro Direto":
            if saldo_virtual < valor:
                falta = valor - saldo_virtual
                aportes_inferidos.append({
                    "data": d_efetiva,
                    "valor": falta,
                    "motivo": f"COMPRA {tkr} R$ {valor:,.2f}",
                })
                saldo_virtual = 0
            else:
                saldo_virtual -= valor

    return aportes_inferidos, saldo_virtual
