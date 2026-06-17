"""
engine/fundamentals_client.py — Dados fundamentalistas via yfinance.

Dois modos:
- fetch_fundamentos(): 6 indicadores básicos, cache 48h (usado por obter_sinais).
- fetch_fundamentos_completos(): 10 indicadores + ROIC, cache 7 dias.
- salvar_fundamentos_db(): coleta + persiste na tabela `fundamentos`.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("engine.fundamentos")

_CACHE_BASE = Path(os.environ.get("CACHE_DIR", str(Path(__file__).resolve().parents[2] / "cache")))
CACHE_DIR = _CACHE_BASE / "brapi"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = timedelta(hours=48)

_CACHE_DIR_COMPLETO = _CACHE_BASE / "fundamentos_completos"
_CACHE_TTL_COMPLETO = timedelta(days=7)

_INDICADORES_COMPLETOS = (
    "PL", "PVP", "ROE", "ROIC", "DY",
    "MARGEM_EBITDA", "DIV_LIQ_EBITDA", "MARGEM_LIQUIDA", "LPA", "VPA",
)

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


# ── Funções para 10 indicadores completos ─────────────────────────

def _cache_completo_path(ticker: str) -> Path:
    _CACHE_DIR_COMPLETO.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR_COMPLETO / f"{ticker}.json"


def _cache_completo_valido(ticker: str) -> dict | None:
    path = _cache_completo_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        ts = data.get("_ts", "2000-01-01")
        if datetime.now() - datetime.fromisoformat(ts) > _CACHE_TTL_COMPLETO:
            return None
        return data
    except Exception:
        return None


def _salvar_cache_completo(ticker: str, payload: dict) -> None:
    try:
        payload["_ts"] = datetime.now().isoformat()
        _cache_completo_path(ticker).write_text(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        log.warning(f"Falha ao salvar cache completo {ticker}: {e}")


def _calcular_roic(yf_ticker, info: dict) -> float | None:
    """ROIC = NOPAT / Capital Investido.
    NOPAT = EBIT × (1 − alíquota_efetiva)
    Capital Investido = Ativo Total − Passivo Circulante
    """
    try:
        fin = yf_ticker.financials
        bs = yf_ticker.balance_sheet
        if fin is None or bs is None or fin.empty or bs.empty:
            return None

        col_fin = fin.columns[0]
        col_bs = bs.columns[0]

        ebit = None
        for chave in ("EBIT", "Operating Income", "Ebit"):
            if chave in fin.index:
                ebit = _safe(fin.loc[chave, col_fin])
                if ebit is not None:
                    break
        if ebit is None:
            return None

        tax_rate = _safe(info.get("effectiveTaxRate"))
        if tax_rate is None:
            prov, pretax = None, None
            for chave in ("Tax Provision", "Income Tax Expense"):
                if chave in fin.index:
                    prov = _safe(fin.loc[chave, col_fin])
                    break
            for chave in ("Pretax Income", "Income Before Tax"):
                if chave in fin.index:
                    pretax = _safe(fin.loc[chave, col_fin])
                    break
            if prov and pretax and pretax != 0:
                tax_rate = abs(prov) / abs(pretax)
        tax_rate = min(tax_rate or 0.25, 0.60)

        nopat = ebit * (1.0 - tax_rate)

        total_assets, curr_liab = None, None
        if "Total Assets" in bs.index:
            total_assets = _safe(bs.loc["Total Assets", col_bs])
        for chave in ("Current Liabilities", "Total Current Liabilities"):
            if chave in bs.index:
                curr_liab = _safe(bs.loc[chave, col_bs])
                break

        if total_assets is None or curr_liab is None:
            return None
        capital_investido = total_assets - curr_liab
        if capital_investido <= 0:
            return None

        return round(nopat / capital_investido * 100, 1)
    except Exception:
        return None


def _extrair_yf_completo(yf_ticker) -> dict:
    """Extrai os 10 indicadores fundamentalistas de um Ticker yfinance."""
    info = yf_ticker.info

    pl_raw = _safe(info.get("trailingPE")) or _safe(info.get("forwardPE"))
    pvp_raw = _safe(info.get("priceToBook"))
    roe_raw = _safe(info.get("returnOnEquity"))
    # trailingAnnualDividendYield é mais confiável para ações BR do que dividendYield
    dy_raw = _safe(info.get("trailingAnnualDividendYield")) or _safe(info.get("dividendYield"))
    mg_liq_raw = _safe(info.get("profitMargins"))
    mg_ebitda_raw = _safe(info.get("ebitdaMargins"))
    lpa_raw = _safe(info.get("trailingEps"))
    vpa_raw = _safe(info.get("bookValue"))
    debt = _safe(info.get("totalDebt"))
    ebitda_val = _safe(info.get("ebitda"))

    div_liq_ebitda = round(debt / ebitda_val, 1) if (debt and ebitda_val) else None
    roic = _calcular_roic(yf_ticker, info)

    result = {
        "PL":            round(pl_raw, 1)          if pl_raw is not None      else None,
        "PVP":           round(pvp_raw, 2)          if pvp_raw is not None     else None,
        "ROE":           round(roe_raw * 100, 1)    if roe_raw is not None     else None,
        "ROIC":          roic,
        "DY":            round(dy_raw * 100, 2)     if (dy_raw is not None and dy_raw <= 1.0) else None,
        "MARGEM_EBITDA": round(mg_ebitda_raw * 100, 1) if mg_ebitda_raw is not None else None,
        "DIV_LIQ_EBITDA": div_liq_ebitda,
        "MARGEM_LIQUIDA": round(mg_liq_raw * 100, 1) if mg_liq_raw is not None else None,
        "LPA":           round(lpa_raw, 2)          if lpa_raw is not None     else None,
        "VPA":           round(vpa_raw, 2)          if vpa_raw is not None     else None,
    }
    tem_dados = any(v is not None for v in result.values())
    result["erro"] = None if tem_dados else "Sem dados fundamentais"
    return result


def _buscar_ticker_completo(ticker: str) -> tuple[str, dict]:
    """Busca 10 indicadores de 1 ticker com cache de 7 dias."""
    from carteira_clean_web.backend.engine.utils import yf_symbol

    cached = _cache_completo_valido(ticker)
    if cached:
        return ticker, cached

    result: dict
    try:
        sym = yf_symbol(ticker)
        yf_t = yf.Ticker(sym)
        result = _extrair_yf_completo(yf_t)
    except Exception as e:
        result = {ind: None for ind in _INDICADORES_COMPLETOS}
        result["erro"] = f"Indisponível: {str(e)[:60]}"

    _salvar_cache_completo(ticker, result)
    return ticker, result


def fetch_fundamentos_completos(tickers: list[str]) -> dict[str, dict]:
    """Busca os 10 indicadores para lista de tickers.
    Cache 7 dias. Busca em paralelo (4 workers).
    Retorna {ticker: {PL, PVP, ROE, ROIC, DY, MARGEM_EBITDA, DIV_LIQ_EBITDA,
                      MARGEM_LIQUIDA, LPA, VPA, erro}}.
    """
    if not HAS_YF or not tickers:
        return {t: {"erro": "yfinance indisponível"} for t in tickers}

    out: dict[str, dict] = {}
    pendentes: list[str] = []

    for t in tickers:
        cached = _cache_completo_valido(t)
        if cached:
            out[t] = cached
        else:
            pendentes.append(t)

    if pendentes:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_buscar_ticker_completo, t): t for t in pendentes}
            for future in as_completed(futures):
                try:
                    ticker, dados = future.result()
                    out[ticker] = dados
                except Exception as e:
                    t = futures[future]
                    out[t] = {ind: None for ind in _INDICADORES_COMPLETOS}
                    out[t]["erro"] = str(e)

    log.info(f"Fundamentos completos: {len(out)} tickers ({len(pendentes)} baixados)")
    return out


def salvar_fundamentos_db(tickers: list[str] | None = None) -> dict:
    """Coleta os 10 indicadores e persiste na tabela `fundamentos`.

    Se tickers=None, usa todos os ativos RV da carteira.
    ETFs/fundos sem dados: registra valor=NULL (não falha).
    Retorna sumário da operação.
    """
    from datetime import date

    from carteira_clean_web.backend.db.models import Fundamento
    from carteira_clean_web.backend.db.session import get_session

    if tickers is None:
        from carteira_clean_web.backend.api import cache as engine_cache
        from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

        if not engine_cache.esta_calculado():
            engine_cache.carregar_disco()
        if not engine_cache.esta_calculado():
            return {"erro": "Cache vazio — recalcule a carteira primeiro."}
        estado = engine_cache.get_estado()
        tickers = [
            t
            for t, p in estado["posicoes"].items()
            if estado["ativos"].get(t, {}).get("familia", "") in COTIZADO_PUBLICO
            and p.qtd > 1e-9
        ]

    if not tickers:
        return {"erro": "Nenhum ticker encontrado."}

    fundamentos = fetch_fundamentos_completos(tickers)
    hoje = date.today()
    agora = datetime.now()

    session = get_session()
    try:
        linhas = []
        com_erro: dict[str, str] = {}
        for ticker, dados in fundamentos.items():
            if dados.get("erro"):
                com_erro[ticker] = dados["erro"]
            for indicador in _INDICADORES_COMPLETOS:
                linhas.append(
                    Fundamento(
                        ticker=ticker,
                        data_referencia=hoje,
                        indicador=indicador,
                        valor=dados.get(indicador),
                        fonte="yfinance",
                        fetched_at=agora,
                    )
                )
        session.bulk_save_objects(linhas)
        session.commit()
        log.info(
            f"salvar_fundamentos_db: {len(tickers)} tickers, "
            f"{len(linhas)} linhas, {len(com_erro)} com erro."
        )
        for t, e in com_erro.items():
            log.warning(f"  {t}: {e}")
        return {
            "total": len(tickers),
            "linhas_inseridas": len(linhas),
            "com_erro": com_erro,
        }
    except Exception as e:
        session.rollback()
        log.error(f"salvar_fundamentos_db: rollback — {e}")
        return {"erro": str(e)}
    finally:
        session.close()
