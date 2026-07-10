"""
tests/test_caixa_derivado.py — Caixa derivado (partida dobrada na projeção).

Cobre os critérios de aceite da fatia "Caixa derivado":
  1) COMPRA/VENDA não afeta patrimonio_gerida nem twr_gerida do dia.
  2) APORTE_EXTERNO eleva patrimônio mas não o twr_gerida do dia.
  3) DIVIDENDO credita caixa, eleva patrimônio e conta como retorno.
  4) Identidade diária: patrimonio_gerida == soma das posições + caixa.
  5) CAIXA FIC FUNC não é excluído — o par manual (COMPRA + RESGATE do
     FIC FUNC) se autocancela no caixa, sem exclusão de ticker.
  6) aportes_inferidos (pré-transição) credita o caixa derivado, evitando
     saldo negativo permanente.

Mais um teste unitário de delta_caixa_evento cobrindo cada branch de tipo.

Rodar:
    pytest tests/test_caixa_derivado.py -v
"""

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine.caixa import delta_caixa_evento
from carteira_clean_web.backend.engine.constantes import DATA_CAIXA_TRANSICAO
from carteira_clean_web.backend.engine.inferencia import inferir_fluxos_externos_retroativos
from carteira_clean_web.backend.engine.twr import calc_evolucao_diaria, calc_twr_e_benchmarks

# Datas de referência (dias úteis; bem antes de DATA_CAIXA_TRANSICAO 2026-05-17)
D0 = date(2026, 1, 2)   # sexta — DATA_INICIO
D1 = date(2026, 1, 5)   # segunda
D2 = date(2026, 1, 6)   # terça
D3 = date(2026, 1, 7)   # quarta
D_FIM = date(2026, 1, 9)  # sexta

ATIVOS = {
    "PETR4": {"familia": "Ação BR", "composite": "Gerida"},
    "CAIXA FIC FUNC": {"familia": "Fundo CP", "composite": "Gerida"},
}

PRECO_FLAT = {D0: 50.0, D1: 50.0, D2: 50.0, D3: 50.0, D_FIM: 50.0}


def _tol(a, b, tol=0.01):
    return abs(a - b) <= tol


# ── Teste 1: COMPRA/VENDA não afeta patrimônio nem TWR do dia ───────────────

def test_compra_venda_nao_afeta_patrimonio_nem_twr():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D0, "ativo": "EXTERNO", "tipo": "APORTE_EXTERNO",
         "qtd": None, "valor": 3000.0, "obs": ""},
        {"data": D1, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 60.0, "valor": 3000.0, "obs": ""},
        {"data": D2, "ativo": "PETR4", "tipo": "VENDA",
         "qtd": 60.0, "valor": 3000.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)
    df = calc_twr_e_benchmarks(df, eventos, [], ATIVOS)

    # Preço nunca muda -> patrimonio_gerida deve ser constante em todos os dias
    pats = df["patrimonio_gerida"].tolist()
    for p in pats:
        assert _tol(p, 8000.0), f"patrimonio_gerida deveria ficar em 8000 em todo o período, foi {p}"

    # Retorno diário do TWR (diferença do acumulado) deve ser ~0 em todos os dias,
    # inclusive nos dias de COMPRA (D1) e VENDA (D2)
    twr_diario = df["twr_gerida"].diff().fillna(0.0)
    for r in twr_diario.tolist():
        assert _tol(r, 0.0, 1e-6), f"retorno diário deveria ser 0, foi {r}"


# ── Teste 2: APORTE_EXTERNO eleva patrimônio mas não o TWR do dia ──────────

def test_aporte_externo_eleva_patrimonio_mas_nao_twr_do_dia():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D1, "ativo": "EXTERNO", "tipo": "APORTE_EXTERNO",
         "qtd": None, "valor": 2000.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)
    df = calc_twr_e_benchmarks(df, eventos, [], ATIVOS)

    row_d0 = df[df["data"] == D0].iloc[0]
    row_d1 = df[df["data"] == D1].iloc[0]

    assert _tol(row_d0["patrimonio_gerida"], 5000.0)
    assert _tol(row_d1["patrimonio_gerida"], 7000.0), "patrimônio deve subir com o aporte"

    ret_d1 = row_d1["twr_gerida"] - row_d0["twr_gerida"]
    assert _tol(ret_d1, 0.0, 1e-6), f"retorno do dia do aporte deveria ser 0, foi {ret_d1}"


# ── Teste 3: DIVIDENDO credita caixa e conta como retorno ──────────────────

def test_dividendo_credita_caixa_e_conta_como_retorno():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D1, "ativo": "PETR4", "tipo": "DIVIDENDO",
         "qtd": None, "valor": 200.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)
    df = calc_twr_e_benchmarks(df, eventos, [], ATIVOS)

    row_d0 = df[df["data"] == D0].iloc[0]
    row_d1 = df[df["data"] == D1].iloc[0]

    assert _tol(row_d1["caixa"], 200.0), "dividendo deve creditar o caixa"
    assert _tol(row_d1["patrimonio_gerida"], 5200.0), "patrimônio deve subir com o dividendo"
    assert row_d1["twr_gerida"] > row_d0["twr_gerida"], "dividendo deve contar como retorno positivo"


# ── Teste 4: identidade diária patrimonio_gerida == posições + caixa ───────

def test_identidade_diaria_patrimonio_igual_posicoes_mais_caixa():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D0, "ativo": "CAIXA FIC FUNC", "tipo": "SALDO_INICIAL",
         "qtd": 1000.0, "valor": 1000.0, "obs": ""},
        {"data": D1, "ativo": "EXTERNO", "tipo": "APORTE_EXTERNO",
         "qtd": None, "valor": 500.0, "obs": ""},
        {"data": D1, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 10.0, "valor": 500.0, "obs": ""},
        {"data": D2, "ativo": "PETR4", "tipo": "DIVIDENDO",
         "qtd": None, "valor": 100.0, "obs": ""},
        {"data": D2, "ativo": "PETR4", "tipo": "BONIFICACAO",
         "qtd": 5.0, "valor": 250.0, "obs": ""},
        {"data": D3, "ativo": "PETR4", "tipo": "VENDA",
         "qtd": 15.0, "valor": 750.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)

    # Posições esperadas calculadas à mão (preço PETR4 sempre 50; CAIXA FIC FUNC
    # sem preço manual -> valorizado pelo custo_total):
    #   D0: PETR4=5000  CAIXAFIC=1000  caixa=0    -> patrimônio=6000
    #   D1: PETR4=5500  CAIXAFIC=1000  caixa=0    -> patrimônio=6500
    #   D2: PETR4=5750  CAIXAFIC=1000  caixa=100  -> patrimônio=6850
    #   D3: PETR4=5000  CAIXAFIC=1000  caixa=850  -> patrimônio=6850
    esperado = {
        D0: (5000.0 + 1000.0, 0.0),
        D1: (5500.0 + 1000.0, 0.0),
        D2: (5750.0 + 1000.0, 100.0),
        D3: (5000.0 + 1000.0, 850.0),
    }
    for d, (soma_posicoes, caixa_esp) in esperado.items():
        row = df[df["data"] == d].iloc[0]
        assert _tol(row["caixa"], caixa_esp), f"{d}: caixa esperado {caixa_esp}, foi {row['caixa']}"
        assert _tol(row["patrimonio_gerida"] - row["caixa"], soma_posicoes), (
            f"{d}: soma de posições esperada {soma_posicoes}, "
            f"foi {row['patrimonio_gerida'] - row['caixa']}"
        )
        assert _tol(row["patrimonio_gerida"], soma_posicoes + caixa_esp), (
            "identidade patrimonio_gerida == posições + caixa violada em " + str(d)
        )


# ── Teste 5: par manual CAIXA FIC FUNC neutraliza o caixa (sem exclusão) ───

def test_caixa_fic_func_par_manual_neutraliza_caixa():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D0, "ativo": "CAIXA FIC FUNC", "tipo": "SALDO_INICIAL",
         "qtd": 2000.0, "valor": 2000.0, "obs": ""},
        # Par automático do novo_evento.py: COMPRA de ação + RESGATE do FIC FUNC,
        # mesmo dia, mesmo valor.
        {"data": D1, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 20.0, "valor": 1000.0, "obs": ""},
        {"data": D1, "ativo": "CAIXA FIC FUNC", "tipo": "RESGATE",
         "qtd": 1000.0, "valor": 1000.0, "obs": "Auto: liquidação COMPRA PETR4"},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, {}, D_FIM)

    row_d0 = df[df["data"] == D0].iloc[0]
    row_d1 = df[df["data"] == D1].iloc[0]

    assert _tol(row_d1["caixa"], row_d0["caixa"]), "par manual deve deixar o caixa líquido do dia em 0"
    assert _tol(row_d1["patrimonio_gerida"], row_d0["patrimonio_gerida"]), (
        "patrimônio deve ficar invariante: alta em PETR4 compensada pela queda no FIC FUNC"
    )


# ── Teste 6: aporte inferido credita o caixa pré-transição ─────────────────

def test_aporte_inferido_credita_caixa_pre_transicao():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": "", "linha": 1},
        # COMPRA pré-transição sem par de CAIXA FIC FUNC nem APORTE_EXTERNO
        {"data": D1, "ativo": "PETR4", "tipo": "COMPRA",
         "qtd": 20.0, "valor": 1000.0, "obs": "", "linha": 2},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}

    assert D1 < DATA_CAIXA_TRANSICAO

    aportes_inferidos, saldo_residual = inferir_fluxos_externos_retroativos(eventos, ATIVOS)
    assert len(aportes_inferidos) == 1
    assert _tol(aportes_inferidos[0]["valor"], 1000.0)
    assert aportes_inferidos[0]["data"] == D1

    df = calc_evolucao_diaria(
        eventos, ATIVOS, precos_pub, {}, D_FIM, aportes_inferidos=aportes_inferidos
    )
    row_d1 = df[df["data"] == D1].iloc[0]

    assert row_d1["caixa"] > -0.01, "aporte inferido deve evitar caixa negativo"
    assert _tol(row_d1["caixa"], 0.0), "débito da COMPRA deve ser compensado pelo aporte inferido"


# ── Teste 7: APORTE_EXTERNO em ativo com cota não dobra o patrimônio ──────
# (hotfix — dupla-conta: perna de posição em twr.py + crédito de caixa)

def test_aporte_externo_em_ativo_com_cota_nao_dobra_patrimonio():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D1, "ativo": "CAIXA FIC FUNC", "tipo": "APORTE_EXTERNO",
         "qtd": None, "valor": 300.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}
    precos_man = {"CAIXA FIC FUNC": {D0: 3.0, D1: 3.0, D2: 3.0, D3: 3.0, D_FIM: 3.0}}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, precos_man, D_FIM)
    df = calc_twr_e_benchmarks(df, eventos, [], ATIVOS)

    row_d0 = df[df["data"] == D0].iloc[0]
    row_d1 = df[df["data"] == D1].iloc[0]

    assert _tol(row_d1["caixa"], row_d0["caixa"]), (
        "caixa não deve mudar — a perna de posição (compra de cotas) já absorveu o aporte"
    )
    delta_pat = row_d1["patrimonio_gerida"] - row_d0["patrimonio_gerida"]
    assert _tol(delta_pat, 300.0), (
        f"patrimônio deveria subir exatamente 300 (1x o aporte, não 2x), subiu {delta_pat}"
    )
    ret_d1 = row_d1["twr_gerida"] - row_d0["twr_gerida"]
    assert _tol(ret_d1, 0.0, 1e-6), f"retorno do dia do aporte deveria ser 0, foi {ret_d1}"


# ── Teste 8: RESGATE_EXTERNO simétrico — sem perna de posição, inalterado ──

def test_resgate_externo_simetrico_sem_perna_de_posicao():
    eventos = [
        {"data": D0, "ativo": "PETR4", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 5000.0, "obs": ""},
        {"data": D0, "ativo": "CAIXA FIC FUNC", "tipo": "SALDO_INICIAL",
         "qtd": 100.0, "valor": 300.0, "obs": ""},
        {"data": D1, "ativo": "CAIXA FIC FUNC", "tipo": "RESGATE_EXTERNO",
         "qtd": None, "valor": 300.0, "obs": ""},
    ]
    precos_pub = {"PETR4": PRECO_FLAT}
    precos_man = {"CAIXA FIC FUNC": {D0: 3.0, D1: 3.0, D2: 3.0, D3: 3.0, D_FIM: 3.0}}

    df = calc_evolucao_diaria(eventos, ATIVOS, precos_pub, precos_man, D_FIM)

    row_d0 = df[df["data"] == D0].iloc[0]
    row_d1 = df[df["data"] == D1].iloc[0]

    # RESGATE_EXTERNO não tem perna de posição em lugar nenhum do engine hoje:
    # caixa debita -valor normalmente (não há dupla-conta a evitar aqui).
    assert _tol(row_d1["caixa"] - row_d0["caixa"], -300.0), (
        "RESGATE_EXTERNO deve debitar caixa normalmente (sem perna de posição)"
    )
    # Soma das posições (patrimonio - caixa) não deve mudar.
    soma_d0 = row_d0["patrimonio_gerida"] - row_d0["caixa"]
    soma_d1 = row_d1["patrimonio_gerida"] - row_d1["caixa"]
    assert _tol(soma_d0, soma_d1), "soma das posições não deve mudar com RESGATE_EXTERNO"


# ── Teste unitário: delta_caixa_evento cobre cada branch de tipo ──────────

def test_delta_caixa_evento_branches():
    ativos = {
        "PETR4": {"familia": "Ação BR", "composite": "Gerida"},
        "FUNCEF": {"familia": "Fundo de Pensão", "composite": "FUNCEF"},
        "CAIXA FIC FUNC": {"familia": "Fundo CP", "composite": "Gerida"},
    }

    def ev(ativo, tipo, valor):
        return {"ativo": ativo, "tipo": tipo, "valor": valor}

    assert delta_caixa_evento(ev("FUNCEF", "CONTRIBUICAO", 100.0), ativos, {}, D0) == 0.0
    assert delta_caixa_evento(ev("PETR4", "SALDO_INICIAL", 100.0), ativos, {}, D0) == 0.0
    assert delta_caixa_evento(ev("PETR4", "BONIFICACAO", 100.0), ativos, {}, D0) == 0.0
    # APORTE_EXTERNO em ticker sem cota disponível: caixa credita normalmente
    assert delta_caixa_evento(ev("PETR4", "APORTE_EXTERNO", 100.0), ativos, {}, D0) == 100.0
    # APORTE_EXTERNO em ticker COTIZADO_PRIVADO COM cota disponível: perna de
    # posição em twr.py já absorve — caixa fica 0 (senão dobra a contagem)
    assert delta_caixa_evento(
        ev("CAIXA FIC FUNC", "APORTE_EXTERNO", 100.0), ativos,
        {"CAIXA FIC FUNC": {D0: 3.0}}, D0,
    ) == 0.0
    assert delta_caixa_evento(ev("PETR4", "RESGATE_EXTERNO", 100.0), ativos, {}, D0) == -100.0
    # RESGATE_EXTERNO não tem perna de posição em lugar nenhum — mesmo com
    # cota disponível, continua debitando caixa normalmente
    assert delta_caixa_evento(
        ev("CAIXA FIC FUNC", "RESGATE_EXTERNO", 100.0), ativos,
        {"CAIXA FIC FUNC": {D0: 3.0}}, D0,
    ) == -100.0
    assert delta_caixa_evento(ev("PETR4", "COMPRA", 100.0), ativos, {}, D0) == -100.0
    assert delta_caixa_evento(ev("CAIXA FIC FUNC", "APORTE", 100.0), ativos, {}, D0) == -100.0
    assert delta_caixa_evento(ev("PETR4", "VENDA", 100.0), ativos, {}, D0) == 100.0
    assert delta_caixa_evento(ev("CAIXA FIC FUNC", "RESGATE", 100.0), ativos, {}, D0) == 100.0
    assert delta_caixa_evento(ev("PETR4", "VENCIMENTO", 100.0), ativos, {}, D0) == 100.0
    for tipo in ("DIVIDENDO", "JCP", "RENDIMENTO", "AMORTIZACAO"):
        assert delta_caixa_evento(ev("PETR4", tipo, 100.0), ativos, {}, D0) == 100.0
    assert delta_caixa_evento(ev("PETR4", "TIPO_INEXISTENTE", 100.0), ativos, {}, D0) == 0.0
