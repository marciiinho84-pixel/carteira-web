"""
cache.py — Estado compartilhado do engine na memória + persistência em disco.

Fluxo:
  - POST /calcular → recalcular() → salva resultado em RAM + arquivo pickle
  - Restart do servidor → lifespan carrega o pickle (sem refazer cálculo)
  - Dados mudam (novo evento, preço) → recalcular() automaticamente após cada mutação

O pickle garante que cotações buscadas via API (yfinance/BCB) sobrevivam ao restart.
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


def _precos_publicos_vazios_mas_esperados(resultado: dict) -> bool:
    """True se precos_publicos vazio mas há posições públicas ativas (qtd > 0).

    Distingue falha de coleta (carteira tem RV mas yfinance retornou nada)
    de carteira legítima sem RV (precos_publicos vazio é correto).
    """
    if resultado.get("precos_publicos"):
        return False  # tem preços — caminho normal
    from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO
    posicoes = resultado.get("posicoes", {})
    ativos = resultado.get("ativos", {})
    for tkr, p in posicoes.items():
        familia = ativos.get(tkr, {}).get("familia", "")
        if familia in COTIZADO_PUBLICO and p.qtd > 1e-9:
            return True  # posição pública ativa sem preço = coleta falhou
    return False


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


def recalcular(db_path: Path = None, no_api: bool = False) -> dict:
    """Executa o engine completo, atualiza RAM e persiste em disco."""
    global _estado, _calculado_em, _erro
    try:
        from carteira_clean_web.backend.engine.run import run
        precos_externos = None
        if no_api and _estado:
            precos_externos = {
                "precos_publicos": _estado.get("precos_publicos", {}),
                "benchmarks": _estado.get("benchmarks", {}),
            }
        resultado = run(db_path=db_path, no_api=no_api, precos_externos=precos_externos)

        # Merge por ticker: quando o fetch atual vier vazio ou parcial, preserva o último
        # preço bom de cada ticker do estado anterior — nunca zera com falha transitória.
        if _estado:
            prev_pp = _estado.get("precos_publicos", {})
            novo_pp = resultado.get("precos_publicos", {})
            for tkr, serie in prev_pp.items():
                if serie and not novo_pp.get(tkr):
                    novo_pp[tkr] = serie
                    log.debug(f"precos_merge: {tkr} preservado do estado anterior")
            resultado["precos_publicos"] = novo_pp

        # Guard anti-envenenamento: coleta yfinance vazia com posições públicas ativas
        # indica falha de fetch, não carteira sem RV — não deve envenenar o cache.
        if _precos_publicos_vazios_mas_esperados(resultado):
            if _estado:
                log.warning("Coleta yfinance vazia com posições públicas — mantendo estado anterior")
                return _estado  # não sobrescreve RAM nem disco
            else:
                log.warning("Coleta yfinance vazia no primeiro boot — serve em RAM, não persiste pkl")
                _estado = resultado
                _calculado_em = datetime.now()
                _erro = None
                return resultado  # não chama _salvar_disco()

        _estado = resultado
        _calculado_em = datetime.now()
        _erro = None
        _salvar_disco()
        return resultado
    except Exception as e:
        _erro = str(e)
        raise
