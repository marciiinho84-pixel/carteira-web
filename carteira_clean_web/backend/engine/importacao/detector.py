"""
engine/importacao/detector.py — Detecção de tipo e formato de documento.
"""

import re
from pathlib import Path

TIPOS_DOCUMENTO = [
    "auto",
    "b3_custodia",
    "b3_movimentacoes",
    "caixa_rv",
    "funcef",
    "caixa_lci",
    "caixa_ouro",
    "caixa_fic_func",
    "tesouro_direto",
]

TIPO_LABELS = {
    "auto": "🔍 Detectar automaticamente",
    "b3_custodia": "B3 — Custódia",
    "b3_movimentacoes": "B3 — Movimentações",
    "caixa_rv": "Caixa — Renda Variável",
    "funcef": "FUNCEF",
    "caixa_lci": "Caixa — LCI",
    "caixa_ouro": "Caixa — Ouro",
    "caixa_fic_func": "Caixa — FIC FUNC",
    "tesouro_direto": "Tesouro Direto",
}

CONFIANCA_ICON = {"alta": "🟢", "media": "🟡", "baixa": "🔴"}

_KEYWORDS: dict[str, list[str]] = {
    "b3_custodia": ["B3 S.A.", "Posição em Custódia", "posicao em custodia", "carteira"],
    "b3_movimentacoes": ["B3 S.A.", "Movimentações", "movimentacao", "Negociação"],
    "funcef": ["FUNCEF", "Fundação dos Economiários"],
    "caixa_rv": ["CAIXA ECONÔMICA", "Renda Variável", "Nota de Negociação"],
    "caixa_lci": ["LCI", "Letra de Crédito Imobiliário", "CAIXA"],
    "caixa_ouro": ["OURO", "Caixa Ouro", "BM&F", "Au"],
    "caixa_fic_func": ["FIC FUNC", "Fundo de Investimento", "CAIXA FIC"],
    "tesouro_direto": ["Tesouro Direto", "NTN-B", "LTN", "Renda+", "RENDA+", "IPCA+"],
}


def detectar_tipo_documento(texto_amostra: str) -> str | None:
    """Tenta inferir o tipo do documento por palavras-chave. Retorna None se incerto."""
    texto_lower = texto_amostra.lower()
    scores: dict[str, int] = {}
    for tipo, kws in _KEYWORDS.items():
        score = sum(1 for kw in kws if kw.lower() in texto_lower)
        if score > 0:
            scores[tipo] = score
    if not scores:
        return None
    melhor = max(scores, key=lambda t: scores[t])
    return melhor if scores[melhor] >= 1 else None


def detectar_formato(nome_arquivo: str) -> str:
    """Retorna 'pdf', 'jpeg', 'png', 'xlsx', 'csv' ou 'desconhecido'."""
    ext = Path(nome_arquivo).suffix.lower().lstrip(".")
    mapa = {"pdf": "pdf", "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "xlsx": "xlsx", "csv": "csv"}
    return mapa.get(ext, "desconhecido")


def mime_type_de_formato(formato: str) -> str:
    mapa = {
        "pdf": "application/pdf",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
    }
    return mapa.get(formato, "application/octet-stream")
