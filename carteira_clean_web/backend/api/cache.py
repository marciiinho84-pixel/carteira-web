"""
cache.py — Estado compartilhado do engine na memória + persistência em disco.

Fluxo:
  - POST /calcular → recalcular() → salva resultado em RAM + arquivo pickle
  - Restart do servidor → lifespan carrega o pickle (sem refazer cálculo)
  - Dados mudam (novo evento, preço) → recalcular() automaticamente após cada mutação

O pickle persiste o estado calculado (posições, performance, alertas)
para boot rápido após restart. Cotações e benchmarks sobrevivem ao restart via
tabelas cotacoes e benchmarks (Camada 3 — fonte única de verdade).
"""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("api.cache")

import os
_DEFAULT_CACHE_FILE = Path(__file__).resolve().parents[2] / "cache_engine.pkl"
_CACHE_DIR = os.environ.get("CACHE_DIR")
_CACHE_FILE = (Path(_CACHE_DIR) / "cache_engine.pkl") if _CACHE_DIR else _DEFAULT_CACHE_FILE

_estado: dict = {}
_calculado_em: Optional[datetime] = None
_erro: Optional[str] = None


def get_estado() -> dict:
    return _estado


def get_calculado_em() -> Optional[datetime]:
    return _calculado_em


def get_erro() -> Optional[str]:
    return _erro


def esta_calculado() -> bool:
    return bool(_estado)


def _salvar_disco() -> None:
    """Persiste o estado atual em pickle para sobreviver ao restart."""
    try:
        payload = {"estado": _estado, "calculado_em": _calculado_em}
        _CACHE_FILE.write_bytes(pickle.dumps(payload))
        log.debug(f"Cache salvo em {_CACHE_FILE}")
    except Exception as e:
        log.warning(f"Não foi possível salvar cache em disco: {e}")


def carregar_disco() -> bool:
    """
    Carrega o último resultado do pickle. Retorna True se bem-sucedido.
    Chamado na startup; evita recalcular quando o servidor reinicia.
    """
    global _estado, _calculado_em
    if not _CACHE_FILE.exists():
        return False
    try:
        payload = pickle.loads(_CACHE_FILE.read_bytes())
        _estado = payload["estado"]
        _calculado_em = payload.get("calculado_em")
        log.info(
            f"Cache carregado do disco (calculado em {_calculado_em})"
            if _calculado_em
            else "Cache carregado do disco"
        )
        return bool(_estado)
    except Exception as e:
        log.warning(f"Cache em disco inválido, ignorando: {e}")
        return False


def recalcular(no_api: bool = False) -> dict:
    """Executa o engine completo, atualiza RAM e persiste em disco."""
    global _estado, _calculado_em, _erro
    try:
        from carteira_clean_web.backend.engine.run import run
        resultado = run(no_api=no_api)
        # saldos_lci exige API BCB — preservar do estado anterior quando no_api=True
        if no_api and not resultado.get("saldos_lci") and _estado.get("saldos_lci"):
            resultado["saldos_lci"] = _estado["saldos_lci"]
        _estado = resultado
        _calculado_em = datetime.now()
        _erro = None
        _salvar_disco()
        return resultado
    except Exception as e:
        _erro = str(e)
        raise
