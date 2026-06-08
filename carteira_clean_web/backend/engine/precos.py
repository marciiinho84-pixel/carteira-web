"""
engine/precos.py — Download de preços públicos (yfinance em lote + retry),
benchmarks (BCB SGS) e PUs do Tesouro Direto (Tesouro Transparente).
"""

import csv
import io
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

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
    if not tickers:
        return {}

    log.info(f"Baixando preços via yfinance em lote ({len(tickers)} ativos)…")

    # Mapeia ticker.SA → ticker interno para reindexar sem trocar símbolos
    yf_map = {tkr + ".SA": tkr for tkr in tickers}
    yf_tickers = list(yf_map.keys())

    def _normalizar_close(df: pd.DataFrame, syms: list) -> pd.DataFrame:
        """Devolve DataFrame com colunas = syms e linhas = datas.

        yf.download com N tickers → MultiIndex (campo, ticker) → df["Close"] = DataFrame
        yf.download com 1 ticker  → colunas planas → df["Close"] = Series
        Normaliza os dois casos para o mesmo formato.
        """
        if df.empty:
            return pd.DataFrame(columns=syms)
        if isinstance(df.columns, pd.MultiIndex):
            close = df["Close"] if "Close" in df.columns.get_level_values(0) else pd.DataFrame(columns=syms)
        else:
            close = df[["Close"]].rename(columns={"Close": syms[0]}) if "Close" in df.columns else pd.DataFrame(columns=syms)
        return close

    def _extrair(close_df: pd.DataFrame, sym_map: dict, faltantes_out: list) -> dict:
        """Extrai séries por nome de coluna; NaN total → ticker vai para faltantes_out."""
        parcial = {}
        for yf_tkr, tkr in sym_map.items():
            if yf_tkr not in close_df.columns:
                log.debug(f"  ✗ {tkr}: ausente no DataFrame")
                faltantes_out.append(yf_tkr)
                continue
            serie = close_df[yf_tkr].dropna()
            if serie.empty:
                # NaN total = falha silenciosa — omite para que o merge em cache.py
                # preserve o último preço bom automaticamente
                log.debug(f"  ✗ {tkr}: todos NaN — entra no retry")
                faltantes_out.append(yf_tkr)
                continue
            parcial[tkr] = {pd.Timestamp(idx).date(): float(v) for idx, v in serie.items()}
            log.debug(f"  ✓ {tkr}: {len(parcial[tkr])} dias")
        return parcial

    # Tentativa 1: lote completo
    faltantes: list = []
    try:
        df = yf.download(
            yf_tickers,
            start=str(data_ini),
            end=str(data_fim + timedelta(days=1)),
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        log.warning(f"yfinance lote falhou — {e}")
        df = pd.DataFrame()

    close_df = _normalizar_close(df, yf_tickers)
    out = _extrair(close_df, yf_map, faltantes)

    # Tentativa 2: retry sequencial com backoff apenas para os faltantes.
    # Crítico no boot a frio: sem estado anterior, o merge não consegue preservar nada.
    if faltantes:
        log.info(f"  Retry sequencial para {len(faltantes)} ticker(s) faltante(s)…")
        for yf_tkr in faltantes:
            tkr = yf_map[yf_tkr]
            time.sleep(1)
            try:
                df_r = yf.download(
                    [yf_tkr],
                    start=str(data_ini),
                    end=str(data_fim + timedelta(days=1)),
                    progress=False,
                    auto_adjust=True,
                )
                close_r = _normalizar_close(df_r, [yf_tkr])
                sem_retry: list = []
                recuperado = _extrair(close_r, {yf_tkr: tkr}, sem_retry)
                if recuperado:
                    out.update(recuperado)
                    log.info(f"  ✓ {tkr}: recuperado no retry")
                else:
                    log.debug(f"  ✗ {tkr}: vazio no retry — merge preservará preço anterior")
            except Exception as e:
                log.warning(f"  ✗ {tkr}: retry falhou — {e}")

    log.info(f"  → {len(out)}/{len(tickers)} ativos com preços")
    _gravar_cotacoes(out)  # Passo 1: persiste cotações novas/alteradas (resiliente)
    return out


def _gravar_cotacoes(precos_dict: dict) -> None:
    """Persiste cotações na tabela append-only cotacoes (variante A).

    Insere nova linha apenas se (ticker, date) é inédito ou o preço mudou
    em >= 0.01 (1 centavo). Tolerância elimina ruído de arredondamento
    float32/64 do yfinance (max observado 1.22e-4 << 0.01).
    Nunca UPDATE/DELETE. Falhas são logadas e silenciadas.
    """
    if not precos_dict:
        return
    try:
        import sqlite3 as _sqlite3

        _db_env = os.environ.get("DB_PATH")
        db_path = _db_env if _db_env else str(
            Path(__file__).resolve().parents[2] / "carteira.db"
        )

        con = _sqlite3.connect(db_path)
        try:
            # Carrega o último preço registrado por (ticker, date) em uma query
            rows = con.execute(
                "SELECT ticker, date, preco FROM cotacoes c "
                "WHERE fetched_at = ("
                "  SELECT MAX(fetched_at) FROM cotacoes "
                "  WHERE ticker = c.ticker AND date = c.date"
                ")"
            ).fetchall()
        except _sqlite3.OperationalError:
            log.debug("cotacoes: tabela não existe ainda — gravação pulada")
            con.close()
            return

        ultimos: dict = {(r[0], r[1]): r[2] for r in rows}
        agora = datetime.now().isoformat(timespec="seconds")
        inserir: list = []

        for ticker, serie in precos_dict.items():
            for dt, preco in serie.items():
                dt_str = dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
                ultimo = ultimos.get((ticker, dt_str))
                if ultimo is None or abs(float(preco) - float(ultimo)) > 0.01:
                    inserir.append((ticker, dt_str, float(preco), agora, "yfinance"))

        if inserir:
            con.executemany(
                "INSERT INTO cotacoes (ticker, date, preco, fetched_at, source) "
                "VALUES (?, ?, ?, ?, ?)",
                inserir,
            )
            con.commit()
            log.info(f"cotacoes: {len(inserir)} linhas gravadas (yfinance)")
        else:
            log.debug("cotacoes: nenhuma cotação nova ou alterada — skip")

        con.close()
    except Exception as e:
        log.warning(f"cotacoes: gravação falhou (não crítico) — {e}")


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


_URL_CVM_BASE = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ano_mes}.zip"
)
_CVM_HEADERS = {"User-Agent": "curl/7.68.0"}


def baixar_precos_cvm(
    cnpj_map: dict,
    data_inicio: date,
    data_fim: date,
    no_api: bool = False,
) -> dict:
    """
    Baixa cotas de fundos CVM para os CNPJs em cnpj_map.

    Args:
        cnpj_map: {ticker: cnpj} — e.g. {"CAIXA OURO": "16.916.060/0001-99"}
        data_inicio, data_fim: intervalo de datas
        no_api: se True, retorna {} sem baixar

    Returns:
        {ticker: {date: float}} — mesmo formato de precos_manuais
    """
    if no_api or not HAS_NETWORK or not cnpj_map:
        return {}

    import io as _io
    import zipfile

    log.info(f"Baixando cotas CVM ({len(cnpj_map)} fundo(s))…")

    # Meses a baixar
    meses = []
    cur = date(data_inicio.year, data_inicio.month, 1)
    while cur <= data_fim:
        meses.append(cur.strftime("%Y%m"))
        if cur.month == 12:
            cur = date(cur.year + 1, 1, 1)
        else:
            cur = date(cur.year, cur.month + 1, 1)

    cnpj_invertido = {v: k for k, v in cnpj_map.items()}
    out = {ticker: {} for ticker in cnpj_map}

    for ano_mes in meses:
        url = _URL_CVM_BASE.format(ano_mes=ano_mes)
        content = None
        for tentativa in range(2):
            try:
                r = requests.get(url, headers=_CVM_HEADERS, timeout=30)
                if r.status_code == 404:
                    log.debug(f"  CVM {ano_mes}: ainda não disponível (404)")
                    break
                r.raise_for_status()
                content = r.content
                break
            except Exception as e:
                if tentativa == 1:
                    log.warning(f"  CVM {ano_mes}: erro após 2 tentativas — {e}")
        if content is None:
            continue

        try:
            with zipfile.ZipFile(_io.BytesIO(content)) as z:
                csv_name = z.namelist()[0]
                with z.open(csv_name) as f:
                    df = pd.read_csv(f, sep=";", dtype=str)
        except Exception as e:
            log.warning(f"  CVM {ano_mes}: erro ao extrair ZIP — {e}")
            continue

        col_cnpj = "CNPJ_FUNDO_CLASSE" if "CNPJ_FUNDO_CLASSE" in df.columns else "CNPJ_FUNDO"
        df_filtrado = df[df[col_cnpj].isin(cnpj_invertido)]
        if df_filtrado.empty:
            log.debug(f"  CVM {ano_mes}: nenhum CNPJ encontrado")
            continue

        for _, row in df_filtrado.iterrows():
            cnpj = row[col_cnpj]
            ticker = cnpj_invertido.get(cnpj)
            if not ticker:
                continue
            try:
                dt = datetime.strptime(row["DT_COMPTC"], "%Y-%m-%d").date()
                cota = float(row["VL_QUOTA"].replace(",", ".") if isinstance(row["VL_QUOTA"], str) else row["VL_QUOTA"])
                if data_inicio <= dt <= data_fim:
                    out[ticker][dt] = cota
            except Exception:
                continue

        n_dias = sum(len(v) for v in out.values())
        log.debug(f"  CVM {ano_mes}: {n_dias} cotas acumuladas")

    for ticker, serie in out.items():
        if serie:
            log.info(f"  ✓ {ticker}: {len(serie)} dias (última cota: {serie[max(serie.keys())]:.8f})")
        else:
            log.warning(f"  ✗ {ticker}: sem cotas encontradas")

    return out


def calcular_saldo_lci(
    ticker: str,
    eventos: list,
    data_fim: date = None,
    no_api: bool = False,
) -> dict:
    """
    Calcula saldo diário de LCI/LCA a partir de eventos COMPRA com obs='CDI:XX.X'.

    Baixa a série CDI do BCB desde a data do contrato mais antigo.
    Retorna {date: saldo_total} para todos os dias úteis até data_fim.
    """
    if no_api or not HAS_NETWORK:
        return {}

    contratos = []
    for ev in eventos:
        if ev.get("ativo") != ticker or ev.get("tipo") != "COMPRA":
            continue
        obs = str(ev.get("obs") or "")
        import re as _re
        m = _re.match(r"CDI:([\d.]+)", obs)
        if not m:
            continue
        taxa_pct = float(m.group(1)) / 100
        dt_inicio = ev["data"]
        if hasattr(dt_inicio, "date"):
            dt_inicio = dt_inicio.date()
        contratos.append({
            "data_inicio": dt_inicio,
            "principal": abs(ev.get("valor") or 0),
            "taxa_pct": taxa_pct,
        })

    if not contratos:
        return {}

    data_inicio_cdi = min(c["data_inicio"] for c in contratos)
    data_fim = data_fim or date.today()

    try:
        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
            f"?formato=json"
            f"&dataInicial={data_inicio_cdi.strftime('%d/%m/%Y')}"
            f"&dataFinal={data_fim.strftime('%d/%m/%Y')}"
        )
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        df_cdi = pd.DataFrame(r.json())
        df_cdi["data"] = pd.to_datetime(df_cdi["data"], format="%d/%m/%Y").dt.date
        df_cdi["valor"] = df_cdi["valor"].astype(float) / 100
        cdi_serie = dict(zip(df_cdi["data"], df_cdi["valor"]))
    except Exception as e:
        log.warning(f"  calcular_saldo_lci {ticker}: erro CDI BCB — {e}")
        return {}

    if not cdi_serie:
        return {}

    dias = sorted(cdi_serie.keys())
    running = {i: None for i in range(len(contratos))}
    resultado = {}

    for dt in dias:
        cdi_d = cdi_serie[dt]
        saldo_total = 0.0
        for i, c in enumerate(contratos):
            if dt < c["data_inicio"]:
                continue
            if dt == c["data_inicio"]:
                running[i] = c["principal"]
            else:
                if running[i] is None:
                    running[i] = c["principal"]
                running[i] *= (1 + cdi_d * c["taxa_pct"])
            saldo_total += running[i]
        if saldo_total > 0:
            resultado[dt] = round(saldo_total, 2)

    if resultado:
        ult_dt = max(resultado.keys())
        log.info(
            f"  ✓ {ticker}: {len(resultado)} dias CDI calculados"
            f" (saldo em {ult_dt}: R$ {resultado[ult_dt]:,.2f})"
        )
    return resultado


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
