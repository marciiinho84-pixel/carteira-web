"""
tests/test_eventos_cvm.py — Fatos relevantes/avisos/calendário via IPE CVM
(Fase 4.2 da fatia "Ingestão de dados").

Casos:
  1) _normalizar_cnpj: mantém só dígitos.
  2) _achar_coluna: match exato, fallback por substring, None se não achar.
  3) coletar_eventos_ipe: filtra categoria + casa CNPJ, grava com tipo/fonte
     corretos; ignora linha com categoria fora do alvo ou CNPJ não cadastrado;
     sem nenhum ativo com cnpj_cvm → inválido sem tentar baixar; falha no
     download → inválido sem crash; coluna essencial ausente → inválido.

Rodar:
    pytest tests/test_eventos_cvm.py -v
"""
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.engine import eventos_cvm as ec
from carteira_clean_web.backend.db.models import Ativo, EventoCorporativo, JobRun


# ─── 1-2: helpers ────────────────────────────────────────────────────────────

def test_normalizar_cnpj_mantem_so_digitos():
    assert ec._normalizar_cnpj("60.872.504/0001-23") == "60872504000123"


@pytest.mark.parametrize("colunas,candidatos,esperado", [
    (["CNPJ_Companhia", "Categoria"], ["cnpj_companhia"], "CNPJ_Companhia"),
    (["Cnpj_Cia_Aberta"], ["cnpj_companhia", "cnpj_cia"], "Cnpj_Cia_Aberta"),  # fallback substring
    (["Outra_Coisa"], ["cnpj_companhia", "cnpj_cia"], None),
])
def test_achar_coluna(colunas, candidatos, esperado):
    df = pd.DataFrame(columns=colunas)
    assert ec._achar_coluna(df, candidatos) == esperado


# ─── 3: coletar_eventos_ipe ──────────────────────────────────────────────────

@pytest.fixture
def patch_ec_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ec.db'}", connect_args={"check_same_thread": False})
    Ativo.metadata.create_all(engine, tables=[Ativo.__table__, EventoCorporativo.__table__, JobRun.__table__])
    Session = sessionmaker(bind=engine)
    with patch(
        "carteira_clean_web.backend.engine.eventos_cvm.get_session",
        side_effect=lambda: Session(),
    ), patch(
        "carteira_clean_web.backend.engine.ingestao_utils.get_session",
        side_effect=lambda: Session(),
    ):
        yield Session


def _seed_ativo(Session, ticker, cnpj):
    db = Session()
    db.add(Ativo(ticker=ticker, cnpj_cvm=cnpj, composite="Gerida"))
    db.commit()
    db.close()


def _df_fake():
    return pd.DataFrame([
        {"CNPJ_Companhia": "60.872.504/0001-23", "Categoria": "Fato Relevante",
         "Data_Referencia": "2026-06-01", "Assunto": "Aquisição de ativo"},
        {"CNPJ_Companhia": "60.872.504/0001-23", "Categoria": "Aviso aos Acionistas",
         "Data_Referencia": "2026-05-15", "Assunto": "Pagamento de JCP"},
        {"CNPJ_Companhia": "60.872.504/0001-23", "Categoria": "Categoria Irrelevante",
         "Data_Referencia": "2026-05-01", "Assunto": "Não deve entrar"},
        {"CNPJ_Companhia": "00.000.000/0001-00", "Categoria": "Fato Relevante",
         "Data_Referencia": "2026-05-01", "Assunto": "CNPJ não cadastrado — não deve entrar"},
    ])


def test_coletar_eventos_ipe_filtra_e_casa_cnpj(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", "60.872.504/0001-23")

    with patch("carteira_clean_web.backend.engine.eventos_cvm._baixar_ipe", return_value=_df_fake()):
        resultado = ec.coletar_eventos_ipe(ano=2026)

    assert resultado["linhas_gravadas"] == 2
    db = Session()
    rows = db.query(EventoCorporativo).filter(EventoCorporativo.ticker == "ITUB3").all()
    tipos = {r.tipo for r in rows}
    db.close()
    assert tipos == {"FATO_RELEVANTE", "AVISO_ACIONISTAS"}
    assert all(r.fonte == "cvm_ipe" for r in rows)


def test_coletar_eventos_ipe_idempotente(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", "60.872.504/0001-23")

    with patch("carteira_clean_web.backend.engine.eventos_cvm._baixar_ipe", return_value=_df_fake()):
        ec.coletar_eventos_ipe(ano=2026)
        ec.coletar_eventos_ipe(ano=2026)  # 2ª coleta — não duplica

    db = Session()
    rows = db.query(EventoCorporativo).filter(EventoCorporativo.ticker == "ITUB3").all()
    db.close()
    assert len(rows) == 2


def test_coletar_eventos_ipe_sem_cnpj_cadastrado_nao_baixa(patch_ec_session):
    with patch("carteira_clean_web.backend.engine.eventos_cvm._baixar_ipe") as mock_baixar:
        resultado = ec.coletar_eventos_ipe(ano=2026)
    mock_baixar.assert_not_called()
    assert resultado["linhas_invalidas"] == 1


def test_coletar_eventos_ipe_falha_download_nao_crasha(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", "60.872.504/0001-23")
    with patch("carteira_clean_web.backend.engine.eventos_cvm._baixar_ipe", side_effect=ConnectionError("fora do ar")):
        resultado = ec.coletar_eventos_ipe(ano=2026)
    assert resultado == {"linhas_gravadas": 0, "linhas_invalidas": 1}


def test_coletar_eventos_ipe_coluna_essencial_ausente(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", "60.872.504/0001-23")
    df_sem_categoria = pd.DataFrame([{"CNPJ_Companhia": "60.872.504/0001-23", "Data_Referencia": "2026-06-01"}])
    with patch("carteira_clean_web.backend.engine.eventos_cvm._baixar_ipe", return_value=df_sem_categoria):
        resultado = ec.coletar_eventos_ipe(ano=2026)
    assert resultado["linhas_invalidas"] == 1
    assert resultado["linhas_gravadas"] == 0


# ─── popular_cnpj_ativos ──────────────────────────────────────────────────────

def test_popular_cnpj_ativos_preenche_via_summary_profile(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", None)
    resp = {"results": [{"summaryProfile": {"cnpj": "60872504000123"}}]}

    with patch("carteira_clean_web.backend.engine.eventos_cvm.brapi_client.get", return_value=resp):
        resultado = ec.popular_cnpj_ativos(["ITUB3"])

    assert resultado == {"linhas_gravadas": 1, "linhas_invalidas": 0}
    db = Session()
    ativo = db.query(Ativo).filter(Ativo.ticker == "ITUB3").first()
    db.close()
    assert ativo.cnpj_cvm == "60872504000123"


def test_popular_cnpj_ativos_nao_sobrescreve_cadastro_existente(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "ITUB3", "11.111.111/0001-11")

    with patch("carteira_clean_web.backend.engine.eventos_cvm.brapi_client.get") as mock_get:
        resultado = ec.popular_cnpj_ativos(["ITUB3"])

    mock_get.assert_not_called()
    assert resultado == {"linhas_gravadas": 0, "linhas_invalidas": 0}
    db = Session()
    ativo = db.query(Ativo).filter(Ativo.ticker == "ITUB3").first()
    db.close()
    assert ativo.cnpj_cvm == "11.111.111/0001-11"


def test_popular_cnpj_ativos_sem_cnpj_no_payload_conta_invalido(patch_ec_session):
    Session = patch_ec_session
    _seed_ativo(Session, "XPTO11", None)

    with patch("carteira_clean_web.backend.engine.eventos_cvm.brapi_client.get", return_value={"results": []}):
        resultado = ec.popular_cnpj_ativos(["XPTO11"])

    assert resultado == {"linhas_gravadas": 0, "linhas_invalidas": 1}
