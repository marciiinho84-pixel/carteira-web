"""
engine/peers.py — Universo de peers para comparação fundamentalista.

Define quais tickers, além dos ~38 da carteira, têm fundamentos coletados:
para cada setor_brapi presente na carteira, os top 8 tickers por volume
(via brapi /api/quote/list?sector=X&sortBy=volume). Persistido em
universo_peers — só direciona a COLETA; a leitura de peers em tempo real
(fn_analise_fundamentalista/comparar_multiplos) usa taxonomia_setorial +
fundamentos diretamente (ver engine/taxonomia.py::mapear_setor_para_indice).
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from . import brapi_client, taxonomia
from .ingestao_utils import get_logger, registrar_job_run, upsert_df
from ..db.models import UniversoPeer
from ..db.session import get_session

log = get_logger("peers")

_TOP_N_POR_SETOR = 8


def _top_tickers_por_setor(setor_brapi: str, top_n: int = _TOP_N_POR_SETOR) -> list[str]:
    resp = brapi_client.get("quote/list", {
        "sector": setor_brapi,
        "sortBy": "volume",
        "sortOrder": "desc",
        "limit": top_n,
    })
    stocks = resp.get("stocks", [])
    out = []
    for item in stocks[:top_n]:
        ticker = item.get("stock") or item.get("ticker")
        if ticker:
            out.append(ticker.upper())
    return out


def definir_universo_peers(tickers_carteira: list[str]) -> dict:
    """Monta o universo = tickers_carteira ∪ top 8 por volume de cada setor
    presente na carteira. UPSERT em universo_peers. Retorna resumo."""
    with registrar_job_run("universo_peers") as job:
        tickers_carteira = [t.upper() for t in tickers_carteira]
        taxonomia_map = taxonomia.carregar_taxonomia_completa()

        setores_carteira = sorted({
            taxonomia_map[t] for t in tickers_carteira
            if taxonomia_map.get(t)
        })

        linhas: dict[str, dict] = {
            t: {"ticker": t, "setor": taxonomia_map.get(t), "motivo": "carteira"}
            for t in tickers_carteira
        }

        invalidas = 0
        for setor in setores_carteira:
            try:
                peers = _top_tickers_por_setor(setor)
            except Exception as e:
                log.warning(f"universo_peers: falha ao buscar peers do setor '{setor}' — {e}")
                invalidas += 1
                continue
            for t in peers:
                if t not in linhas:
                    linhas[t] = {"ticker": t, "setor": setor, "motivo": f"peer_setor:{setor}"}

        n = 0
        if linhas:
            df = pd.DataFrame(list(linhas.values()))
            df["adicionado_em"] = datetime.utcnow()
            with get_session() as db:
                n = upsert_df(db, UniversoPeer.__table__, ["ticker"], df)

        job.linhas_gravadas = n
        job.linhas_invalidas = invalidas
        log.info(f"universo_peers: {n} tickers ({len(tickers_carteira)} carteira, {len(setores_carteira)} setores)")
        return {"linhas_gravadas": n, "linhas_invalidas": invalidas, "setores": setores_carteira}


def carregar_universo_peers() -> list[str]:
    """Retorna todos os tickers do universo (carteira + peers)."""
    with get_session() as db:
        return [r.ticker for r in db.query(UniversoPeer).all()]


def peers_do_mesmo_setor(ticker: str) -> list[str]:
    """Tickers cujo setor_brapi mapeia para o mesmo índice B3 do ticker dado.

    Não restringe a universo_peers (que só direciona coleta) — usa toda a
    taxonomia_setorial; o caller intersecta com quem de fato tem fundamentos.
    """
    mapa = taxonomia.carregar_taxonomia_completa()
    idx_alvo = taxonomia.mapear_setor_para_indice(mapa.get(ticker.upper()))
    if not idx_alvo:
        return []
    return [
        t for t, setor in mapa.items()
        if t != ticker.upper() and taxonomia.mapear_setor_para_indice(setor) == idx_alvo
    ]
