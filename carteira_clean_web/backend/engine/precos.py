"""
engine/precos.py — Download de preços públicos (yfinance) e benchmarks (BCB SGS).

Lógica copiada de baixar_precos_publicos() e baixar_benchmarks()
em atualizar_carteira.py. Sem alteração de comportamento.
"""

import logging
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger("engine.precos")

try:
    import yfinance as yf
    import requests
    HAS_NETWORK = True
except ImportError:
    HAS_NETWORK = False


def baixar_precos_publicos(
    tickers: list,
    data_ini: date,
    data_fim: date,
    no_api: bool = False,
) -> dict:
    if no_api or not HAS_NETWORK:
        log.warning("Modo no_api: pulando download de preços públicos")
        return {}
    out = {}
    log.info(f"Baixando preços via yfinance ({len(tickers)} ativos)…")
    for tkr in tickers:
        yf_tkr = tkr + ".SA"
        try:
            df = yf.download(
                yf_tkr,
                start=str(data_ini),
                end=str(data_fim + timedelta(days=1)),
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if df.empty:
                log.debug(f"  ✗ {tkr}: vazio")
                continue
            close = df["Close"] if "Close" in df else df.iloc[:, 0]
            if hasattr(close, "squeeze"):
                close = close.squeeze()
            out[tkr] = {
                pd.Timestamp(idx).date(): float(v)
                for idx, v in close.items()
                if pd.notna(v)
            }
            log.debug(f"  ✓ {tkr}: {len(out[tkr])} dias")
        except Exception as e:
            log.warning(f"  ✗ {tkr}: {e}")
    log.info(f"  → {len(out)}/{len(tickers)} ativos com preços")
    return out


def baixar_benchmarks(
    data_ini: date,
    data_fim: date,
    no_api: bool = False,
) -> dict:
    if no_api or not HAS_NETWORK:
        return {}
    out = {}
    log.info("Baixando benchmarks…")
    for nome, tkr in [("IBOV", "^BVSP"), ("SP500", "^GSPC"), ("USDBRL", "BRL=X")]:
        try:
            df = yf.download(
                tkr,
                start=str(data_ini),
                end=str(data_fim + timedelta(days=1)),
                progress=False,
                auto_adjust=True,
                threads=False,
            )
            if df.empty:
                continue
            close = df["Close"] if "Close" in df else df.iloc[:, 0]
            if hasattr(close, "squeeze"):
                close = close.squeeze()
            out[nome] = {
                pd.Timestamp(idx).date(): float(v)
                for idx, v in close.items()
                if pd.notna(v)
            }
            log.debug(f"  ✓ {nome}: {len(out[nome])} dias")
        except Exception as e:
            log.warning(f"  ✗ {nome}: {e}")
    for nome, codigo in [("CDI", 12), ("IPCA", 433)]:
        try:
            url = (
                f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
                f"?formato=json&dataInicial={data_ini.strftime('%d/%m/%Y')}"
                f"&dataFinal={data_fim.strftime('%d/%m/%Y')}"
            )
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            df = pd.DataFrame(r.json())
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.date
            df["valor"] = df["valor"].astype(float) / 100
            out[nome] = dict(zip(df["data"], df["valor"]))
            log.debug(f"  ✓ {nome}: {len(out[nome])} pontos")
        except Exception as e:
            log.warning(f"  ✗ {nome}: {e}")
    return out
