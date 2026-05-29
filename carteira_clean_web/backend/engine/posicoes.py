"""
engine/posicoes.py — PEPS com reset em zeramento.

Lógica copiada literalmente de calc_posicoes_e_vendas() em atualizar_carteira.py.
Sem alteração de comportamento.
"""

from collections import defaultdict
from dataclasses import dataclass

from .constantes import COMPRAS, VENDAS, PROVENTOS, COTIZADO_PUBLICO, COTIZADO_PRIVADO
from .utils import preco_em


@dataclass
class Posicao:
    qtd: float = 0.0
    custo_total: float = 0.0

    @property
    def custo_medio(self):
        return self.custo_total / self.qtd if self.qtd > 1e-9 else 0.0


def calc_posicoes_e_vendas(eventos: list, ativos: dict = None, precos_manuais: dict = None):
    """PEPS corrigido com reset em zeramento.

    Returns: (posicoes, vendas_rv, vendas_rf, proventos)
      - vendas_rv: vendas de RV (vão para RELATORIO_VENDAS)
      - vendas_rf: resgates de cotizados privados (auditoria)
      - proventos: {ticker: total_proventos}
    """
    posicoes = defaultdict(Posicao)
    vendas_rv = []
    vendas_rf = []
    proventos = defaultdict(float)
    ativos = ativos or {}
    precos_manuais = precos_manuais or {}

    for ev in eventos:
        tkr = ev["ativo"]
        tipo = ev["tipo"]
        p = posicoes[tkr]

        if tipo in COMPRAS or tipo == "CONTRIBUICAO":
            qtd = ev["qtd"] or 0
            valor = ev["valor"] or 0
            p.qtd += qtd
            p.custo_total += abs(valor)

        elif tipo == "APORTE_EXTERNO":
            familia = ativos.get(tkr, {}).get("familia", "")
            if familia in COTIZADO_PRIVADO:
                valor = abs(ev["valor"] or 0)
                cota = preco_em(precos_manuais.get(tkr, {}), ev["data"])
                if cota and cota > 0 and valor > 0:
                    p.qtd += valor / cota
                    p.custo_total += valor

        elif tipo in VENDAS:
            qtd = ev["qtd"] or 0
            valor_recebido = ev["valor"] or 0
            if p.qtd > 1e-9:
                cm = p.custo_medio
                custo_vendido = cm * qtd
                pnl = valor_recebido - custo_vendido
                venda = {
                    "data": ev["data"],
                    "ticker": tkr,
                    "qtd_vendida": qtd,
                    "preco_venda": ev["preco"],
                    "custo_medio": cm,
                    "valor_recebido": valor_recebido,
                    "pnl": pnl,
                    "pnl_pct": pnl / custo_vendido * 100 if custo_vendido > 0 else 0,
                }
                familia = ativos.get(tkr, {}).get("familia", "")
                if familia in COTIZADO_PUBLICO:
                    vendas_rv.append(venda)
                else:
                    vendas_rf.append(venda)
                p.custo_total -= custo_vendido
                p.qtd -= qtd
                if abs(p.qtd) < 1e-6:
                    p.qtd = 0.0
                    p.custo_total = 0.0

        elif tipo in PROVENTOS:
            proventos[tkr] += ev["valor"] or 0

    return dict(posicoes), vendas_rv, vendas_rf, dict(proventos)
