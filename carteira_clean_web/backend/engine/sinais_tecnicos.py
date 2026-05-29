"""
engine/sinais_tecnicos.py — Sinais técnicos (RSI, MACD, médias móveis).

Módulo puro de cálculo, sem dependência do Streamlit. Baixa histórico de 1 ano
via yfinance (em lote, 1 requisição), calcula os indicadores e consolida em um
sinal único. Usa cache em disco de 4h para evitar chamadas repetidas.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from carteira_clean_web.backend.engine.utils import yf_symbol

log = logging.getLogger("engine.sinais")

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache" / "sinais"
CACHE_TTL_HORAS = 4
PERIODO = "1y"        # 1 ano cobre MM200 (~252 pregões)
MIN_PONTOS = 30       # mínimo para RSI/MACD confiáveis

# ── Cores (design system) ─────────────────────────────────────────
_VERDE   = "#26A69A"
_VERMELHO = "#EF5350"
_AMBAR   = "#F59E0B"
_CINZA   = "#6B7280"
_INDIGO  = "#6366F1"


# ── Cache em disco ────────────────────────────────────────────────

def _cache_path(ticker: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{ticker}.json"


def _cache_valido(ticker: str) -> dict | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        gerado = datetime.fromisoformat(data["gerado_em"])
    except Exception:
        return None
    if datetime.now() - gerado > timedelta(hours=CACHE_TTL_HORAS):
        return None
    return data


def _salvar_cache(ticker: str, payload: dict) -> None:
    try:
        _cache_path(ticker).write_text(json.dumps(payload))
    except Exception as e:
        log.warning(f"Falha ao salvar cache de {ticker}: {e}")


# ── Indicadores ───────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI de Wilder via suavização exponencial (alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss          # avg_loss == 0 → rs == inf → RSI == 100
    return 100 - (100 / (1 + rs))


def calc_macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


# ── Classificadores (cada um devolve sinal/label/cor/score) ───────
# score: +2 compra forte · +1 compra fraca · 0 neutro · -1 venda fraca · -2 venda

def _classificar_rsi(rsi: float) -> dict:
    if rsi is None or pd.isna(rsi):
        return {"sinal": "NEUTRO", "label": "RSI sem dados", "cor": _CINZA, "score": 0}
    r = round(rsi)
    if rsi <= 30:
        return {"sinal": "COMPRA", "label": f"RSI {r} — sobrevendido", "cor": _VERDE, "score": 2}
    if rsi <= 40:
        return {"sinal": "COMPRA_FRACA", "label": f"RSI {r} — próx. sobrevendido", "cor": _AMBAR, "score": 1}
    if rsi >= 70:
        return {"sinal": "VENDA", "label": f"RSI {r} — sobrecomprado", "cor": _VERMELHO, "score": -2}
    if rsi >= 60:
        return {"sinal": "VENDA_FRACA", "label": f"RSI {r} — próx. sobrecomprado", "cor": _AMBAR, "score": -1}
    return {"sinal": "NEUTRO", "label": f"RSI {r}", "cor": _CINZA, "score": 0}


def _classificar_macd(macd: pd.Series, signal: pd.Series, janela_dias: int = 5) -> dict:
    """Detecta cruzamento MACD×sinal nos últimos N dias (evento acionável).
    Sem cruzamento recente → neutro, apenas indicando a posição atual."""
    if len(macd) < janela_dias + 2:
        return {"sinal": "NEUTRO", "label": "MACD sem dados", "cor": _CINZA, "score": 0}
    for i in range(-1, -(janela_dias + 1), -1):
        hoje = macd.iloc[i] - signal.iloc[i]
        ontem = macd.iloc[i - 1] - signal.iloc[i - 1]
        if pd.isna(hoje) or pd.isna(ontem):
            continue
        dias = abs(i)
        suf = "" if dias == 1 else f" ({dias}d atrás)"
        if ontem < 0 and hoje > 0:
            return {"sinal": "COMPRA", "label": f"MACD cruzou ↑{suf}", "cor": _VERDE, "score": 2}
        if ontem > 0 and hoje < 0:
            return {"sinal": "VENDA", "label": f"MACD cruzou ↓{suf}", "cor": _VERMELHO, "score": -2}
    atual = macd.iloc[-1] - signal.iloc[-1]
    if pd.isna(atual):
        return {"sinal": "NEUTRO", "label": "MACD sem dados", "cor": _CINZA, "score": 0}
    pos = "acima" if atual > 0 else "abaixo"
    return {"sinal": "NEUTRO", "label": f"MACD {pos} da linha", "cor": _CINZA, "score": 0}


def _classificar_mm(close: pd.Series, janela_dias: int = 5) -> dict:
    """Médias móveis: detecta cruzamento (alta/baixa) no par mais longo que os
    dados suportam (50×200 → 20×50). Sem cruzamento → neutro com o alinhamento."""
    n = len(close)
    if n >= 200 + janela_dias:
        curto, longo = 50, 200
    elif n >= 50 + janela_dias:
        curto, longo = 20, 50
    else:
        return {"sinal": "NEUTRO", "label": "MM sem dados", "cor": _CINZA, "score": 0}

    mmc = close.rolling(curto).mean()
    mml = close.rolling(longo).mean()
    for i in range(-1, -(janela_dias + 1), -1):
        hoje = mmc.iloc[i] - mml.iloc[i]
        ontem = mmc.iloc[i - 1] - mml.iloc[i - 1]
        if pd.isna(hoje) or pd.isna(ontem):
            continue
        dias = abs(i)
        suf = "" if dias == 1 else f" ({dias}d atrás)"
        if ontem < 0 and hoje > 0:
            return {"sinal": "COMPRA", "label": f"Cruz. alta MM{curto}×{longo}{suf}", "cor": _VERDE, "score": 2}
        if ontem > 0 and hoje < 0:
            return {"sinal": "VENDA", "label": f"Cruz. baixa MM{curto}×{longo}{suf}", "cor": _VERMELHO, "score": -2}

    preco, c, l = close.iloc[-1], mmc.iloc[-1], mml.iloc[-1]
    if pd.notna(c) and pd.notna(l):
        if preco > c > l:
            return {"sinal": "NEUTRO", "label": f"Acima das MM{curto}/{longo}", "cor": _CINZA, "score": 0}
        if preco < c < l:
            return {"sinal": "NEUTRO", "label": f"Abaixo das MM{curto}/{longo}", "cor": _CINZA, "score": 0}
    return {"sinal": "NEUTRO", "label": f"MM{curto}/{longo} lateral", "cor": _CINZA, "score": 0}


def _sinal_combinado(indicadores: list[dict]) -> dict:
    """Consolida RSI + MACD + MM. Venda simétrica à compra; CONFLITO quando há
    sinal forte de compra e de venda ao mesmo tempo."""
    scores = [d["score"] for d in indicadores]
    net = sum(scores)
    forte_compra = any(s == 2 for s in scores)
    forte_venda = any(s == -2 for s in scores)
    if forte_compra and forte_venda:
        return {"label": "CONFLITO", "cor": _INDIGO, "peso": 1}
    if net >= 4:
        return {"label": "COMPRA FORTE", "cor": _VERDE, "peso": 6}
    if net >= 2:
        return {"label": "COMPRA", "cor": _VERDE, "peso": 4}
    if net == 1:
        return {"label": "COMPRA FRACA", "cor": _VERDE, "peso": 2}
    if net <= -4:
        return {"label": "VENDA FORTE", "cor": _VERMELHO, "peso": 6}
    if net <= -2:
        return {"label": "VENDA", "cor": _VERMELHO, "peso": 4}
    if net == -1:
        return {"label": "VENDA FRACA", "cor": _VERMELHO, "peso": 2}
    return {"label": "NEUTRO", "cor": _CINZA, "peso": 0}


# ── Download (yfinance, em lote) ──────────────────────────────────

def _baixar(symbols: list[str]) -> pd.DataFrame | None:
    if not HAS_YF or not symbols:
        return None
    return yf.download(
        symbols, period=PERIODO, interval="1d",
        auto_adjust=True, progress=False, threads=False,
    )


def _extrair_close(df: pd.DataFrame | None, sym: str) -> pd.Series | None:
    """Extrai a série Close de `sym` de um DataFrame que pode ter colunas
    simples (1 ticker) ou MultiIndex (lote)."""
    if df is None or df.empty:
        return None
    cols = df.columns
    if isinstance(cols, pd.MultiIndex):
        nivel0 = cols.get_level_values(0)
        if "Close" in nivel0:
            sub = df["Close"]
            s = sub[sym] if (isinstance(sub, pd.DataFrame) and sym in sub.columns) else sub
        elif sym in nivel0:
            sub = df[sym]
            s = sub["Close"] if "Close" in sub.columns else sub.iloc[:, 0]
        else:
            return None
    else:
        s = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.dropna()


# ── Orquestração ──────────────────────────────────────────────────

def _erro(ticker: str, msg: str) -> dict:
    return {"ticker": ticker, "erro": msg, "tem_sinal_ativo": False,
            "combinado": {"label": "—", "cor": _CINZA, "peso": 0},
            "gerado_em": datetime.now().isoformat()}


def _computar_sinal(ticker: str, close: pd.Series | None) -> dict:
    if close is None or len(close) < MIN_PONTOS:
        return _erro(ticker, "Dados insuficientes")

    rsi_series = calc_rsi(close)
    macd_line, signal_line, _ = calc_macd(close)

    rsi_val = float(rsi_series.iloc[-1])
    rsi_info = _classificar_rsi(rsi_val)
    macd_info = _classificar_macd(macd_line, signal_line)
    mm_info = _classificar_mm(close)
    combinado = _sinal_combinado([rsi_info, macd_info, mm_info])

    return {
        "ticker": ticker,
        "rsi": round(rsi_val, 1) if not pd.isna(rsi_val) else None,
        "rsi_sinal": rsi_info["sinal"], "rsi_label": rsi_info["label"], "rsi_cor": rsi_info["cor"],
        "macd_sinal": macd_info["sinal"], "macd_label": macd_info["label"], "macd_cor": macd_info["cor"],
        "mm_sinal": mm_info["sinal"], "mm_label": mm_info["label"], "mm_cor": mm_info["cor"],
        "combinado": combinado,
        "tem_sinal_ativo": combinado["peso"] > 0,
        "gerado_em": datetime.now().isoformat(),
        "erro": None,
    }


def calcular_sinal(ticker: str) -> dict:
    """Calcula o sinal de um ticker (com cache de 4h)."""
    ticker = ticker.strip().upper()
    cached = _cache_valido(ticker)
    if cached:
        return cached
    sym = yf_symbol(ticker)
    try:
        close = _extrair_close(_baixar([sym]), sym)
        res = _computar_sinal(ticker, close)
    except Exception as e:
        res = _erro(ticker, str(e))
    _salvar_cache(ticker, res)
    return res


def calcular_sinais_lote(tickers: list[str]) -> list[dict]:
    """Calcula sinais técnicos + fundamentalistas para vários tickers.
    Técnicos: cache por ticker (4h). Fundamentalistas: Brapi, cache por lote (48h).
    Ordena por peso do sinal técnico desc, depois alfabético."""
    tickers = list(dict.fromkeys(
        t.strip().upper() for t in tickers if t and t.strip()
    ))
    resultados: list[dict] = []
    pendentes: list[str] = []
    for t in tickers:
        cached = _cache_valido(t)
        (resultados if cached else pendentes).append(cached or t)

    if pendentes:
        sym_map = {t: yf_symbol(t) for t in pendentes}
        try:
            df = _baixar(list(sym_map.values()))
        except Exception as e:
            log.warning(f"Download em lote falhou: {e}")
            df = None
        for t in pendentes:
            try:
                close = _extrair_close(df, sym_map[t]) if df is not None else None
                res = _computar_sinal(t, close)
            except Exception as e:
                res = _erro(t, str(e))
            _salvar_cache(t, res)
            resultados.append(res)

    # Enriquecer com fundamentalistas via yfinance (cache 48h)
    try:
        from carteira_clean_web.backend.engine.fundamentals_client import fetch_fundamentos
        tickers_para_brapi = [s["ticker"] for s in resultados if not s.get("erro")]
        fundamentos = fetch_fundamentos(tickers_para_brapi)
        for sinal in resultados:
            t = sinal["ticker"]
            f = fundamentos.get(t, {})
            sinal["fund"] = {
                "pl":         f.get("pl"),
                "pvp":        f.get("pvp"),
                "ev_ebitda":  f.get("ev_ebitda"),
                "roe":        f.get("roe"),
                "margem_liq": f.get("margem_liq"),
                "div_ebitda": f.get("div_ebitda"),
                "erro":       f.get("erro"),
            }
    except Exception as e:
        log.warning(f"Fundamentalistas indisponíveis: {e}")
        for sinal in resultados:
            sinal.setdefault("fund", {"erro": "Indisponível"})

    resultados.sort(key=lambda x: (
        -(x.get("combinado", {}).get("peso", 0)),
        x.get("ticker", ""),
    ))
    return resultados
