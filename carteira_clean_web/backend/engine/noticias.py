"""
engine/noticias.py — Impacto macro (Fatia 13).

Notícias por ativo: ver engine/noticias_rss.py (Google News RSS, substituiu
yfinance .news — descontinuado como fonte, instável/vazio).
Impacto macro: lookup na tabela matriz_sensibilidade.
"""
from __future__ import annotations

# ── Seed data para matriz_sensibilidade ──────────────────────────────────────
SEED_MATRIZ: list[dict] = [
    # SELIC ↓
    {"indicador": "SELIC_META", "variacao": "QUEDA", "setor": "Construção Civil",   "direcao": "POSITIVO", "peso": 3, "logica": "Financiamento imobiliário mais barato estimula demanda"},
    {"indicador": "SELIC_META", "variacao": "QUEDA", "setor": "Bancos Tradicionais","direcao": "NEGATIVO", "peso": 2, "logica": "Compressão de spread — margem financeira reduz"},
    {"indicador": "SELIC_META", "variacao": "QUEDA", "setor": "Energia Elétrica",   "direcao": "POSITIVO", "peso": 2, "logica": "DY relativo melhora vs renda fixa; valuation cresce"},
    {"indicador": "SELIC_META", "variacao": "QUEDA", "setor": "Saneamento",         "direcao": "POSITIVO", "peso": 2, "logica": "Utilities com dividendos tornam-se relativamente mais atrativos"},
    {"indicador": "SELIC_META", "variacao": "QUEDA", "setor": "Varejo",             "direcao": "POSITIVO", "peso": 2, "logica": "Crédito ao consumidor mais barato estimula consumo"},
    {"indicador": "SELIC_META", "variacao": "ALTA",  "setor": "Construção Civil",   "direcao": "NEGATIVO", "peso": 3, "logica": "Financiamento imobiliário mais caro reduz demanda"},
    {"indicador": "SELIC_META", "variacao": "ALTA",  "setor": "Bancos Tradicionais","direcao": "POSITIVO", "peso": 2, "logica": "Spread aumenta; margem financeira cresce"},
    {"indicador": "SELIC_META", "variacao": "ALTA",  "setor": "Energia Elétrica",   "direcao": "NEGATIVO", "peso": 2, "logica": "DY relativo piora vs renda fixa; valuation comprime"},
    # USD ↑
    {"indicador": "USD_BRL",    "variacao": "ALTA",  "setor": "Petróleo & Gás",     "direcao": "POSITIVO", "peso": 3, "logica": "Receita em USD; queda do BRL eleva receita convertida"},
    {"indicador": "USD_BRL",    "variacao": "ALTA",  "setor": "Agronegócio",        "direcao": "POSITIVO", "peso": 3, "logica": "Exportadoras beneficiam-se da receita em USD"},
    {"indicador": "USD_BRL",    "variacao": "ALTA",  "setor": "Varejo",             "direcao": "NEGATIVO", "peso": 2, "logica": "Produtos importados encarecem; pressão nos custos"},
    {"indicador": "USD_BRL",    "variacao": "QUEDA", "setor": "Petróleo & Gás",     "direcao": "NEGATIVO", "peso": 2, "logica": "Apreciação do BRL reduz receita convertida"},
    # IPCA ↑
    {"indicador": "IPCA",       "variacao": "ALTA",  "setor": "Varejo",             "direcao": "NEGATIVO", "peso": 2, "logica": "Inflação corrói poder de compra e eleva custos"},
    {"indicador": "IPCA",       "variacao": "ALTA",  "setor": "Energia Elétrica",   "direcao": "POSITIVO", "peso": 1, "logica": "Tarifas indexadas à inflação protegem receita"},
    {"indicador": "IPCA",       "variacao": "ALTA",  "setor": "Saneamento",         "direcao": "POSITIVO", "peso": 1, "logica": "Contratos indexados protegem receita real"},
]
