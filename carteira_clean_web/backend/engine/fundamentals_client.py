"""
engine/fundamentals_client.py — Dados fundamentalistas via yfinance (Ticker.info).

Cache por ticker em disco (48h — dados trimestrais).
Usa yfinance, que já é dependência do projeto e fornece os 6 campos
sem limitações de plano. ETFs/FIIs sem fundamentais retornam
"Sem dados fundamentais" como esperado.
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("engine.brapi")

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "brapi"
CACHE_TTL = timedelta(hours=48)

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False


# ── Cache por ticker ──────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker}.json"


def _cache_valido(ticker: str) -> dict | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        ts = data.get("_ts", "2000-01-01")
        if datetime.now() - datetime.fromisoformat(ts) > CACHE_TTL:
            return None
        return data
    except Exception:
        return None


def _salvar_cache(ticker: str, payload: dict) -> None:
    try:
        payload["_ts"] = datetime.now().isoformat()
        _cache_path(ticker).write_text(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        log.warning(f"Falha ao salvar cache {ticker}: {e}")


# ── Extração de campos do yfinance ────────────────────────────────

def _safe(v) -> float | None:
    """Float válido e não-zero, ou None."""
    if v is None:
        return None
    try:
        f = float(v)
        return f if f != 0.0 else None
    except (TypeError, ValueError):
        return None


def _extrair_yf(info: dict) -> dict:
    """Mapeia yfinance Ticker.info nos 6 indicadores fundamentalistas."""
    pl_raw    = _safe(info.get("trailingPE")) or _safe(info.get("forwardPE"))
    pvp_raw   = _safe(info.get("priceToBook"))
    ev_raw    = _safe(info.get("enterpriseToEbitda"))
    roe_raw   = _safe(info.get("returnOnEquity"))
    mg_raw    = _safe(info.get("profitMargins"))
    debt      = _safe(info.get("totalDebt"))
    ebitda    = _safe(info.get("ebitda"))

    pl        = round(pl_raw, 1)          if pl_raw  is not None else None
    pvp       = round(pvp_raw, 2)         if pvp_raw is not None else None
    ev_ebitda = round(ev_raw, 1)          if ev_raw  is not None else None
    roe       = round(roe_raw * 100, 1)   if roe_raw is not None else None
    margem    = round(mg_raw  * 100, 1)   if mg_raw  is not None else None
    div_ebitda = round(debt / ebitda, 1)  if (debt and ebitda)   else None

    # Margens > 100% são holdings/artefatos; mostrar mas não esconder
    tem_dados = any(x is not None for x in [pl, pvp, ev_ebitda, roe, margem, div_ebitda])
    return {
        "pl":         pl,
        "pvp":        pvp,
        "ev_ebitda":  ev_ebitda,
        "roe":        roe,
        "margem_liq": margem,
        "div_ebitda": div_ebitda,
        "erro":       None if tem_dados else "Sem dados fundamentais",
    }


# ── Fetch por ticker (com cache) ──────────────────────────────────

def _buscar_ticker(ticker: str) -> tuple[str, dict]:
    """Busca fundamentais de 1 ticker. Retorna (ticker, dados)."""
    from carteira_clean_web.backend.engine.utils import yf_symbol

    cached = _cache_valido(ticker)
    if cached:
        return ticker, cached

    result: dict
    try:
        sym = yf_symbol(ticker)
        info = yf.Ticker(sym).info
        result = _extrair_yf(info)
    except Exception as e:
        result = {"erro": f"Indisponível: {str(e)[:60]}"}

    _salvar_cache(ticker, result)
    return ticker, result


# ── Função pública ────────────────────────────────────────────────

def fetch_fundamentos(tickers: list[str]) -> dict[str, dict]:
    """Busca fundamentalistas para uma lista de tickers.
    Usa cache por ticker (48h). Busca em paralelo (4 workers) os pendentes.
    Retorna {ticker: {pl, pvp, ev_ebitda, roe, margem_liq, div_ebitda, erro}}.
    """
    if not HAS_YF or not tickers:
        return {t: {"erro": "yfinance indisponível"} for t in tickers}

    out: dict[str, dict] = {}
    pendentes: list[str] = []

    for t in tickers:
        cached = _cache_valido(t)
        if cached:
            out[t] = cached
        else:
            pendentes.append(t)

    if pendentes:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_buscar_ticker, t): t for t in pendentes}
            for future in as_completed(futures):
                try:
                    ticker, dados = future.result()
                    out[ticker] = dados
                except Exception as e:
                    t = futures[future]
                    out[t] = {"erro": str(e)}

    log.info(f"Fundamentos: {len(out)} tickers ({len(pendentes)} baixados)")
    return out
