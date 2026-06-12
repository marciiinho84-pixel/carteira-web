"""
Testes de regressão da Fase 2.1 — Seção 12 do ROTEIRO_CLAUDE_CODE.md

Todos os valores esperados vêm diretamente da Seção 12 do roteiro.
Estes testes NÃO requerem conexão de rede (rodam com --no-api).

Para rodar:
    pytest carteira_clean_web/tests/regression/test_fase21.py -v
"""

import sys
from pathlib import Path

# parents[3] = /home/marcio/carteira-web (raiz do projeto)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import pytest
from carteira_clean_web.backend.engine.io import carregar_dados
from carteira_clean_web.backend.engine.posicoes import calc_posicoes_e_vendas
from carteira_clean_web.backend.engine.inferencia import inferir_fluxos_externos_retroativos
from carteira_clean_web.backend.engine.twr import calc_evolucao_diaria, calc_twr_e_benchmarks
from carteira_clean_web.backend.engine.atribuicao import calc_atribuicao_mensal

DB_PATH = ROOT / "carteira_clean_web" / "carteira.db"


@pytest.fixture(scope="module")
def dados():
    """Carrega dados do SQLite uma vez para todos os testes."""
    return carregar_dados(DB_PATH)


@pytest.fixture(scope="module")
def resultado(dados):
    """Executa o engine completo sem API."""
    from datetime import date
    ativos, eventos, precos_manuais = dados
    # sem API → sem preços públicos; benchmarks lidos da tabela (podem ser vazios em CI)
    precos_publicos = {}
    posicoes, vendas_rv, vendas_rf, proventos = calc_posicoes_e_vendas(eventos, ativos)
    aportes_inferidos, saldo_residual = inferir_fluxos_externos_retroativos(eventos, ativos)
    df_evo = calc_evolucao_diaria(eventos, ativos, precos_publicos, precos_manuais, date(2026, 5, 15))
    df_evo = calc_twr_e_benchmarks(df_evo, eventos, aportes_inferidos, ativos)
    df_atrib = calc_atribuicao_mensal(eventos, ativos, precos_publicos, precos_manuais, date(2026, 5, 15))
    return {
        "ativos": ativos,
        "eventos": eventos,
        "precos_manuais": precos_manuais,
        "posicoes": posicoes,
        "vendas_rv": vendas_rv,
        "vendas_rf": vendas_rf,
        "proventos": proventos,
        "aportes_inferidos": aportes_inferidos,
        "saldo_residual": saldo_residual,
        "df_evo": df_evo,
        "df_atrib": df_atrib,
    }


# ────────────────────────────────────────────────────────────────────
# Seção 12F — Validações estruturais
# ────────────────────────────────────────────────────────────────────

class TestContagens:
    def test_35_ativos_cadastrados(self, dados):
        ativos, _, _ = dados
        assert len(ativos) == 35, f"Esperado 35, encontrado {len(ativos)}"

    def test_105_eventos(self, dados):
        _, eventos, _ = dados
        assert len(eventos) == 105, f"Esperado 105, encontrado {len(eventos)}"

    def test_47_precos_manuais(self, dados):
        _, _, precos_manuais = dados
        total = sum(len(v) for v in precos_manuais.values())
        assert total == 47, f"Esperado 47, encontrado {total}"

    def test_1_ativo_funcef(self, dados):
        ativos, _, _ = dados
        funcef = [t for t, info in ativos.items() if info.get("composite") == "FUNCEF"]
        assert len(funcef) == 1, f"Esperado 1 ativo FUNCEF, encontrado {len(funcef)}"

    def test_34_ativos_gerida(self, dados):
        ativos, _, _ = dados
        gerida = [t for t, info in ativos.items() if info.get("composite") == "Gerida"]
        assert len(gerida) == 34

    def test_12_tipos_evento_validos(self, dados):
        from carteira_clean_web.backend.scripts.migrate_from_excel import TIPOS_VALIDOS
        _, eventos, _ = dados
        tipos_no_banco = set(e["tipo"] for e in eventos)
        invalidos = tipos_no_banco - TIPOS_VALIDOS
        assert not invalidos, f"Tipos inválidos no banco: {invalidos}"

    def test_todos_ativos_de_eventos_cadastrados(self, dados):
        ativos, eventos, _ = dados
        ativos_eventos = set(e["ativo"] for e in eventos)
        nao_cadastrados = ativos_eventos - set(ativos.keys())
        assert not nao_cadastrados, f"Ativos em eventos mas não no cadastro: {nao_cadastrados}"


# ────────────────────────────────────────────────────────────────────
# Seção 12A — P&L de vendas realizadas
# ────────────────────────────────────────────────────────────────────

class TestVendasRV:
    def test_6_vendas_rv(self, resultado):
        assert len(resultado["vendas_rv"]) == 6

    def test_pnl_total_exato(self, resultado):
        pnl_total = sum(v["pnl"] for v in resultado["vendas_rv"])
        assert abs(pnl_total - 3629.15) < 0.01, f"P&L total: R$ {pnl_total:.2f}, esperado R$ 3629.15"

    def test_pnl_bslv39(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "BSLV39")
        assert abs(v["pnl"] - 300.10) < 0.01, f"P&L BSLV39: R$ {v['pnl']:.2f}"

    def test_pnl_aura33(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "AURA33")
        assert abs(v["pnl"] - 479.00) < 0.01, f"P&L AURA33: R$ {v['pnl']:.2f}"

    def test_pnl_seer3(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "SEER3")
        assert abs(v["pnl"] - 243.55) < 0.01, f"P&L SEER3: R$ {v['pnl']:.2f}"

    def test_pnl_petr4(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "PETR4")
        assert abs(v["pnl"] - 2189.00) < 0.01, f"P&L PETR4: R$ {v['pnl']:.2f}"

    def test_pnl_prio3(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "PRIO3")
        assert abs(v["pnl"] - 387.50) < 0.01, f"P&L PRIO3: R$ {v['pnl']:.2f}"

    def test_pnl_plpl3(self, resultado):
        v = next(v for v in resultado["vendas_rv"] if v["ticker"] == "PLPL3")
        assert abs(v["pnl"] - 30.00) < 0.01, f"P&L PLPL3: R$ {v['pnl']:.2f}"

    def test_12_resgates_rf(self, resultado):
        assert len(resultado["vendas_rf"]) == 12


# ────────────────────────────────────────────────────────────────────
# Seção 12B — Custos médios de posições ativas
# ────────────────────────────────────────────────────────────────────

class TestCustosMedios:
    def test_custo_medio_wege3(self, resultado):
        p = resultado["posicoes"]["WEGE3"]
        assert abs(p.custo_medio - 47.3182) < 0.001, f"Custo médio WEGE3: {p.custo_medio:.4f}"

    def test_custo_medio_aura33_pos_compra(self, resultado):
        """Após a venda (13/04) e recompra pendente, custo deve ser R$ 138.7833."""
        p = resultado["posicoes"]["AURA33"]
        assert abs(p.custo_medio - 138.7833) < 0.001, f"Custo médio AURA33: {p.custo_medio:.4f}"

    def test_petr4_posicao_zerada(self, resultado):
        """PETR4 foi vendido completamente — PEPS reset, posição deve ser 0."""
        p = resultado["posicoes"].get("PETR4")
        if p:
            assert abs(p.qtd) < 1e-6, f"PETR4 deveria estar zerada, qtd={p.qtd}"

    def test_bslv39_custo_medio_atual(self, resultado):
        """BSLV39 foi vendido em 28/01 (P&L +R$300,10) e recomprado depois.
        Custo atual deve ser diferente de R$124,99 (reset em zeramento aplicado).
        """
        p = resultado["posicoes"].get("BSLV39")
        if p and p.qtd > 1e-6:
            # Confirmação do PEPS com reset: custo não pode ser o valor pré-venda
            assert abs(p.custo_medio - 124.99) > 0.01, (
                "Custo médio do BSLV39 não foi resetado após zeramento"
            )


# ────────────────────────────────────────────────────────────────────
# Seção 12D — Inferência de fluxos retroativos
# ────────────────────────────────────────────────────────────────────

class TestInferencia:
    def test_22_aportes_inferidos(self, resultado):
        n = len(resultado["aportes_inferidos"])
        assert n == 22, f"Esperado 22 aportes inferidos, encontrado {n}"

    def test_total_inferido(self, resultado):
        total = sum(a["valor"] for a in resultado["aportes_inferidos"])
        assert abs(total - 37582.59) < 0.01, f"Total inferido: R$ {total:.2f}, esperado R$ 37582.59"

    def test_saldo_residual(self, resultado):
        sr = resultado["saldo_residual"]
        assert abs(sr - 2070.00) < 0.01, f"Saldo residual: R$ {sr:.2f}, esperado R$ 2070.00"

    def test_desvio_dentro_tolerancia(self, resultado):
        """Desvio entre saldo residual e saldo real (R$ 2450.48) deve ser < R$ 500."""
        saldo_real = 2450.48
        desvio = abs(resultado["saldo_residual"] - saldo_real)
        assert desvio < 500, f"Desvio R$ {desvio:.2f} acima de R$ 500"

    def test_desvio_esperado_380(self, resultado):
        """Desvio específico esperado: R$ 380.48."""
        saldo_real = 2450.48
        desvio = abs(resultado["saldo_residual"] - saldo_real)
        assert abs(desvio - 380.48) < 0.01, f"Desvio: R$ {desvio:.2f}, esperado R$ 380.48"


# ────────────────────────────────────────────────────────────────────
# Evolução diária — estrutura
# ────────────────────────────────────────────────────────────────────

class TestEvolucaoDiaria:
    def test_96_dias_uteis(self, resultado):
        """Entre 02/01/2026 e 15/05/2026 há 96 dias úteis."""
        n = len(resultado["df_evo"])
        assert n == 96, f"Esperado 96 dias úteis, encontrado {n}"

    def test_colunas_presentes(self, resultado):
        df = resultado["df_evo"]
        colunas_esperadas = [
            "data", "patrimonio_gerida", "patrimonio_funcef", "patrimonio_total",
            "patrimonio_rv", "twr_gerida", "twr_total", "twr_rv",
        ]
        for col in colunas_esperadas:
            assert col in df.columns, f"Coluna ausente: {col}"

    def test_patrimonio_funcef_positivo(self, resultado):
        df = resultado["df_evo"]
        assert (df["patrimonio_funcef"] > 0).all(), "FUNCEF deve ser positivo em todos os dias"

    def test_nao_ha_posicoes_negativas(self, resultado):
        for tkr, p in resultado["posicoes"].items():
            assert p.qtd >= -1e-6, f"Posição negativa: {tkr} qtd={p.qtd}"


# ────────────────────────────────────────────────────────────────────
# Atribuição mensal
# ────────────────────────────────────────────────────────────────────

class TestAtribuicaoMensal:
    def test_92_linhas(self, resultado):
        n = len(resultado["df_atrib"])
        assert n == 92, f"Esperado 92 linhas de atribuição, encontrado {n}"

    def test_colunas_presentes(self, resultado):
        df = resultado["df_atrib"]
        for col in ["mes", "composite", "ativo", "retorno_ativo", "peso_medio", "contribuicao"]:
            assert col in df.columns

    def test_apenas_dois_composites(self, resultado):
        composites = set(resultado["df_atrib"]["composite"].unique())
        assert composites <= {"Gerida", "FUNCEF"}
