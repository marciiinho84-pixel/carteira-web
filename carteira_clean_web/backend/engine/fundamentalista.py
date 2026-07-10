"""
engine/fundamentalista.py — Análise fundamentalista (Fatia 10).

Lê a tabela `fundamentos` e analisa múltiplos, compara com setor e histórico.
NÃO busca dados novos — usa o substrato da Fatia 2.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean, stdev


_INDICADORES_LABEL = {
    "PL":              "P/L",
    "PVP":             "P/VP",
    "ROE":             "ROE (%)",
    "ROIC":            "ROIC (%)",
    "DY":              "DY (%)",
    "MARGEM_EBITDA":   "Margem EBITDA (%)",
    "DIV_LIQ_EBITDA":  "Dív.Líq/EBITDA",
    "MARGEM_LIQUIDA":  "Margem Líquida (%)",
    "LPA":             "LPA (R$)",
    "VPA":             "VPA (R$)",
}

_GRUPOS = {
    "valuation":    ["PL", "PVP", "DIV_LIQ_EBITDA"],
    "rentabilidade": ["ROE", "ROIC", "MARGEM_EBITDA", "MARGEM_LIQUIDA"],
    "saude":        ["DIV_LIQ_EBITDA"],
    "proventos":    ["DY", "LPA", "VPA"],
}


def _ultimos_fundamentos(fundamentos_rows: list[dict]) -> dict[str, float | None]:
    """Retorna o valor mais recente de cada indicador (por fetched_at desc)."""
    mais_recente: dict[str, tuple] = {}
    for row in fundamentos_rows:
        ind = row["indicador"]
        fat = row.get("fetched_at") or ""
        if ind not in mais_recente or fat > mais_recente[ind][0]:
            mais_recente[ind] = (fat, row.get("valor"))
    return {ind: v for ind, (_, v) in mais_recente.items()}


def analise_fundamentalista(
    ticker: str,
    fundamentos_ticker: list[dict],
    fundamentos_setor: dict[str, list[dict]],
) -> dict:
    """
    Análise fundamentalista em 4 dimensões para um ticker.

    Args:
        ticker:              código do ativo
        fundamentos_ticker:  rows de `fundamentos` para este ticker
        fundamentos_setor:   {ticker_peer: rows} para colegas do mesmo setor
    """
    meus = _ultimos_fundamentos(fundamentos_ticker)

    # Médias do setor por indicador (excluindo o próprio ticker)
    setor_vals: dict[str, list[float]] = defaultdict(list)
    for peer, rows in fundamentos_setor.items():
        if peer == ticker:
            continue
        for ind, val in _ultimos_fundamentos(rows).items():
            if val is not None:
                setor_vals[ind].append(val)
    media_setor: dict[str, float | None] = {
        ind: mean(vs) if vs else None for ind, vs in setor_vals.items()
    }

    # Histórico do próprio ticker para detectar outliers
    hist_vals: dict[str, list[float]] = defaultdict(list)
    for row in fundamentos_ticker:
        ind = row["indicador"]
        val = row.get("valor")
        if val is not None:
            hist_vals[ind].append(val)

    def posicao_relativa(ind: str, atual: float | None, media: float | None) -> str:
        if atual is None or media is None:
            return "sem dados"
        if abs(media) < 1e-9:
            return "na média"
        diff_pct = (atual - media) / abs(media) * 100
        if diff_pct > 20:
            return "acima da média"
        elif diff_pct < -20:
            return "abaixo da média"
        return "na média"

    def flag_outlier(ind: str, atual: float | None) -> bool:
        if atual is None:
            return False
        hist = hist_vals.get(ind, [])
        if len(hist) < 4:
            return False
        m, s = mean(hist), stdev(hist)
        return abs(atual - m) > 2 * s if s > 0 else False

    dimensoes: dict[str, list[dict]] = {}
    for grupo, inds in _GRUPOS.items():
        linhas = []
        for ind in inds:
            val = meus.get(ind)
            med = media_setor.get(ind)
            linhas.append({
                "indicador":       _INDICADORES_LABEL.get(ind, ind),
                "valor_atual":     round(val, 4) if val is not None else None,
                "media_setor":     round(med, 4) if med is not None else None,
                "posicao":         posicao_relativa(ind, val, med),
                "outlier_historico": flag_outlier(ind, val),
            })
        dimensoes[grupo] = linhas

    n_peers = len([p for p in fundamentos_setor if p != ticker])
    return {
        "ticker": ticker,
        "dimensoes": dimensoes,
        "todos_indicadores": {
            _INDICADORES_LABEL.get(ind, ind): round(val, 4) if val is not None else None
            for ind, val in meus.items()
        },
        "n_peers_setor": n_peers,
        "nota": (
            "Fatos comparativos — não recomenda compra/venda. "
            f"Comparado com {n_peers} ativo(s) do mesmo setor. "
            "Fonte: tabela fundamentos (yfinance + brapi)."
        ),
    }


def screening_fundamentalista(
    criterios: dict[str, dict],
    fundamentos_todos: dict[str, list[dict]],
) -> list[dict]:
    """
    Filtra ativos que atendem a critérios fundamentalistas.

    Args:
        criterios: {indicador: {"min": float, "max": float}}
                   Exemplo: {"ROE": {"min": 15}, "DY": {"min": 4}}
        fundamentos_todos: {ticker: rows}
    """
    resultados = []
    for ticker, rows in fundamentos_todos.items():
        meus = _ultimos_fundamentos(rows)
        atende = True
        linha: dict = {"ticker": ticker}
        for ind, limites in criterios.items():
            val = meus.get(ind)
            linha[_INDICADORES_LABEL.get(ind, ind)] = round(val, 4) if val is not None else None
            if val is None:
                atende = False
                break
            if "min" in limites and val < limites["min"]:
                atende = False
                break
            if "max" in limites and val > limites["max"]:
                atende = False
                break
        if atende:
            resultados.append(linha)
    return resultados


def comparar_multiplos(
    tickers: list[str],
    fundamentos_todos: dict[str, list[dict]],
) -> dict:
    """
    Tabela side-by-side de múltiplos fundamentalistas para 2-5 tickers.
    """
    tabela: dict[str, dict[str, Any]] = {}
    for ind, label in _INDICADORES_LABEL.items():
        tabela[label] = {}
        for ticker in tickers:
            rows = fundamentos_todos.get(ticker, [])
            meus = _ultimos_fundamentos(rows)
            val = meus.get(ind)
            tabela[label][ticker] = round(val, 4) if val is not None else None

    # Remover linhas onde todos são None
    tabela = {k: v for k, v in tabela.items() if any(x is not None for x in v.values())}

    return {
        "tickers": tickers,
        "tabela": tabela,
        "nota": "Fonte: tabela fundamentos (yfinance + brapi). Coleta via POST /api/v1/macro/coletar se dados desatualizados.",
    }
