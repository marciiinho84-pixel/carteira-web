"""
tests/test_atribuicao_mensal.py — Atribuição mensal: bloco_ips + linhas TOTAL.

Casos:
  A) calc_atribuicao_mensal retorna bloco_ips por ativo (não None para ativos reais).
  B) Linhas TOTAL existem por (mes, composite) e TOTAL_CARTEIRA por mes.
  C) Estrutura JSON válida: todos os campos obrigatórios presentes nos rows.
  D) Soma das contribuições individuais bate com a linha TOTAL (tolerância 1e-9).

Rodar:
    pytest tests/test_atribuicao_mensal.py -v -s
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.atribuicao import calc_atribuicao_mensal
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

# ── Fixture mínima ────────────────────────────────────────────────────────────
# Dois ativos Gerida (cotizados públicos), um mês de histórico de preços.
# Famílias: usa a primeira de COTIZADO_PUBLICO para garantir correspondência.

_FAM = next(iter(COTIZADO_PUBLICO))  # ex: "Ação BR"

D_INI = date(2026, 4, 1)   # 1º dia útil de abril 2026
D_FIM = date(2026, 4, 30)  # último dia útil de abril 2026

ATIVOS = {
    "WEGE3": {
        "familia": _FAM, "composite": "Gerida",
        "benchmark": "IBOV", "bloco_ips": "SWING_TRADE",
    },
    "BURA39": {
        "familia": _FAM, "composite": "Gerida",
        "benchmark": "S&P500 BRL", "bloco_ips": "GROWTH",
    },
}

EVENTOS = [
    {"data": D_INI, "ativo": "WEGE3",  "tipo": "SALDO_INICIAL",
     "qtd": 100.0, "valor": 3500.0, "obs": ""},
    {"data": D_INI, "ativo": "BURA39", "tipo": "SALDO_INICIAL",
     "qtd": 50.0, "valor": 2500.0, "obs": ""},
]

PRECOS_PUB = {
    "WEGE3": {D_INI: 35.0, D_FIM: 36.40},   # +4%
    "BURA39": {D_INI: 50.0, D_FIM: 49.00},  # -2%
}

PRECOS_MAN = {}


@pytest.fixture(scope="module")
def df_atrib():
    return calc_atribuicao_mensal(EVENTOS, ATIVOS, PRECOS_PUB, PRECOS_MAN, D_FIM)


# ── Teste A: bloco_ips por ativo ─────────────────────────────────────────────

def test_A_bloco_ips_presente_por_ativo(df_atrib):
    """bloco_ips deve aparecer preenchido para ativos reais (não TOTAL)."""
    assert "bloco_ips" in df_atrib.columns, "coluna bloco_ips ausente no df"

    ind = df_atrib[df_atrib["ativo"] != "TOTAL"]
    assert len(ind) > 0, "nenhuma linha de ativo individual"

    # WEGE3 → SWING_TRADE, BURA39 → GROWTH
    wege = ind[ind["ativo"] == "WEGE3"]
    bura = ind[ind["ativo"] == "BURA39"]
    assert not wege.empty, "WEGE3 ausente"
    assert not bura.empty, "BURA39 ausente"
    assert wege.iloc[0]["bloco_ips"] == "SWING_TRADE"
    assert bura.iloc[0]["bloco_ips"] == "GROWTH"

    print(f"\n[A] bloco_ips únicos nos ativos: {ind['bloco_ips'].unique().tolist()}")


# ── Teste B: linhas TOTAL existem ─────────────────────────────────────────────

def test_B_linhas_total_existem(df_atrib):
    """Deve existir TOTAL por (mes, composite) e TOTAL_CARTEIRA por mes."""
    totais = df_atrib[df_atrib["ativo"] == "TOTAL"]
    assert not totais.empty, "nenhuma linha TOTAL no df"

    # TOTAL Gerida
    tot_gerida = totais[(totais["composite"] == "Gerida")]
    assert not tot_gerida.empty, "linha TOTAL Gerida ausente"
    assert (tot_gerida["peso_medio"] == 1.0).all(), "peso_medio do TOTAL Gerida deve ser 1.0"

    # TOTAL_CARTEIRA
    tot_cart = totais[totais["composite"] == "TOTAL_CARTEIRA"]
    assert not tot_cart.empty, "linha TOTAL_CARTEIRA ausente"

    # benchmark do TOTAL Gerida deve ser o composto IPS
    bench_gerida = tot_gerida.iloc[0]["benchmark"]
    assert "IBOV" in bench_gerida and "CDI" in bench_gerida, (
        f"benchmark do TOTAL Gerida inválido: {bench_gerida!r}"
    )

    print(f"\n[B] linhas TOTAL:\n{totais[['mes','composite','ativo','contribuicao','benchmark']].to_string(index=False)}")


# ── Teste C: estrutura JSON válida ────────────────────────────────────────────

def test_C_estrutura_json_valida(df_atrib):
    """Todos os campos obrigatórios presentes; tipos corretos."""
    campos_obrig = {"mes", "composite", "ativo", "retorno_ativo", "peso_medio",
                    "contribuicao", "benchmark", "bloco_ips"}
    assert campos_obrig.issubset(set(df_atrib.columns)), (
        f"colunas ausentes: {campos_obrig - set(df_atrib.columns)}"
    )

    # Tipos numéricos
    assert pd.api.types.is_float_dtype(df_atrib["retorno_ativo"]), "retorno_ativo deve ser float"
    assert pd.api.types.is_float_dtype(df_atrib["peso_medio"]),    "peso_medio deve ser float"
    assert pd.api.types.is_float_dtype(df_atrib["contribuicao"]),  "contribuicao deve ser float"

    # mes no formato YYYY-MM
    assert df_atrib["mes"].str.match(r"^\d{4}-\d{2}$").all(), "mes fora do formato YYYY-MM"

    # composite só valores esperados
    composites_validos = {"Gerida", "FUNCEF", "TOTAL_CARTEIRA"}
    assert set(df_atrib["composite"].unique()).issubset(composites_validos), (
        f"composite inesperado: {set(df_atrib['composite'].unique()) - composites_validos}"
    )

    print(f"\n[C] colunas: {list(df_atrib.columns)}")
    print(f"    composites: {df_atrib['composite'].unique().tolist()}")
    print(f"    n_rows={len(df_atrib)}")


# ── Teste D: soma das contribuições bate com TOTAL ────────────────────────────

def test_D_soma_contribuicoes_bate_total(df_atrib):
    """sum(contribuicao dos ativos individuais) == contribuicao da linha TOTAL por (mes, composite)."""
    ind = df_atrib[df_atrib["ativo"] != "TOTAL"]
    tot = df_atrib[(df_atrib["ativo"] == "TOTAL") & (df_atrib["composite"] != "TOTAL_CARTEIRA")]

    for _, row_tot in tot.iterrows():
        mes_str = row_tot["mes"]
        comp    = row_tot["composite"]
        soma_ind = ind[(ind["mes"] == mes_str) & (ind["composite"] == comp)]["contribuicao"].sum()
        diff = abs(soma_ind - row_tot["contribuicao"])
        print(f"\n[D] {mes_str}/{comp}: ind={soma_ind:.6f}  total={row_tot['contribuicao']:.6f}  diff={diff:.2e}")
        assert diff < 1e-9, (
            f"divergência {diff:.2e} em {mes_str}/{comp}: "
            f"soma_ind={soma_ind:.6f} vs TOTAL={row_tot['contribuicao']:.6f}"
        )
