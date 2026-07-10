"""
engine/validacao.py — Validação ativa (7 tipos de alertas).

Lógica copiada de validar() em atualizar_carteira.py. Sem alteração.
"""

import re
import pandas as pd
from datetime import date
from collections import defaultdict

from .constantes import COTIZADO_PUBLICO, DATA_CAIXA_TRANSICAO


def validar(posicoes: dict, eventos: list, ativos: dict, df_evo: pd.DataFrame) -> list:
    alertas = []

    for tkr, p in posicoes.items():
        # Tolerância de -0.01 (não -1e-6) para engolir poeira de arredondamento
        # de ponto flutuante em resgates/zeramentos totais (ex.: PEPS com muitas
        # compras/vendas pequenas), sem perder a checagem real de VENDA > COMPRA.
        if p.qtd < -0.01:
            alertas.append(("ERRO", tkr, f"Posição negativa ({p.qtd:.4f}) — VENDAs > COMPRAs"))

    ativos_eventos = set(e["ativo"] for e in eventos)
    nao_cadastrados = ativos_eventos - set(ativos.keys())
    for tkr in nao_cadastrados:
        alertas.append(("AVISO", tkr, "Aparece em EVENTOS mas não está cadastrado em CAD_ATIVOS"))

    if not df_evo.empty:
        ultimo = df_evo.iloc[-1]
        pat_gerida = ultimo["patrimonio_gerida"]
        if pat_gerida > 0:
            for tkr, p in posicoes.items():
                if p.qtd < 1e-9:
                    continue
                info = ativos.get(tkr, {})
                if info.get("composite") != "Gerida":
                    continue
                pct = p.custo_total / pat_gerida
                if pct > 0.15:
                    alertas.append(("AVISO", tkr, f"Concentração {pct*100:.1f}% > 15% na Carteira Gerida"))

    hoje = date.today()
    for ev in eventos:
        obs = ev.get("obs") or ""
        if "PENDENTE LIQUIDAÇÃO" in obs:
            # Extrair data de liquidação do formato "→ DD/MM" e só alertar se ainda não venceu
            m = re.search(r"→\s*(\d{2}/\d{2})", obs)
            if m:
                dia, mes = map(int, m.group(1).split("/"))
                ano = hoje.year if (mes, dia) >= (hoje.month, hoje.day) else hoje.year
                try:
                    data_liq = date(ano, mes, dia)
                    if hoje <= data_liq:
                        alertas.append(("INFO", ev["ativo"], f"Evento de {ev['data']} pendente liquidação"))
                except ValueError:
                    pass  # data inválida — ignorar
            else:
                # sem data explícita: alertar sempre
                alertas.append(("INFO", ev["ativo"], f"Evento de {ev['data']} pendente liquidação"))

    return alertas


def validar_saldo_caixa_negativo(
    df_evo: pd.DataFrame, data_a_partir: date = DATA_CAIXA_TRANSICAO
) -> list:
    """Alerta (ERRO) se o caixa derivado ficar negativo em algum dia >= data_a_partir.

    Nunca corrige/clampa o valor — só sinaliza. Pré-transição é contabilmente
    incompleto por natureza e fica de fora.
    """
    alertas = []
    if df_evo.empty or "caixa" not in df_evo.columns:
        return alertas

    df_periodo = df_evo[df_evo["data"] >= data_a_partir]
    negativos = df_periodo[df_periodo["caixa"] < -0.01]
    if negativos.empty:
        return alertas

    pior = negativos.loc[negativos["caixa"].idxmin()]
    alertas.append((
        "ERRO", "CAIXA",
        f"Saldo de caixa derivado negativo em {len(negativos)} dia(s) desde "
        f"{data_a_partir} — pior caso: R$ {pior['caixa']:,.2f} em {pior['data']} "
        f"(indica evento faltante no log, ex. APORTE_EXTERNO/RESGATE_EXTERNO)",
    ))
    return alertas
