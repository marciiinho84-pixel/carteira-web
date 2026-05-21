"""
engine/precos.py — Download de preços públicos (yfinance), benchmarks (BCB SGS)
e PUs do Tesouro Direto (Tesouro Transparente).
"""

import csv
import io
import logging
import re
from datetime import date, datetime, timedelta

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
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
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
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
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


_URL_TESOURO_CSV = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)


def baixar_precos_tesouro(ativos: dict, no_api: bool = False) -> dict:
    """
    Baixa PU de venda diário dos títulos Tesouro Direto via Tesouro Transparente.

    Identifica o vencimento do título por:
      1. Campo data_vencimento do ativo (se preenchido)
      2. Regex "(venc DD/MM/YYYY)" no campo observacao

    Retorna {ticker: {date: pu_venda}} — mesmo formato de precos_manuais.
    """
    if no_api or not HAS_NETWORK:
        return {}

    td_ativos = {t: info for t, info in ativos.items() if info.get("familia") == "Tesouro Direto"}
    if not td_ativos:
        return {}

    log.info(f"Baixando PUs do Tesouro Direto ({len(td_ativos)} ativo(s))…")

    try:
        r = requests.get(_URL_TESOURO_CSV, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        reader = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";")
        todas_linhas = list(reader)
    except Exception as e:
        log.warning(f"Tesouro Transparente: erro ao baixar CSV — {e}")
        return {}

    out = {}
    for tkr, info in td_ativos.items():
        # Determinar vencimento do título
        venc_date = info.get("data_vencimento")
        if venc_date:
            venc_str = venc_date.strftime("%d/%m/%Y") if hasattr(venc_date, "strftime") else str(venc_date)
        else:
            obs = info.get("observacao") or ""
            m = re.search(r"\(venc\s+(\d{2}/\d{2}/\d{4})\)", obs)
            if not m:
                log.debug(f"  ✗ {tkr}: vencimento não encontrado (preencha data_vencimento ou observacao)")
                continue
            venc_str = m.group(1)

        linhas = [row for row in todas_linhas if row.get("Data Vencimento") == venc_str]
        if not linhas:
            log.debug(f"  ✗ {tkr}: vencimento {venc_str} não encontrado no CSV")
            continue

        precos = {}
        for row in linhas:
            try:
                dt = datetime.strptime(row["Data Base"], "%d/%m/%Y").date()
                pu_str = row.get("PU Venda Manha", "").replace(".", "").replace(",", ".")
                if pu_str and float(pu_str) > 0:
                    precos[dt] = float(pu_str)
            except Exception:
                continue

        if precos:
            out[tkr] = precos
            pu_recente = precos[max(precos.keys())]
            log.info(f"  ✓ {tkr}: {len(precos)} dias (venc {venc_str}, PU {max(precos.keys())}: {pu_recente:.2f})")
        else:
            log.debug(f"  ✗ {tkr}: sem PUs válidos para venc {venc_str}")

    return out
