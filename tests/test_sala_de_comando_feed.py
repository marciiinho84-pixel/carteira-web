"""
tests/test_sala_de_comando_feed.py — _build_observacoes (sala_de_comando.py).

Cobre a extração de campos extra de fundamentos_json por categoria: "url"
pra NOTICIA (bug: ficava presa no banco e nunca chegava no frontend) e
"ativos_relacionados" pra MACRO (já existia).
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from carteira_clean_web.backend.db.models import Base, ObservacaoFeed
from carteira_clean_web.backend.api.routers.sala_de_comando import _build_observacoes


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_noticia_expoe_url_de_fundamentos_json(db):
    db.add(ObservacaoFeed(
        categoria="NOTICIA", ativo="PETR4", referencia_id=1,
        conteudo='PETR4: "Petrobras anuncia projeto" (InfoMoney)',
        fundamentos_json=json.dumps({"titulo": "Petrobras anuncia projeto", "fonte": "InfoMoney",
                                       "url": "https://infomoney.com.br/abc", "publicado_em": None}),
        criado_em=datetime.utcnow(), visualizado_em=None,
    ))
    db.commit()

    itens = _build_observacoes(db)
    assert len(itens) == 1
    assert itens[0]["url"] == "https://infomoney.com.br/abc"
    assert itens[0]["ativo"] == "PETR4"


def test_noticia_sem_url_retorna_none(db):
    db.add(ObservacaoFeed(
        categoria="NOTICIA", ativo="PETR4", referencia_id=1,
        conteudo="PETR4: notícia sem url",
        fundamentos_json=json.dumps({"titulo": "sem url", "fonte": None, "url": None}),
        criado_em=datetime.utcnow(), visualizado_em=None,
    ))
    db.commit()

    itens = _build_observacoes(db)
    assert itens[0]["url"] is None


def test_outras_categorias_nao_expoe_url(db):
    db.add(ObservacaoFeed(
        categoria="ALERTA", ativo="PETR4", referencia_id=1,
        conteudo="PETR4 RSI 75 cruzou >= 70",
        fundamentos_json=json.dumps({"alerta_id": 1, "tipo": "RSI"}),
        criado_em=datetime.utcnow(), visualizado_em=None,
    ))
    db.commit()

    itens = _build_observacoes(db)
    assert itens[0]["url"] is None


def test_macro_continua_expondo_ativos_relacionados(db):
    db.add(ObservacaoFeed(
        categoria="MACRO", ativo=None, referencia_id=None,
        conteudo="Regime macro: juros mudou para \"subindo\" — afeta ITUB3",
        fundamentos_json=json.dumps({"ativos_carteira_afetados": [{"ticker": "ITUB3"}]}),
        criado_em=datetime.utcnow(), visualizado_em=None,
    ))
    db.commit()

    itens = _build_observacoes(db)
    assert itens[0]["ativos_relacionados"] == ["ITUB3"]
    assert itens[0]["url"] is None
