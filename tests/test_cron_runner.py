"""
tests/test_cron_runner.py — Orquestração dos jobs agendados (Fase 6 da
fatia "Ingestão de dados"). Não testa o agendamento do APScheduler em si
(seria um teste de integração de tempo real) — testa que cada job chama as
funções certas, na ordem certa, com os dados certos.

Casos:
  1) job_cotacoes: POST /api/v1/calcular no backend (não recalcular()
     direto — é o fix pro bug de estado obsoleto entre processos) e
     depois coleta proventos dos tickers da carteira.
  2) job_fundamentos_peers: sem tickers da carteira → não tenta nada;
     com tickers → define universo e coleta fundamentos do universo
     completo (carteira + peers), não só da carteira.
  3) job_noticias: só coleta se houver tickers.
  4) job_taxonomia / job_eventos_ipe: delegação direta.

Rodar:
    pytest tests/test_cron_runner.py -v
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.scripts import cron_runner as cr


def _mock_estado(tickers):
    return {"ativos": {t: {} for t in tickers}}


# ─── 1: job_cotacoes ─────────────────────────────────────────────────────────

def test_job_cotacoes_chama_api_http_nao_recalcular_direto():
    resp = MagicMock()
    resp.json.return_value = {"ok": True}
    resp.raise_for_status = MagicMock()

    with patch("carteira_clean_web.backend.scripts.cron_runner.requests.post", return_value=resp) as mock_post, \
         patch.object(cr, "_tickers_carteira", return_value=["ITUB3"]), \
         patch("carteira_clean_web.backend.engine.proventos_brapi.coletar_proventos") as mock_prov:
        cr.job_cotacoes()

    mock_post.assert_called_once_with(
        "http://backend:8000/api/v1/calcular", params={"no_api": "false"}, timeout=300,
    )
    mock_prov.assert_called_once_with(["ITUB3"])


def test_job_cotacoes_propaga_erro_http_sem_coletar_proventos():
    resp = MagicMock()
    resp.raise_for_status.side_effect = ConnectionError("backend fora do ar")

    with patch("carteira_clean_web.backend.scripts.cron_runner.requests.post", return_value=resp), \
         patch("carteira_clean_web.backend.engine.proventos_brapi.coletar_proventos") as mock_prov:
        try:
            cr.job_cotacoes()
            assert False, "deveria ter propagado a exceção"
        except ConnectionError:
            pass
    mock_prov.assert_not_called()


# ─── 2: job_fundamentos_peers ────────────────────────────────────────────────

def test_job_fundamentos_peers_sem_carteira_nao_faz_nada():
    with patch.object(cr, "_tickers_carteira", return_value=[]), \
         patch("carteira_clean_web.backend.engine.peers.definir_universo_peers") as mock_def, \
         patch("carteira_clean_web.backend.engine.fundamentos_brapi.coletar_fundamentos_peers") as mock_col:
        cr.job_fundamentos_peers()
    mock_def.assert_not_called()
    mock_col.assert_not_called()


def test_job_fundamentos_peers_usa_universo_completo():
    with patch.object(cr, "_tickers_carteira", return_value=["ITUB3"]), \
         patch("carteira_clean_web.backend.engine.peers.definir_universo_peers") as mock_def, \
         patch("carteira_clean_web.backend.engine.peers.carregar_universo_peers", return_value=["ITUB3", "BBDC4"]), \
         patch("carteira_clean_web.backend.engine.fundamentos_brapi.coletar_fundamentos_peers") as mock_col:
        cr.job_fundamentos_peers()
    mock_def.assert_called_once_with(["ITUB3"])
    mock_col.assert_called_once_with(["ITUB3", "BBDC4"])  # universo, não só carteira


# ─── 3: job_noticias ──────────────────────────────────────────────────────────

def test_job_noticias_sem_carteira_nao_coleta():
    with patch.object(cr, "_tickers_carteira", return_value=[]), \
         patch("carteira_clean_web.backend.engine.noticias_rss.coletar_noticias") as mock_col:
        cr.job_noticias()
    mock_col.assert_not_called()


def test_job_noticias_com_carteira_coleta():
    with patch.object(cr, "_tickers_carteira", return_value=["ITUB3", "PETR4"]), \
         patch("carteira_clean_web.backend.engine.noticias_rss.coletar_noticias") as mock_col:
        cr.job_noticias()
    mock_col.assert_called_once_with(["ITUB3", "PETR4"])


# ─── 4: delegação direta ─────────────────────────────────────────────────────

def test_job_taxonomia_delega():
    with patch("carteira_clean_web.backend.engine.taxonomia.coletar_taxonomia_setorial") as mock_col:
        cr.job_taxonomia()
    mock_col.assert_called_once()


def test_job_eventos_ipe_popula_cnpj_antes_de_coletar():
    with patch.object(cr, "_tickers_carteira", return_value=["ITUB3"]), \
         patch("carteira_clean_web.backend.engine.eventos_cvm.popular_cnpj_ativos") as mock_cnpj, \
         patch("carteira_clean_web.backend.engine.eventos_cvm.coletar_eventos_ipe") as mock_col:
        cr.job_eventos_ipe()
    mock_cnpj.assert_called_once_with(["ITUB3"])
    mock_col.assert_called_once()


def test_job_eventos_ipe_sem_carteira_so_coleta():
    with patch.object(cr, "_tickers_carteira", return_value=[]), \
         patch("carteira_clean_web.backend.engine.eventos_cvm.popular_cnpj_ativos") as mock_cnpj, \
         patch("carteira_clean_web.backend.engine.eventos_cvm.coletar_eventos_ipe") as mock_col:
        cr.job_eventos_ipe()
    mock_cnpj.assert_not_called()
    mock_col.assert_called_once()


# ─── _tickers_carteira ────────────────────────────────────────────────────────

def test_tickers_carteira_cache_vazio_retorna_lista_vazia():
    with patch("carteira_clean_web.backend.api.cache.esta_calculado", return_value=False), \
         patch("carteira_clean_web.backend.api.cache.carregar_disco"):
        assert cr._tickers_carteira() == []


def test_tickers_carteira_le_do_cache():
    with patch("carteira_clean_web.backend.api.cache.esta_calculado", return_value=True), \
         patch("carteira_clean_web.backend.api.cache.get_estado", return_value=_mock_estado(["ITUB3", "PETR4"])):
        assert sorted(cr._tickers_carteira()) == ["ITUB3", "PETR4"]
