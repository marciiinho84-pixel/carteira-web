"""
tests/test_analise_fundamentalista_peers.py — fn_analise_fundamentalista
resolvendo peers via taxonomia_setorial (não mais ativos.setor), Fase 3.

Caso: ticker com fundamentos + 2 peers com fundamentos no mesmo índice →
n_peers_setor > 0 e media_setor calculada (bug original: peers só existiam
dentro da própria carteira via ativos.setor, quase sempre 0).

Rodar:
    pytest tests/test_analise_fundamentalista_peers.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from carteira_clean_web.backend.mcp.tools import portfolio


def test_analise_fundamentalista_usa_peers_fora_da_carteira():
    fundamentos_fake = {
        "ITUB3": [{"indicador": "ROE", "valor": 18.0, "fetched_at": "2026-07-01", "data_referencia": "2026-07-01"}],
        "BBDC4": [{"indicador": "ROE", "valor": 20.0, "fetched_at": "2026-07-01", "data_referencia": "2026-07-01"}],
        "SANB11": [{"indicador": "ROE", "valor": 16.0, "fetched_at": "2026-07-01", "data_referencia": "2026-07-01"}],
    }
    with patch.object(portfolio, "_carregar_fundamentos_db", return_value=fundamentos_fake), \
         patch(
             "carteira_clean_web.backend.engine.peers.peers_do_mesmo_setor",
             return_value=["BBDC4", "SANB11", "TICKER_SEM_FUNDAMENTOS11"],
         ):
        resultado = portfolio.fn_analise_fundamentalista("ITUB3")

    assert resultado["n_peers_setor"] == 2  # BBDC4 + SANB11 (o 3º não tem fundamentos)
    assert resultado["dimensoes"]["rentabilidade"][0]["media_setor"] == 18.0  # (20+16)/2
