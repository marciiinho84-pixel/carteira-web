"""
engine/brapi_client.py — Cliente HTTP compartilhado para a API brapi.dev.

Usado pelos coletores de taxonomia setorial, peers/fundamentos e proventos
(fatia "Ingestão de dados"). Injeta o token via BRAPI_TOKEN (env) e aplica
o retry padrão (ingestao_utils.retry_padrao) — retry só em falha de
rede/timeout ou HTTP 429/5xx, nunca em 4xx.
"""
from __future__ import annotations

import os

import requests

from .ingestao_utils import get_logger, retry_padrao

log = get_logger("brapi_client")

BASE_URL = "https://brapi.dev/api"
_TIMEOUT = 30


def _token() -> str:
    tok = os.environ.get("BRAPI_TOKEN", "")
    if not tok:
        log.warning("BRAPI_TOKEN não configurado — chamadas à brapi vão falhar (plano gratuito exige token)")
    return tok


@retry_padrao
def get(path: str, params: dict | None = None) -> dict:
    """GET autenticado em brapi.dev/api/{path}.

    Lança HTTPError se a resposta não for 2xx (retry_padrao já decide
    internamente se vale a pena tentar de novo: só em 429/5xx).
    """
    full_params = dict(params or {})
    full_params["token"] = _token()
    resp = requests.get(f"{BASE_URL}/{path.lstrip('/')}", params=full_params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()
