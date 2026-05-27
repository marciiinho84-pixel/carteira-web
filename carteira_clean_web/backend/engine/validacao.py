"""
engine/validacao.py — Validação ativa (7 tipos de alertas).

Lógica copiada de validar() em atualizar_carteira.py. Sem alteração.
"""

import re
import pandas as pd
from datetime import date
from collections import defaultdict

from .constantes import COTIZADO_PUBLICO


SALDO_REAL_FIC_FUNC = 2450.48  # reportado pelo user em 16/05/2026


def validar(posicoes: dict, eventos: list, ativos: dict, df_evo: pd.DataFrame) -> list:
    alertas = []

    for tkr, p in posicoes.items():
        if p.qtd < -1e-6:
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
        if "AGREGADO" in obs:
            alertas.append(("INFO", ev["ativo"], "Evento agregado provisório"))

    return alertas


def validar_reconciliacao_caixa(saldo_residual: float) -> tuple:
    """Adiciona alerta de reconciliação caixa virtual vs. saldo real."""
    desvio = abs(saldo_residual - SALDO_REAL_FIC_FUNC)
    if desvio > 100:
        return ("AVISO", "CAIXA FIC FUNC",
                f"Saldo residual inferido (R$ {saldo_residual:,.2f}) diverge do reportado "
                f"(R$ {SALDO_REAL_FIC_FUNC:,.2f}) em R$ {desvio:,.2f}")
    return ("INFO", "CAIXA FIC FUNC",
            f"✓ Reconciliação caixa virtual ≈ saldo real (desvio R$ {desvio:,.2f})")
