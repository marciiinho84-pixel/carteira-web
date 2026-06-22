"""
tests/test_sprint_itens456.py — Sprint de refinamentos itens 4, 5 e 6.

Casos:
  A) Item 4: constantes PRECO_*_POR_MTOK existem; acúmulo de sessão funciona.
  B) Item 5: banco vazio → alembic upgrade head → schema correto;
             alembic downgrade base → tabelas removidas.
  C) Item 6: baixar_benchmarks usa _normalizar_close/_extrair compartilhados;
             medir speedup sequencial vs lote (mock yfinance).

Rodar:
    pytest tests/test_sprint_itens456.py -v -s
"""

import sys
import time
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── Teste A: constantes e acúmulo de sessão ──────────────────────────────────

def test_A_constantes_custo():
    """PRECO_INPUT_POR_MTOK / PRECO_OUTPUT_POR_MTOK existem e derivam _CUSTO_IN/_CUSTO_OUT."""
    from carteira_clean_web.frontend.telas import assistente as ast

    assert hasattr(ast, "PRECO_INPUT_POR_MTOK"),  "Faltou PRECO_INPUT_POR_MTOK"
    assert hasattr(ast, "PRECO_OUTPUT_POR_MTOK"), "Faltou PRECO_OUTPUT_POR_MTOK"

    assert ast._CUSTO_IN  == ast.PRECO_INPUT_POR_MTOK  / 1_000_000
    assert ast._CUSTO_OUT == ast.PRECO_OUTPUT_POR_MTOK / 1_000_000

    # Valores actuais para Opus 4.8
    assert ast.PRECO_INPUT_POR_MTOK  == 5.0
    assert ast.PRECO_OUTPUT_POR_MTOK == 25.0

    print(f"\n[A] PRECO_INPUT_POR_MTOK={ast.PRECO_INPUT_POR_MTOK}, "
          f"PRECO_OUTPUT_POR_MTOK={ast.PRECO_OUTPUT_POR_MTOK}")
    print(f"    _CUSTO_IN={ast._CUSTO_IN:.8f}, _CUSTO_OUT={ast._CUSTO_OUT:.8f}")


def test_A_acumulo_sessao():
    """Simula acúmulo de tokens de sessão (lógica sem Streamlit)."""
    # Simula um _sess dict como o session_state faria
    sess = {"tok_in": 0, "tok_out": 0, "msgs": 0}
    _CUSTO_IN  = 5.0 / 1_000_000
    _CUSTO_OUT = 25.0 / 1_000_000
    _USD_BRL   = 5.7

    respostas = [
        (1000, 500),
        (800, 600),
        (1200, 400),
    ]
    for tok_in, tok_out in respostas:
        sess["tok_in"]  += tok_in
        sess["tok_out"] += tok_out
        sess["msgs"]    += 1

    custo_usd = sess["tok_in"] * _CUSTO_IN + sess["tok_out"] * _CUSTO_OUT
    custo_brl = custo_usd * _USD_BRL

    assert sess["msgs"]   == 3
    assert sess["tok_in"] == 3000
    assert sess["tok_out"] == 1500
    total_tok = sess["tok_in"] + sess["tok_out"]
    assert total_tok == 4500

    esperado_usd = (3000 * _CUSTO_IN) + (1500 * _CUSTO_OUT)
    assert abs(custo_usd - esperado_usd) < 1e-10

    print(f"\n[A] 3 mensagens: {total_tok} tokens | custo R$ {custo_brl:.4f}")


# ── Teste B: alembic upgrade/downgrade em banco vazio ────────────────────────

@pytest.mark.skip(reason="alembic agora aponta para PostgreSQL (DATABASE_URL); "
                          "teste SQLite obsoleto após migração")
def test_B_alembic_upgrade_downgrade(tmp_path):
    """upgrade head → schema correto; downgrade base → banco limpo."""
    import os, subprocess, sqlite3

    db = tmp_path / "test.db"
    env = {**os.environ, "DB_PATH": str(db)}

    # upgrade head
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert result.returncode == 0, f"upgrade head falhou:\n{result.stderr}"

    # verificar tabelas criadas
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    con.close()

    assert "cotacoes"   in tables, f"cotacoes não encontrada. Tabelas: {tables}"
    assert "benchmarks" in tables, f"benchmarks não encontrada. Tabelas: {tables}"
    assert "alembic_version" in tables

    print(f"\n[B] upgrade head OK — tabelas: {sorted(tables)}")

    # downgrade base
    result2 = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert result2.returncode == 0, f"downgrade base falhou:\n{result2.stderr}"

    con2 = sqlite3.connect(str(db))
    cur2 = con2.cursor()
    cur2.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables_after = {r[0] for r in cur2.fetchall()}
    con2.close()

    data_tables = tables_after - {"alembic_version"}
    assert not data_tables, f"Tabelas residuais após downgrade: {data_tables}"
    print(f"[B] downgrade base OK — sem tabelas de dados residuais")


# ── Teste C: baixar_benchmarks em lote vs sequencial ────────────────────────

def test_C_benchmark_lote_compartilha_helpers():
    """_normalizar_close e _extrair são módulo-nível (não mais funções internas)."""
    from carteira_clean_web.backend.engine import precos

    assert callable(getattr(precos, "_normalizar_close", None)), \
        "_normalizar_close não é função de módulo"
    assert callable(getattr(precos, "_extrair", None)), \
        "_extrair não é função de módulo"
    assert hasattr(precos, "_BENCH_YF_MAP"), \
        "_BENCH_YF_MAP não definido no módulo"
    assert len(precos._BENCH_YF_MAP) == 5, \
        f"Esperado 5 benchmarks yf, encontrado {len(precos._BENCH_YF_MAP)}"

    print(f"\n[C] _normalizar_close e _extrair em nível de módulo ✓")
    print(f"    _BENCH_YF_MAP: {precos._BENCH_YF_MAP}")


def test_C_benchmark_lote_speedup():
    """
    Mock: sequencial faz 5 yf.download de 0.1s cada = ~0.5s.
    Lote faz 1 yf.download de 0.1s = ~0.1s.
    Confirma que versão atual faz ≤ 2 chamadas para 5 tickers sem faltantes.
    """
    from datetime import date, timedelta
    from carteira_clean_web.backend.engine import precos

    datas = pd.date_range("2026-01-02", "2026-01-31", freq="B")
    yf_tickers = list(precos._BENCH_YF_MAP.keys())

    # DataFrame com todos os 5 tickers (simula download em lote bem-sucedido)
    close_data = {tkr: [100.0 + i for i in range(len(datas))] for tkr in yf_tickers}
    df_batch = pd.DataFrame(
        {("Close", tkr): vals for tkr, vals in close_data.items()},
        index=datas,
    )
    df_batch.columns = pd.MultiIndex.from_tuples(df_batch.columns)

    call_count = {"n": 0}
    delay_per_call = 0.05  # 50ms por chamada

    def fake_download(tickers, **kwargs):
        call_count["n"] += 1
        time.sleep(delay_per_call)
        if isinstance(tickers, str):
            tickers = [tickers]
        cols = [("Close", t) for t in tickers]
        data = {c: [100.0] * len(datas) for c in cols}
        df = pd.DataFrame(data, index=datas)
        df.columns = pd.MultiIndex.from_tuples(df.columns)
        return df

    with patch.object(precos.yf, "download", side_effect=fake_download):
        with patch.object(precos, "_gravar_benchmarks"):
            with patch.object(precos, "requests") as mock_req:
                # BCB returns empty to skip CDI/IPCA
                mock_resp = MagicMock()
                mock_resp.raise_for_status = lambda: None
                mock_resp.json.return_value = []
                mock_req.get.return_value = mock_resp

                t0 = time.time()
                result = precos.baixar_benchmarks(date(2026, 1, 2), date(2026, 1, 31))
                elapsed = time.time() - t0

    # Com lote: deve ter feito apenas 1 chamada yf.download (sem faltantes)
    assert call_count["n"] == 1, \
        f"Esperado 1 chamada yf.download (lote), feitas {call_count['n']}"
    assert len(result) == 5, \
        f"Esperado 5 benchmarks, encontrado {len(result)}: {list(result.keys())}"

    # Speedup teórico: sequencial seria 5 × 50ms = 250ms; lote = 50ms
    print(f"\n[C] Lote: {call_count['n']} chamada(s) yf.download, "
          f"{elapsed*1000:.0f}ms — benchmarks: {sorted(result.keys())}")
    print(f"    Speedup estimado vs sequencial: ~5x (1 vs 5 chamadas)")
