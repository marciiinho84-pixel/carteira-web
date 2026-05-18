"""Constantes compartilhadas por todos os módulos do engine."""

from datetime import date

DATA_INICIO = date(2026, 1, 2)
DATA_CAIXA_TRANSICAO = date(2026, 5, 17)

COTIZADO_PUBLICO = {"Ação BR", "BDR", "BDR de ETF", "ETF BR"}
COTIZADO_PRIVADO = {"Fundo CP", "Fundo de Pensão", "Fundo Indexado", "Tesouro Direto"}
AGREGADO_PRIVADO = {"Letra de Crédito"}

FLUXOS_EXTERNOS = {"APORTE_EXTERNO", "RESGATE_EXTERNO", "CONTRIBUICAO"}
COMPRAS = {"COMPRA", "SALDO_INICIAL", "BONIFICACAO"}
VENDAS = {"VENDA", "VENCIMENTO"}
PROVENTOS = {"DIVIDENDO", "JCP", "RENDIMENTO", "AMORTIZACAO"}
