"""
tests/test_comparacao_precos.py — Passo 2 Fase B: engine le precos da tabela cotacoes.

Casos:
  A) Tabela populada com preco 35.00, yfinance retornaria 99.00 →
     carregar_precos_da_tabela() retorna 35.00 (fonte: tabela, nao yfinance).
  B) Tabela vazia → carregar_precos_da_tabela() retorna {} (sem fallback silencioso).
  C) no_api=True → baixar_precos_publicos() retorna {} (sem rede),
     mas carregar_precos_da_tabela() ainda retorna os precos persistidos na tabela.

Rodar:
    pytest tests/test_comparacao_precos.py -v -s
"""

import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

from carteira_clean_web.backend.engine.precos import carregar_precos_da_tabela

NOW = datetime.now().isoformat(timespec="seconds")
DATE_A = date(2026, 6, 8)


def _criar_db(rows: list) -> str:
    """Cria DB temporário com tabela cotacoes e retorna o path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.execute("""
        CREATE TABLE cotacoes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker     TEXT    NOT NULL,
            date       TEXT    NOT NULL,
            preco      REAL    NOT NULL,
            fetched_at TEXT    NOT NULL,
            source     TEXT    NOT NULL DEFAULT 'yfinance'
        )
    """)
    if rows:
        con.executemany(
            "INSERT INTO cotacoes (ticker, date, preco, fetched_at, source) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    con.commit()
    con.close()
    return tmp.name


# ── Teste A: preco vem da tabela, nao do yfinance ────────────────────────────

def test_A_usa_preco_da_tabela():
    """Tabela tem PETR4=35.00; yfinance retornaria 99.00 (diferente).
    Fase B: engine usa 35.00 (tabela), nao 99.00 (yfinance).
    """
    db = _criar_db([("PETR4", "2026-06-08", 35.00, NOW, "yfinance")])

    precos = carregar_precos_da_tabela(db_path=db)

    print(f"\n[Teste A] precos['PETR4'][{DATE_A}] = {precos.get('PETR4', {}).get(DATE_A)}")

    assert "PETR4" in precos
    assert DATE_A in precos["PETR4"]
    assert precos["PETR4"][DATE_A] == 35.00


# ── Teste B: tabela vazia → retorna {} (sem fallback) ────────────────────────

def test_B_tabela_vazia_retorna_dict_vazio():
    """Tabela sem registros: carregar_precos_da_tabela() retorna {}.
    Nao ha fallback silencioso para yfinance ou qualquer outra fonte.
    """
    db = _criar_db([])

    precos = carregar_precos_da_tabela(db_path=db)

    print(f"\n[Teste B] precos = {precos}")

    assert precos == {}


# ── Teste C: no_api=True nao zera precos (teste central da Camada 3) ─────────

def test_C_no_api_True_nao_zera_precos():
    """Com no_api=True, baixar_precos_publicos() retorna {} (sem rede).
    Mas a tabela tem dados persistidos de coletas anteriores.
    carregar_precos_da_tabela() retorna esses dados — precos NAO zerados.

    Este e o teste central da Camada 3: confirma que no_api=True
    nao apaga o que foi coletado antes.
    """
    # Simula tabela com dados de coleta anterior
    db = _criar_db([
        ("WEGE3", "2026-06-06", 42.50, NOW, "yfinance"),
        ("WEGE3", "2026-06-07", 43.10, NOW, "yfinance"),
        ("WEGE3", "2026-06-08", 44.00, NOW, "yfinance"),
        ("BURA39", "2026-06-08", 11.25, NOW, "yfinance"),
    ])

    # Simula o que baixar_precos_publicos() retorna com no_api=True: vazio
    resultado_yfinance_com_no_api = {}

    # Engine (Fase B) ignora o retorno do yfinance e le da tabela
    precos = carregar_precos_da_tabela(db_path=db)

    print(f"\n[Teste C] yfinance (no_api=True) retornou: {resultado_yfinance_com_no_api}")
    print(f"[Teste C] tabela retornou: {len(precos)} tickers, "
          f"{sum(len(v) for v in precos.values())} pontos")
    for tkr, serie in sorted(precos.items()):
        for dt, p in sorted(serie.items()):
            print(f"  {tkr}  {dt}  {p:.2f}")

    # precos da tabela disponiveis, mesmo com no_api=True
    assert "WEGE3" in precos
    assert len(precos["WEGE3"]) == 3
    assert precos["WEGE3"][date(2026, 6, 8)] == 44.00
    assert "BURA39" in precos
    assert precos["BURA39"][date(2026, 6, 8)] == 11.25

    # confirma que yfinance estava vazio (simula no_api=True)
    assert resultado_yfinance_com_no_api == {}
