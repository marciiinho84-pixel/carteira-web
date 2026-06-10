"""
tests/test_cache_passo3.py — Passo 3: limpeza de guard e merge do cache.py.

Casos:
  A) Guard removido: pkl salvo mesmo com precos_publicos={} + posicao ativa.
     Antes: guard impedia _salvar_disco(). Agora: sempre salva.
  B) Merge removido: resultado de run() nao e modificado pelo cache.
     Antes: ticker ausente no fetch era restaurado do _estado anterior.
     Agora: resultado passa diretamente sem modificacao.

Rodar:
    pytest tests/test_cache_passo3.py -v -s
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import pytest

import carteira_clean_web.backend.api.cache as cache_mod


def _resultado(precos_publicos=None, posicoes=None, ativos=None, benchmarks=None):
    """Monta resultado mínimo compatível com o retorno de run()."""
    return {
        "precos_publicos": precos_publicos if precos_publicos is not None else {},
        "benchmarks": benchmarks or {},
        "posicoes": posicoes or {},
        "ativos": ativos or {},
        "eventos": [],
        "precos_manuais": {},
        "vendas_rv": [],
        "vendas_rf": [],
        "proventos": {},
        "aportes_inferidos": [],
        "saldo_residual": 0.0,
        "df_evo": pd.DataFrame(),
        "df_atrib": pd.DataFrame(),
        "alertas": [],
        "hoje": date.today(),
    }


# ── Teste A: guard removido — pkl sempre salvo ───────────────────────────────

def test_A_pkl_salvo_mesmo_com_precos_publicos_vazios():
    """Guard removido: precos_publicos={} + posicao ativa nao bloqueia mais _salvar_disco.

    Comportamento ANTIGO (guard ativo):
      _precos_publicos_vazios_mas_esperados() retornava True →
      _salvar_disco() NAO era chamado (estado envenenado bloqueado).

    Comportamento NOVO (guard removido):
      _salvar_disco() e chamado independente de precos_publicos estar vazio.
      A protecao e estrutural: a tabela cotacoes nao perde dados.
    """
    posicao = MagicMock()
    posicao.qtd = 100.0

    resultado = _resultado(
        precos_publicos={},           # vazio — antes o guard dispararia
        posicoes={"PETR4": posicao},
        ativos={"PETR4": {"familia": "Acao"}},
    )

    cache_mod._estado = {}  # boot a frio — sem estado anterior

    with patch("carteira_clean_web.backend.engine.run.run", return_value=resultado):
        with patch.object(cache_mod, "_salvar_disco") as mock_salvar:
            res = cache_mod.recalcular()

    print(f"\n[Teste A] _salvar_disco chamado: {mock_salvar.call_count}x")
    print(f"[Teste A] precos_publicos no resultado: {res['precos_publicos']}")

    mock_salvar.assert_called_once()   # nova logica: sempre salva
    assert res["precos_publicos"] == {}


# ── Teste B: merge removido — resultado de run() nao e alterado ──────────────

def test_B_precos_publicos_nao_sofrem_merge():
    """Merge removido: ticker ausente no fetch novo nao e restaurado do estado antigo.

    Comportamento ANTIGO (merge ativo):
      PETR4 em _estado mas ausente em resultado_novo →
      merge adicionava PETR4 de volta em resultado["precos_publicos"].

    Comportamento NOVO (merge removido):
      resultado de run() e usado diretamente — PETR4 permanece ausente.
      A fonte de verdade e a tabela cotacoes, nao o _estado anterior.
    """
    # Simula estado anterior com PETR4
    cache_mod._estado = _resultado(
        precos_publicos={"PETR4": {date(2026, 6, 8): 35.00}},
        benchmarks={"CDI": {}},
    )

    # Novo resultado: PETR4 ausente (como se o yfinance nao o devolvesse)
    resultado_novo = _resultado(
        precos_publicos={"WEGE3": {date(2026, 6, 8): 43.00}},
    )

    with patch("carteira_clean_web.backend.engine.run.run", return_value=resultado_novo):
        with patch.object(cache_mod, "_salvar_disco"):
            res = cache_mod.recalcular()

    print(f"\n[Teste B] tickers em precos_publicos: {list(res['precos_publicos'].keys())}")

    assert "WEGE3" in res["precos_publicos"]
    assert "PETR4" not in res["precos_publicos"]   # sem merge: PETR4 nao voltou
