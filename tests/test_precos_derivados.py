"""
tests/test_precos_derivados.py — Preços derivados (LCI/CVM/Tesouro) persistidos
na tabela cotacoes (append-only), fonte de verdade independente de no_api.

Casos:
  1) Ponto persistido sobrevive a atualizar_precos_derivados(no_api=True).
  2) Duas chamadas consecutivas no_api=True são deterministas (sem linha nova).
  3) Correção de preço = nova linha vence; linha antiga permanece na tabela.
  4) Desempate por id DESC quando fetched_at empata.
  5) Unitários: serie vazia é no-op; leitura tolera falha de sessão.

Rodar:
    pytest tests/test_precos_derivados.py -v
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from carteira_clean_web.backend.engine.precos import (
    _gravar_cotacoes_derivadas,
    carregar_precos_derivados_da_tabela,
    atualizar_precos_derivados,
)

D0 = date(2026, 1, 2)
D1 = date(2026, 1, 5)
D2 = date(2026, 1, 6)


def _seed(engine, ticker, dt, preco, fetched_at, source):
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO cotacoes (ticker, date, preco, fetched_at, source) "
                "VALUES (:ticker, :date, :preco, :fetched_at, :source)"
            ),
            {"ticker": ticker, "date": dt, "preco": preco, "fetched_at": fetched_at, "source": source},
        )
        conn.commit()


def _count(engine, ticker=None):
    with engine.connect() as conn:
        if ticker:
            return conn.execute(
                text("SELECT COUNT(*) FROM cotacoes WHERE ticker = :t"), {"t": ticker}
            ).scalar()
        return conn.execute(text("SELECT COUNT(*) FROM cotacoes")).scalar()


# ── Teste 1: ponto persistido sobrevive a no_api=True ──────────────────────

def test_persistido_sobrevive_no_api_true(patch_session, sqlite_engine):
    _seed(sqlite_engine, "LCI_TESTE", D0, 28347.07, "2026-07-08T10:00:00", "curva_lci")
    _seed(sqlite_engine, "FUNDO_TESTE", D0, 3.027147, "2026-07-08T10:00:00", "cvm")

    ativos = {
        "FUNDO_TESTE": {"cnpj_cvm": "12.345.678/0001-99", "familia": "Fundo CP", "composite": "Gerida"},
        "LCI_TESTE": {"familia": "Letra de Crédito", "composite": "Gerida"},
    }
    eventos = [
        {"data": D0, "ativo": "LCI_TESTE", "tipo": "COMPRA",
         "qtd": None, "valor": 1000.0, "obs": "CDI: 100,00%"},
    ]

    resultado = atualizar_precos_derivados(
        ativos, eventos, precos_manuais={}, data_inicio=D0, data_fim=D2, no_api=True,
    )

    assert resultado["LCI_TESTE"][D0] == 28347.07
    assert resultado["FUNDO_TESTE"][D0] == 3.027147


# ── Teste 2: duas chamadas consecutivas no_api=True são deterministas ──────

def test_determinismo_duas_chamadas_no_api_true(patch_session, sqlite_engine):
    _seed(sqlite_engine, "LCI_TESTE", D0, 28347.07, "2026-07-08T10:00:00", "curva_lci")
    ativos = {"LCI_TESTE": {"familia": "Letra de Crédito", "composite": "Gerida"}}
    eventos = [
        {"data": D0, "ativo": "LCI_TESTE", "tipo": "COMPRA",
         "qtd": None, "valor": 1000.0, "obs": "CDI: 100,00%"},
    ]

    antes = _count(sqlite_engine)
    r1 = atualizar_precos_derivados(ativos, eventos, {}, D0, D2, no_api=True)
    r2 = atualizar_precos_derivados(ativos, eventos, {}, D0, D2, no_api=True)
    depois = _count(sqlite_engine)

    assert r1 == r2
    assert antes == depois, "no_api=True nunca deve gravar linha nova"


# ── Teste 3: correção de preço = nova linha vence, antiga permanece ────────

def test_correcao_vence_linha_antiga_permanece(patch_session, sqlite_engine):
    _seed(sqlite_engine, "FUNDO_TESTE", D0, 3.0000, "2026-07-01T10:00:00", "cvm")

    _gravar_cotacoes_derivadas("FUNDO_TESTE", {D0: 3.05}, "cvm")  # delta relativo > 1e-5

    lidos = carregar_precos_derivados_da_tabela(("cvm",))
    assert lidos["FUNDO_TESTE"][D0] == 3.05

    assert _count(sqlite_engine, "FUNDO_TESTE") == 2, "linha antiga não pode ser apagada/alterada"


def test_correcao_dentro_da_tolerancia_nao_insere(patch_session, sqlite_engine):
    _seed(sqlite_engine, "FUNDO_TESTE", D0, 3.000000, "2026-07-01T10:00:00", "cvm")

    _gravar_cotacoes_derivadas("FUNDO_TESTE", {D0: 3.0000001}, "cvm")  # bem abaixo de 1e-5 relativo

    assert _count(sqlite_engine, "FUNDO_TESTE") == 1


# ── Teste 4: desempate por id DESC quando fetched_at empata ────────────────

def test_desempate_por_id_quando_fetched_at_empata(patch_session, sqlite_engine):
    mesmo_instante = "2026-07-08T10:00:00"
    _seed(sqlite_engine, "LCI_TESTE", D0, 100.0, mesmo_instante, "curva_lci")
    _seed(sqlite_engine, "LCI_TESTE", D0, 200.0, mesmo_instante, "curva_lci")  # id maior, mesmo fetched_at

    lidos = carregar_precos_derivados_da_tabela(("curva_lci",))
    assert lidos["LCI_TESTE"][D0] == 200.0, "deve vencer o maior id em caso de empate de fetched_at"


# ── Unitários ───────────────────────────────────────────────────────────────

def test_gravar_com_serie_vazia_e_no_op(patch_session, sqlite_engine):
    _gravar_cotacoes_derivadas("QUALQUER", {}, "cvm")
    assert _count(sqlite_engine) == 0


def test_carregar_retorna_vazio_em_falha_de_sessao(monkeypatch):
    def _quebra():
        raise RuntimeError("sem conexão")

    monkeypatch.setattr(
        "carteira_clean_web.backend.db.session.get_session", lambda: _quebra()
    )
    assert carregar_precos_derivados_da_tabela() == {}
