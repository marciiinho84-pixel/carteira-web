"""
Testes do motor de varredura da Sala de Comando (engine/varredura_feed.py).

Cobre as 7 categorias de sinal (edge-triggered: emite só na transição pra um
estado de sinal, nunca repete enquanto a condição persiste), o caso "sem
sinal" (ausência de dado/mudança é resultado válido, não motivo pra
fabricar) e a deduplicação (mesmo evento não gera duas linhas).

Usa SQLite em memória com o mesmo schema de produção (Base.metadata) e
mocka as tools MCP / helpers de sala_de_comando chamados internamente —
o motor de varredura em si (transição de estado, dedupe, gravação) é o
alvo do teste, não as tools de terceiros que ele consome.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from carteira_clean_web.backend.db.models import (
    Alerta, Base, Noticia, ObservacaoFeed, Tese, VarreduraEstado,
)
from carteira_clean_web.backend.engine import varredura_feed as vf


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _n(db, categoria: str) -> int:
    return db.query(ObservacaoFeed).filter(ObservacaoFeed.categoria == categoria).count()


# ─── Categoria 1: Alerta ─────────────────────────────────────────────────────

def test_alerta_dispara_e_nao_repete_enquanto_persiste(db):
    a = Alerta(tipo="RSI", ativo="PETR4", condicao=">=", valor_gatilho=70, ativo_bool=1, criado_em=datetime.utcnow())
    db.add(a)
    db.commit()

    hit = {"alerta_id": a.id, "tipo": "RSI", "ativo": "PETR4", "mensagem": "PETR4 RSI 75 cruzou >= 70", "valor_atual": 75}

    with patch.object(vf, "_transicionou", wraps=vf._transicionou):
        with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_verificar_alertas",
                   return_value={"disparados": []}):
            n1 = vf._varrer_alertas(db)  # baseline: ok, sem alerta anterior -> sem emissão
    assert n1 == 0
    assert _n(db, "ALERTA") == 0

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_verificar_alertas",
               return_value={"disparados": [hit]}):
        n2 = vf._varrer_alertas(db)  # transição ok -> disparado
        n3 = vf._varrer_alertas(db)  # ainda disparado -> não repete

    assert n2 == 1
    assert n3 == 0
    assert _n(db, "ALERTA") == 1
    item = db.query(ObservacaoFeed).filter_by(categoria="ALERTA").first()
    assert item.referencia_id == a.id
    assert item.ativo == "PETR4"
    assert "RSI" in item.conteudo


def test_alerta_sem_alertas_cadastrados_nao_fabrica(db):
    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_verificar_alertas",
               return_value={"total": 0, "disparados": [], "nota": "Nenhum alerta cadastrado."}):
        n = vf._varrer_alertas(db)
    assert n == 0
    assert _n(db, "ALERTA") == 0


# ─── Categoria 2: Tese invalidada ────────────────────────────────────────────

def test_tese_invalidada_emite_uma_vez(db):
    t = Tese(ticker="WEGE3", racional="tese X", nivel_invalidacao="VERDE",
              data_criacao=datetime.utcnow().date(), status="ATIVA")
    db.add(t)
    db.commit()

    assert vf._varrer_teses(db) == 0  # baseline ATIVA, sem emissão

    t.status = "INVALIDADA"
    t.criterio_invalidacao = "queda de 20% no preço-alvo"
    db.commit()
    assert vf._varrer_teses(db) == 1

    item = db.query(ObservacaoFeed).filter_by(categoria="TESE").first()
    assert item.ativo == "WEGE3"
    assert item.referencia_id == t.id
    assert "invalidada" in item.conteudo

    # roda de novo sem mudança — não duplica
    assert vf._varrer_teses(db) == 0
    assert _n(db, "TESE") == 1


def test_tese_ativa_sem_mudanca_nao_gera_fato(db):
    t = Tese(ticker="ITUB3", racional="tese Y", nivel_invalidacao="VERDE",
              data_criacao=datetime.utcnow().date(), status="ATIVA")
    db.add(t)
    db.commit()
    vf._varrer_teses(db)
    vf._varrer_teses(db)
    assert _n(db, "TESE") == 0


# ─── Categoria 3: Desvio de banda IPS ────────────────────────────────────────

def test_ips_desvio_de_banda_emite_na_transicao(db):
    kpis_ok = {"engine_ok": True, "patrimonio_gerida": 100_000.0}
    bloco_ok = {"bloco": "SWING_TRADE", "pct_real": 0.30, "pct_alvo": 0.30, "banda_min": 0.20, "banda_max": 0.40, "status": "OK"}
    bloco_abaixo = {**bloco_ok, "pct_real": 0.05, "status": "ABAIXO"}

    with patch("carteira_clean_web.backend.api.routers.sala_de_comando._build_kpis", return_value=kpis_ok), \
         patch("carteira_clean_web.backend.api.routers.sala_de_comando._calc_blocos_ips", return_value=[bloco_ok]):
        assert vf._varrer_ips(db) == 0  # baseline OK, sem emissão

    with patch("carteira_clean_web.backend.api.routers.sala_de_comando._build_kpis", return_value=kpis_ok), \
         patch("carteira_clean_web.backend.api.routers.sala_de_comando._calc_blocos_ips", return_value=[bloco_abaixo]):
        assert vf._varrer_ips(db) == 1

    item = db.query(ObservacaoFeed).filter_by(categoria="IPS").first()
    assert "Swing Trade" in item.conteudo
    assert "abaixo" in item.conteudo


def test_ips_engine_nao_calculado_nao_fabrica(db):
    with patch("carteira_clean_web.backend.api.routers.sala_de_comando._build_kpis", return_value={"engine_ok": False}):
        assert vf._varrer_ips(db) == 0
    assert _n(db, "IPS") == 0


# ─── Categoria 4: Gatilho técnico ────────────────────────────────────────────

def test_tecnico_mudanca_de_rating_emite(db):
    neutro = {"ticker": "PRIO3", "rating_geral": 0.1, "rating_texto": "neutro", "sinais": []}
    compra = {"ticker": "PRIO3", "rating_geral": 0.8, "rating_texto": "compra", "sinais": ["MM20 acima da MM50"]}

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_tecnica", return_value=neutro):
        assert vf._varrer_tecnico(db, ["PRIO3"]) == 0  # baseline, sem emissão

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_tecnica", return_value=compra):
        assert vf._varrer_tecnico(db, ["PRIO3"]) == 1
        assert vf._varrer_tecnico(db, ["PRIO3"]) == 0  # ainda compra, não repete

    item = db.query(ObservacaoFeed).filter_by(categoria="TECNICO").first()
    assert item.ativo == "PRIO3"
    assert "compra" in item.conteudo


def test_tecnico_sem_dados_nao_fabrica(db):
    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_tecnica",
               return_value={"erro": "Sem dados OHLCV para XPTO3."}):
        assert vf._varrer_tecnico(db, ["XPTO3"]) == 0
    assert _n(db, "TECNICO") == 0


# ─── Categoria 5: Gatilho fundamentalista ───────────────────────────────────

def test_fundamentalista_cruza_limiar_emite(db):
    na_media = {"dimensoes": {"valuation": [
        {"indicador": "P/L", "valor_atual": 10.0, "media_setor": 10.5, "posicao": "na média"},
    ]}}
    abaixo = {"dimensoes": {"valuation": [
        {"indicador": "P/L", "valor_atual": 5.0, "media_setor": 10.5, "posicao": "abaixo da média"},
    ]}}

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_fundamentalista", return_value=na_media):
        assert vf._varrer_fundamentalista(db, ["BBAS3"]) == 0

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_fundamentalista", return_value=abaixo):
        assert vf._varrer_fundamentalista(db, ["BBAS3"]) == 1

    item = db.query(ObservacaoFeed).filter_by(categoria="FUNDAMENTALISTA").first()
    assert item.ativo == "BBAS3"
    assert "P/L" in item.conteudo


def test_fundamentalista_sem_fundamentos_nao_fabrica(db):
    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_analise_fundamentalista",
               return_value={"erro": "Sem fundamentos para XPTO3."}):
        assert vf._varrer_fundamentalista(db, ["XPTO3"]) == 0
    assert _n(db, "FUNDAMENTALISTA") == 0


# ─── Categoria 6: Notícia relevante ──────────────────────────────────────────

def test_noticia_nova_emite_e_nao_duplica(db):
    n1 = Noticia(ticker="PETR4", titulo="PETR4 anuncia dividendos", fonte="InfoMoney",
                 url="https://x", publicado_em=datetime.utcnow(), coletado_em=datetime.utcnow())
    db.add(n1)
    db.commit()

    assert vf._varrer_noticias(db, ["PETR4"]) == 1
    assert vf._varrer_noticias(db, ["PETR4"]) == 0  # já emitida, não duplica

    item = db.query(ObservacaoFeed).filter_by(categoria="NOTICIA").first()
    assert item.ativo == "PETR4"
    assert item.referencia_id == n1.id


def test_noticia_antiga_fora_da_janela_nao_entra(db):
    velha = Noticia(ticker="PETR4", titulo="Notícia de 30 dias atrás", fonte="X",
                     publicado_em=datetime.utcnow() - timedelta(days=30),
                     coletado_em=datetime.utcnow() - timedelta(days=30))
    db.add(velha)
    db.commit()
    assert vf._varrer_noticias(db, ["PETR4"]) == 0


def test_noticia_sem_posicoes_nao_fabrica(db):
    assert vf._varrer_noticias(db, []) == 0


# ─── Categoria 7: Fato macro relevante ──────────────────────────────────────

def test_macro_muda_regime_e_afeta_posicao_emite(db):
    regime_estavel = {"juros": {"classificacao": "estavel"}, "inflacao": {"classificacao": "controlada"},
                       "cambio": {"classificacao": "estavel"}}
    regime_subindo = {"juros": {"classificacao": "subindo"}, "inflacao": {"classificacao": "controlada"},
                       "cambio": {"classificacao": "estavel"}}
    impacto_com_ativo = {"ativos_carteira_afetados": [{"ticker": "ITUB3", "setor": "Bancos", "direcao": "negativo", "peso": 3}]}

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_regime_mercado", return_value=regime_estavel):
        assert vf._varrer_macro(db) == 0  # baseline

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_regime_mercado", return_value=regime_subindo), \
         patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_impacto_macro", return_value=impacto_com_ativo):
        assert vf._varrer_macro(db) == 1

    item = db.query(ObservacaoFeed).filter_by(categoria="MACRO").first()
    assert item.ativo is None
    assert "ITUB3" in item.conteudo


def test_macro_muda_regime_sem_posicao_afetada_nao_fabrica(db):
    regime_estavel = {"juros": {"classificacao": "estavel"}, "inflacao": {"classificacao": "controlada"},
                       "cambio": {"classificacao": "estavel"}}
    regime_subindo = {"juros": {"classificacao": "subindo"}, "inflacao": {"classificacao": "controlada"},
                       "cambio": {"classificacao": "estavel"}}

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_regime_mercado", return_value=regime_estavel):
        vf._varrer_macro(db)

    with patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_regime_mercado", return_value=regime_subindo), \
         patch("carteira_clean_web.backend.mcp.tools.portfolio.fn_impacto_macro",
               return_value={"ativos_carteira_afetados": []}):
        assert vf._varrer_macro(db) == 0
    assert _n(db, "MACRO") == 0


# ─── Orquestrador ────────────────────────────────────────────────────────────

def test_rodar_varredura_isola_falha_por_categoria(db):
    """Uma categoria que lança exceção não deve impedir as demais de rodar."""
    with patch("carteira_clean_web.backend.api.cache.esta_calculado", return_value=False), \
         patch.object(vf, "_varrer_alertas", side_effect=RuntimeError("boom")), \
         patch.object(vf, "_varrer_teses", return_value=0), \
         patch.object(vf, "_varrer_ips", return_value=0), \
         patch.object(vf, "_varrer_tecnico", return_value=0), \
         patch.object(vf, "_varrer_fundamentalista", return_value=0), \
         patch.object(vf, "_varrer_noticias", return_value=0), \
         patch.object(vf, "_varrer_macro", return_value=0):
        resultado = vf.rodar_varredura(db)

    assert resultado["ALERTA"] == 0
    assert set(resultado.keys()) == {"ALERTA", "TESE", "IPS", "TECNICO", "FUNDAMENTALISTA", "NOTICIA", "MACRO"}
