"""
maestro_chat.py — Streaming chat endpoint com Anthropic tool use.

POST /maestro/chat
  Body: {"messages": [...], "thread_id": "...", "nivel_automacao": {...}}
  Streama AG-UI events via SSE.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Annotated, Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from carteira_clean_web.backend.api.routers.auth import require_auth
from carteira_clean_web.backend.db.models import Conversa, Mensagem
from carteira_clean_web.backend.db.session import get_session

log = logging.getLogger("maestro_chat")

router = APIRouter(prefix="/maestro", tags=["maestro"])

# ── Anthropic ────────────────────────────────────────────────────────────────

try:
    import anthropic as _anthropic_lib
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

MODEL = "claude-opus-4-8"

# ── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """═══════════════════════════════════════════════════════════
ESTILO DE COMUNICAÇÃO (respeitar sempre)
═══════════════════════════════════════════════════════════

- Entre direto no assunto. Sem preâmbulos, sem introduções cerimoniais
  ("Ótima pergunta", "Vou analisar", "Deixa eu puxar").
- Não anuncie o que vai fazer — faça e apresente.
- Não numere seções explicativas (A, B, C) a menos que o usuário peça.
- Respostas concisas. Se cabe em 3 frases, não use 10.
- Quando faltar dado, diga de forma curta e siga ("Não tenho consenso de
  analistas. Com os dados disponíveis:").
- PRESERVAR: honestidade intelectual. Nunca fabricar dado. Avisar quando
  a fonte é limitada. Distinguir dado interno (banco) de externo. Isso é
  substância, não prolixidade — manter.

═══════════════════════════════════════════════════════════

Você é o maestro da carteira de investimentos de Marcio de Almeida Souza,
integrado à ferramenta Carteira Clean.

Seu papel: afiar o raciocínio do investidor e AMPLIAR seu campo de visão.
Você traduz entre duas lentes — o mundo lá fora (contexto de mercado, ativos,
oportunidades) e a carteira aqui dentro (posições, comportamento, IPS). A
decisão de alocação é sempre dele; ele dá o enter. Seu trabalho é fazer com
que essa decisão seja a mais bem-informada possível.

═══════════════════════════════════════════════════════════
REGRA FIXA SOBRE A CARTEIRA
═══════════════════════════════════════════════════════════

A FUNCEF (previdência fechada) está FORA do seu escopo de análise.
O investidor não a gere e já determinou que seja desconsiderada.
Todas as análises de alocação, aderência à IPS, concentração e
rebalanceamento são sobre a Carteira Gerida (excluindo FUNCEF).
Não mencione a FUNCEF a menos que o investidor pergunte
explicitamente sobre ela.

═══════════════════════════════════════════════════════════
PRINCÍPIOS INEGOCIÁVEIS
═══════════════════════════════════════════════════════════

1. TODA métrica numérica vem de uma tool. Nunca estime, invente ou arredonde
   de memória. Se não tem tool para o dado, diga que não tem — nunca fabrique.

2. Reporte fatos. Não provoque nem evite divergência entre análises.
   Convergência e divergência são igualmente legítimas. Neutralidade quanto
   ao resultado, fidelidade ao dado.

3. Fale no momento em que algo pertinente e fundamentado surge. O default é
   falar; o silêncio é que precisa se justificar. "Pertinente" = relevante
   para a IPS, as teses ou o comportamento do investidor. "Fundamentado" =
   sustentado por dados, não por opinião.

4. Sua função é AMPLIAR o campo de visão do investidor, não estreitá-lo.
   Traga ideias que ele não pensou. Busque além da carteira atual — ativos,
   setores, instrumentos que existem no mundo e se encaixam na lógica do que
   ele precisa. Sugira livremente e com profundidade. O que torna isso
   assessoria legítima (e não prescrição) é a estrutura: toda sugestão vem
   com a tese por trás, e a decisão é declaradamente dele. Ele dá o enter.
   Você nunca decide por ele — mas nunca o deixa com menos opções do que
   poderia ter.

═══════════════════════════════════════════════════════════
AÇÕES DE ESCRITA — NÍVEL L2 (propõe → confirma → grava)
═══════════════════════════════════════════════════════════

Você tem tools que GRAVAM no banco: registrar_tese, registrar_decisao_diario,
atualizar_tese, invalidar_tese, criar_alerta. Estas mudam o estado da carteira
do investidor — exigem o protocolo L2:

1. MONTE a ação a partir do que o investidor disse.
2. MOSTRE antes de gravar, em formato claro: "Vou registrar: [campos].
   Confirma?" — liste cada campo que será gravado.
3. SÓ chame a tool de escrita DEPOIS de uma confirmação afirmativa explícita
   ("sim", "pode", "confirma", "grava"). Nunca grave por iniciativa própria.
4. Se o investidor disser "não" ou pedir ajuste, ajuste a proposta e mostre
   de novo. Não grave até ele aprovar.

Nunca chame uma tool de escrita na mesma resposta em que propõe — proponha,
espere a confirmação na próxima mensagem, então grave.

listar_alertas, verificar_alertas, forcar_coleta e pesquisar_web NÃO exigem L2:
- listar_alertas: use quando o investidor perguntar quais alertas existem
  (lista todos os cadastrados). O painel "Alertas" do app mostra a mesma lista.
- verificar_alertas: chame no INÍCIO da conversa; se algo disparou, reporte
  logo. Se nada disparou, não precisa mencionar.
- forcar_coleta: use quando detectar dado defasado e avise o que está fazendo.
- pesquisar_web: use quando precisar de dado não disponível no banco interno
  (consenso de analistas, preço-alvo, notícias recentes, contexto macro do dia).

═══════════════════════════════════════════════════════════
USO DA WEB — HIERARQUIA DE FONTES E DISCIPLINA
═══════════════════════════════════════════════════════════

Ao buscar dados na web com pesquisar_web, formule queries direcionadas:

TIER 1 — Dados e múltiplos:
  tradingview.com → consenso, preço-alvo, técnico
  investidor10.com.br → fundamentos BR, preço justo
  statusinvest.com.br → fundamentos BR, comparação
  fundamentus.com.br → dados brutos, screener

TIER 2 — Research:
  analisa.genialinvestimentos.com.br → Genial
  nordinvestimentos.com.br → Nord
  suno.com.br → Suno
  kinea.com.br → macro

TIER 3 — Dados oficiais:
  b3.com.br, cvm.gov.br, bcb.gov.br

TIER 4 — Notícias:
  infomoney.com.br, valorinveste.globo.com, bloomberglinea.com.br

TIER 5 — Internacional (BDRs):
  tradingview.com, finance.yahoo.com, seekingalpha.com

DICA DE QUERY: "TICKER informação site:fonte.com.br" para resultados precisos.
Ex: "ITUB3 preço alvo consenso site:tradingview.com"

DISCIPLINA (anti-alucinação — obrigatória ao usar pesquisar_web):
- SEMPRE citar fonte (nome do site + URL) ao apresentar resultado.
- Dado de web = "contexto externo não verificado" — distinto do banco interno.
- Nunca apresentar dado de blog/fórum como research de casa de análise.
- Ao citar casa de análise: "segundo a [casa], ..."
- Se a busca não retornar fonte confiável, diga que não encontrou dado confiável.

═══════════════════════════════════════════════════════════
COMO PENSAR (não apenas reportar)
═══════════════════════════════════════════════════════════

Vá além do óbvio. Não pare em "bloco X está fora da banda". Pergunte-se:

- DENTRO do bloco: há concentração monotemática? Um único ativo domina? A
  diversificação interna é real ou ilusória?

- ENTRE blocos: há sobreposição setorial que o investidor talvez não veja?
  Há ativos classificados num bloco que pela natureza caberiam em outro?

- AO LONGO DO TEMPO: o desvio da IPS está se abrindo ou fechando?

- CRUZANDO LENTES: a exposição setorial (espelho) faz sentido dado o momento
  do setor (janela)?

- OLHAR PARA FORA: quando há um buraco na carteira, não se limite ao que o
  investidor já tem. Traga nomes concretos, explique a tese de cada um,
  aponte trade-offs.

═══════════════════════════════════════════════════════════
DISCIPLINAS DE GESTÃO (referência: IPS v1.0)
═══════════════════════════════════════════════════════════

- IPS: 4 blocos (Swing Trade 30% ±10pp, Growth 20% ±10pp, Defensivos 20% ±5pp,
  Renda Fixa 30% ±5pp). Use como régua e como bússola.
- Teses com invalidação: monitore critérios de invalidação registrados.
- Atribuição (Brinson-Fachler): use para responder "meu retorno vem de
  alocação ou de seleção?"
- Risco: aponte concentração, correlação implícita entre posições, e liquidez
  quando relevante.

═══════════════════════════════════════════════════════════
TOM E FORMATO
═══════════════════════════════════════════════════════════

- Português brasileiro, preciso com números (R$ com formatação BR).
- Conciso por padrão (3-8 linhas). Expanda quando a análise exigir.
- Tabelas para comparações, bullets para listas curtas.
- Não repita dados que o investidor já vê no dashboard — interprete-os.
- Não seja servil nem evasivo. Fale com a franqueza de um sócio que respeita
  a autonomia do outro."""

# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "obter_posicoes",
        "description": "Retorna todas as posições ativas com P&L e alertas.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obter_performance",
        "description": "Retorna performance da carteira no período comparada com benchmarks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "description": "Período: ytd, 1m, 3m, 6m, 1a (default: ytd)",
                    "enum": ["ytd", "1m", "3m", "6m", "1a"],
                },
                "benchmark": {
                    "type": "string",
                    "description": "CDI, IBOV ou AMBOS (default: ambos)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "obter_cotacao",
        "description": "Busca cotação ao vivo via yfinance e cruza com posição na carteira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo (ex: WEGE3, PETR4)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "obter_diario",
        "description": "Retorna entradas do diário de decisões.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo": {"type": "string", "description": "7d, 30d, 90d, all (default: 30d)"},
                "busca": {"type": "string", "description": "Texto para filtrar entradas"},
                "ticker": {"type": "string", "description": "Filtrar por ticker"},
            },
            "required": [],
        },
    },
    {
        "name": "obter_sinais",
        "description": "Retorna sinais técnicos (RSI/MACD/MM) e fundamentos para ativos da carteira ou lista.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tickers. Sem filtro = carteira inteira",
                },
                "apenas_ativos": {"type": "boolean", "description": "Se true, retorna apenas ativos com sinal ativo"},
            },
            "required": [],
        },
    },
    {
        "name": "obter_fundamentos",
        "description": "Retorna indicadores fundamentalistas (P/L, P/VP, ROE, etc.) da carteira ou lista.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tickers. Sem filtro = carteira inteira",
                },
            },
            "required": [],
        },
    },
    {
        "name": "consultar_fundamentos",
        "description": "Retorna os últimos indicadores fundamentalistas persistidos no DB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tickers. Sem filtro = carteira inteira",
                },
            },
            "required": [],
        },
    },
    {
        "name": "obter_watchlist",
        "description": "Retorna a watchlist com cotações ao vivo e distância até o preço-alvo.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obter_analise_rv",
        "description": "Análise completa da carteira RV: posições + sinais técnicos + fundamentos + watchlist. Use esta quando o usuário pedir análise geral da carteira RV.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "obter_brinson",
        "description": "Retorna decomposição Brinson-Fachler por bloco IPS (efeito alocação vs seleção).",
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "string", "description": "YYYY-MM. Sem filtro = todos os meses"},
                "bloco_ips": {
                    "type": "string",
                    "description": "SWING_TRADE, GROWTH, DEFENSIVOS, RENDA_FIXA ou TOTAL",
                },
            },
            "required": [],
        },
    },
    {
        "name": "obter_atribuicao",
        "description": "Retorna atribuição mensal: quais ativos contribuíram para a performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "string", "description": "YYYY-MM"},
                "composite": {"type": "string", "description": "Gerida, FUNCEF ou TOTAL_CARTEIRA"},
                "bloco_ips": {
                    "type": "string",
                    "description": "SWING_TRADE, GROWTH, RENDA_FIXA, DEFENSIVOS ou FORA_IPS",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analise_aderencia_setorial",
        "description": "Cruza exposição setorial real vs. IPS com desempenho recente dos índices B3. Use esta (nunca obter_posicoes) para aderência à IPS, concentração setorial, blocos fora da banda, rebalanceamento entre blocos.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "consultar_teses",
        "description": "Retorna teses de investimento ativas (ou de um ticker específico).",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filtrar por ticker (opcional)"},
            },
            "required": [],
        },
    },
    {
        "name": "consultar_diario_decisoes",
        "description": "Retorna entradas do diário de decisão estruturado com resultado dinâmico.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filtrar por ticker (opcional)"},
                "periodo": {"type": "string", "description": "7d, 30d, 90d, all (default: 90d)"},
            },
            "required": [],
        },
    },
    {
        "name": "risco_carteira",
        "description": "Risco ex-ante: exposição por fator, drawdown, liquidez e stress.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "exposicao, drawdown, liquidez, stress ou todos (default: todos)",
                    "enum": ["exposicao", "drawdown", "liquidez", "stress", "todos"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "disciplina_caixa",
        "description": "Monitoramento de caixa e aderência ao plano de aportes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "consultar_macro",
        "description": "Retorna os últimos pontos de cada indicador macro persistido (SELIC_META, IPCA, USD_BRL, IPCA_FOCUS).",
        "input_schema": {
            "type": "object",
            "properties": {
                "indicadores": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de indicadores. Sem filtro = todos",
                },
                "ultimos_n": {"type": "integer", "description": "Número de observações por indicador (default: 12)"},
            },
            "required": [],
        },
    },
    {
        "name": "consultar_eventos_corporativos",
        "description": "Retorna eventos corporativos futuros (earnings, ex-dividend) dos ativos em carteira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Filtrar por ativo específico. None = todos"},
                "janela_dias": {"type": "integer", "description": "Horizonte em dias (default: 60)"},
            },
            "required": [],
        },
    },
    {
        "name": "perfil_comportamental",
        "description": "Perfil comportamental calculado sobre o event log: turnover, holding, frequencia, concentracao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metrica": {
                    "type": "string",
                    "description": "turnover | holding | frequencia | concentracao | todos (default: todos)",
                    "enum": ["turnover", "holding", "frequencia", "concentracao", "todos"],
                },
                "periodo_meses": {
                    "type": "integer",
                    "description": "Janela de análise em meses (default: 12)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "divergencias_dito_feito",
        "description": "Cruzamento dito-vs-feito: compara declarações (IPS, teses, diário) com comportamento real.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "horizonte | alocacao | conviccao | invalidacao | todos (default: todos)",
                    "enum": ["horizonte", "alocacao", "conviccao", "invalidacao", "todos"],
                },
                "periodo_meses": {
                    "type": "integer",
                    "description": "Janela para padrões comportamentais (default: 6)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "vieses_comportamentais",
        "description": "Detecta 5 vieses comportamentais a partir do event log: disposition_effect, overtrading, subdiversificacao, clustering_temporal, trend_chasing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "periodo_meses": {
                    "type": "integer",
                    "description": "Janela de análise em meses (default: 12)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "analise_fundamentalista",
        "description": "Análise fundamentalista em 4 dimensões para um ativo, comparando com peers do mesmo setor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo (ex: WEGE3)"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "screening_fundamentalista",
        "description": "Filtra ativos da carteira + watchlist por critérios fundamentalistas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "roe_min": {"type": "number", "description": "ROE mínimo (%)"},
                "dy_min": {"type": "number", "description": "DY mínimo (%)"},
                "pl_max": {"type": "number", "description": "P/L máximo"},
                "div_liq_ebitda_max": {"type": "number", "description": "Dív.Líq/EBITDA máximo"},
                "margem_ebitda_min": {"type": "number", "description": "Margem EBITDA mínima (%)"},
            },
            "required": [],
        },
    },
    {
        "name": "comparar_multiplos",
        "description": "Tabela side-by-side de múltiplos fundamentalistas para 2-5 tickers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de 2 a 5 tickers",
                },
            },
            "required": ["tickers"],
        },
    },
    {
        "name": "contexto_setorial",
        "description": "Contexto setorial: performance recente do índice B3 + macro relevante + ativos da carteira.",
        "input_schema": {
            "type": "object",
            "properties": {
                "setor": {
                    "type": "string",
                    "description": "Código do índice (ex: 'IFNC'), nome amigável (ex: 'Bancos', 'Imobiliário') ou 'todos' (default: todos)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "regime_mercado",
        "description": "Classifica o regime macroeconômico atual em 4 eixos: juros, inflação, câmbio, bolsa.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "analise_tecnica",
        "description": "Análise técnica com sistema de votação (MM20/50/200, RSI, MACD, Bollinger) para um ativo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo (ex: PETR4, WEGE3)"},
                "periodo": {
                    "type": "string",
                    "description": "1mo | 3mo | 6mo | 1y | 2y (default: 6mo)",
                    "enum": ["1mo", "3mo", "6mo", "1y", "2y"],
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "grafico_tecnico",
        "description": "Gera gráfico candlestick interativo (Plotly HTML) com MMs, Bollinger, RSI e volume.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo"},
                "periodo": {
                    "type": "string",
                    "description": "1mo | 3mo | 6mo | 1y | 2y (default: 6mo)",
                    "enum": ["1mo", "3mo", "6mo", "1y", "2y"],
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "noticias_ativos",
        "description": "Retorna notícias recentes dos ativos via yfinance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Código do ativo, 'carteira' (top-10) ou 'watchlist' (default: carteira)",
                },
                "dias": {"type": "integer", "description": "Janela em dias (default: 7)"},
            },
            "required": [],
        },
    },
    {
        "name": "impacto_macro",
        "description": "Avalia o impacto de um evento macro nos ativos da carteira usando matriz de sensibilidade.",
        "input_schema": {
            "type": "object",
            "properties": {
                "evento": {
                    "type": "string",
                    "description": "Texto livre (ex: 'queda de 0.5pp na Selic')",
                },
                "indicador": {
                    "type": "string",
                    "description": "SELIC_META | USD_BRL | IPCA | IPCA_FOCUS",
                },
                "variacao": {
                    "type": "string",
                    "description": "ALTA ou QUEDA (default: QUEDA)",
                    "enum": ["ALTA", "QUEDA"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "consultar_glossario",
        "description": "Retorna definição de indicadores e vieses comportamentais.",
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {
                    "type": "string",
                    "description": "Nome ou código do indicador (ex: 'P/L', 'RSI', 'disposition effect')",
                },
                "categoria": {
                    "type": "string",
                    "description": "fundamentalista | tecnico | comportamental",
                },
            },
            "required": [],
        },
    },
    # ── CAMADA 3 — TOOLS DE ESCRITA (L2: confirme antes de chamar) ────────────
    {
        "name": "registrar_tese",
        "description": (
            "Grava uma nova tese de investimento. ESCRITA L2: só chame DEPOIS "
            "de mostrar os detalhes ao investidor e ele confirmar explicitamente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo"},
                "racional": {"type": "string", "description": "Tese central — por que investir"},
                "bloco_ips": {"type": "string", "description": "SWING_TRADE | GROWTH | DEFENSIVOS | RENDA_FIXA"},
                "cenario_esperado": {"type": "string", "description": "Cenário-base esperado"},
                "criterio_invalidacao": {"type": "string", "description": "O que invalidaria a tese"},
                "gatilho": {"type": "string", "description": "Gatilho de monitoramento"},
            },
            "required": ["ticker", "racional"],
        },
    },
    {
        "name": "registrar_decisao_diario",
        "description": (
            "Grava uma decisão no diário estruturado. ESCRITA L2: só chame "
            "após o investidor confirmar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Código do ativo"},
                "acao": {"type": "string", "description": "COMPRA | VENDA | AUMENTO | REDUCAO | MANTER | WATCHLIST"},
                "racional": {"type": "string", "description": "Por que tomou a decisão"},
                "conviccao": {"type": "integer", "description": "Convicção de 1 a 5 (default 3)"},
                "preco": {"type": "number", "description": "Preço de entrada/referência"},
                "cenario_esperado": {"type": "string", "description": "Cenário esperado"},
                "tese_id": {"type": "integer", "description": "ID de tese a vincular (opcional)"},
            },
            "required": ["ticker", "acao", "racional"],
        },
    },
    {
        "name": "atualizar_tese",
        "description": (
            "Atualiza campos de uma tese existente. ESCRITA L2: só após confirmação. "
            "Passe apenas os campos a alterar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tese_id": {"type": "integer", "description": "ID da tese"},
                "racional": {"type": "string"},
                "bloco_ips": {"type": "string"},
                "cenario_esperado": {"type": "string"},
                "criterio_invalidacao": {"type": "string"},
                "nivel_invalidacao": {"type": "string", "description": "VERDE | AMARELO | VERMELHO"},
            },
            "required": ["tese_id"],
        },
    },
    {
        "name": "invalidar_tese",
        "description": (
            "Marca uma tese como INVALIDADA com motivo. ESCRITA L2: só após confirmação."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tese_id": {"type": "integer", "description": "ID da tese"},
                "motivo": {"type": "string", "description": "Motivo da invalidação"},
            },
            "required": ["tese_id", "motivo"],
        },
    },
    {
        "name": "criar_alerta",
        "description": (
            "Cadastra um alerta/gatilho monitorável. ESCRITA L2: só após confirmação. "
            "Tipos: RSI (ativo=ticker), preco (ativo=ticker), banda_IPS (ativo=bloco_ips), "
            "invalidacao (ativo=tese_id)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "description": "RSI | banda_IPS | preco | invalidacao"},
                "condicao": {"type": "string", "description": "Operador: '>=', '<=', 'fora_banda'"},
                "ativo": {"type": "string", "description": "Alvo: ticker, bloco_ips ou tese_id"},
                "valor_gatilho": {"type": "number", "description": "Limiar numérico (ex: 80 p/ RSI>=80)"},
            },
            "required": ["tipo", "condicao"],
        },
    },
    {
        "name": "listar_alertas",
        "description": (
            "Lista os alertas cadastrados (habilitados e desabilitados). LEITURA — "
            "use quando o investidor perguntar quais alertas existem. Diferente de "
            "verificar_alertas, que só reporta os que dispararam."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "apenas_ativos": {"type": "boolean", "description": "Se true, só os habilitados"},
            },
            "required": [],
        },
    },
    {
        "name": "verificar_alertas",
        "description": (
            "Verifica todos os alertas cadastrados e reporta quais dispararam. "
            "LEITURA — chame no INÍCIO da conversa e relate os disparos ao investidor."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "forcar_coleta",
        "description": (
            "Dispara coleta de dados sob demanda quando detectar dado velho. "
            "tipo: cotacoes | fundamentos | macro | eventos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "description": "cotacoes | fundamentos | macro | eventos"},
            },
            "required": ["tipo"],
        },
    },
    {
        "name": "pesquisar_web",
        "description": (
            "Busca na internet via DuckDuckGo. Use para dados NÃO disponíveis no banco interno: "
            "consenso de analistas, preço-alvo, notícias recentes, contexto macro do dia. "
            "Formule queries direcionadas com site: para resultados melhores. "
            "Ex: 'ITUB3 preço alvo consenso site:tradingview.com'. "
            "SEMPRE cite fonte ao apresentar resultado — dado de web ≠ dado do banco."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto da busca. Use 'TICKER info site:fonte.com' para resultados direcionados."},
                "max_results": {"type": "integer", "description": "Número de resultados (padrão 5, máximo 10)"},
            },
            "required": ["query"],
        },
    },
]

# ── Tool function dispatch ───────────────────────────────────────────────────

def _dispatch_tool(name: str, inputs: dict) -> dict:
    """Executa a função Python correspondente ao tool call."""
    from carteira_clean_web.backend.mcp.tools.portfolio import (
        fn_obter_posicoes,
        fn_obter_performance,
        fn_obter_cotacao,
        fn_obter_diario,
        fn_obter_sinais,
        fn_obter_fundamentos,
        fn_consultar_fundamentos,
        fn_obter_watchlist,
        fn_obter_analise_rv,
        fn_brinson,
        fn_atribuicao,
        fn_analise_aderencia_setorial,
        fn_consultar_teses,
        fn_consultar_diario_decisoes,
        fn_risco_carteira,
        fn_disciplina_caixa,
        fn_consultar_macro,
        fn_consultar_eventos_corporativos,
        fn_perfil_comportamental,
        fn_divergencias_dito_feito,
        fn_vieses_comportamentais,
        fn_analise_fundamentalista,
        fn_screening_fundamentalista,
        fn_comparar_multiplos,
        fn_contexto_setorial,
        fn_regime_mercado,
        fn_analise_tecnica,
        fn_grafico_tecnico,
        fn_noticias_ativos,
        fn_impacto_macro,
        fn_consultar_glossario,
        fn_registrar_tese,
        fn_registrar_decisao_diario,
        fn_atualizar_tese,
        fn_invalidar_tese,
        fn_criar_alerta,
        fn_listar_alertas,
        fn_verificar_alertas,
        fn_forcar_coleta,
        fn_pesquisar_web,
    )

    dispatch: dict[str, Any] = {
        "obter_posicoes":                 lambda: fn_obter_posicoes(),
        "obter_performance":              lambda: fn_obter_performance(**inputs),
        "obter_cotacao":                  lambda: fn_obter_cotacao(**inputs),
        "obter_diario":                   lambda: fn_obter_diario(**inputs),
        "obter_sinais":                   lambda: fn_obter_sinais(**inputs),
        "obter_fundamentos":              lambda: fn_obter_fundamentos(**inputs),
        "consultar_fundamentos":          lambda: fn_consultar_fundamentos(**inputs),
        "obter_watchlist":                lambda: fn_obter_watchlist(),
        "obter_analise_rv":               lambda: fn_obter_analise_rv(),
        "obter_brinson":                  lambda: fn_brinson(**inputs),
        "obter_atribuicao":               lambda: fn_atribuicao(**inputs),
        "analise_aderencia_setorial":     lambda: fn_analise_aderencia_setorial(),
        "consultar_teses":                lambda: fn_consultar_teses(**inputs),
        "consultar_diario_decisoes":      lambda: fn_consultar_diario_decisoes(**inputs),
        "risco_carteira":                 lambda: fn_risco_carteira(**inputs),
        "disciplina_caixa":               lambda: fn_disciplina_caixa(),
        "consultar_macro":                lambda: fn_consultar_macro(**inputs),
        "consultar_eventos_corporativos": lambda: fn_consultar_eventos_corporativos(**inputs),
        "perfil_comportamental":          lambda: fn_perfil_comportamental(**inputs),
        "divergencias_dito_feito":        lambda: fn_divergencias_dito_feito(**inputs),
        "vieses_comportamentais":         lambda: fn_vieses_comportamentais(**inputs),
        "analise_fundamentalista":        lambda: fn_analise_fundamentalista(**inputs),
        "screening_fundamentalista":      lambda: fn_screening_fundamentalista(**inputs),
        "comparar_multiplos":             lambda: fn_comparar_multiplos(**inputs),
        "contexto_setorial":              lambda: fn_contexto_setorial(**inputs),
        "regime_mercado":                 lambda: fn_regime_mercado(),
        "analise_tecnica":                lambda: fn_analise_tecnica(**inputs),
        "grafico_tecnico":                lambda: fn_grafico_tecnico(**inputs),
        "noticias_ativos":                lambda: fn_noticias_ativos(**inputs),
        "impacto_macro":                  lambda: fn_impacto_macro(**inputs),
        "consultar_glossario":            lambda: fn_consultar_glossario(**inputs),
        "registrar_tese":                 lambda: fn_registrar_tese(**inputs),
        "registrar_decisao_diario":       lambda: fn_registrar_decisao_diario(**inputs),
        "atualizar_tese":                 lambda: fn_atualizar_tese(**inputs),
        "invalidar_tese":                 lambda: fn_invalidar_tese(**inputs),
        "criar_alerta":                   lambda: fn_criar_alerta(**inputs),
        "listar_alertas":                 lambda: fn_listar_alertas(**inputs),
        "verificar_alertas":              lambda: fn_verificar_alertas(),
        "forcar_coleta":                  lambda: fn_forcar_coleta(**inputs),
        "pesquisar_web":                  lambda: fn_pesquisar_web(**inputs),
    }

    fn = dispatch.get(name)
    if fn is None:
        return {"erro": f"Tool desconhecida: {name}"}
    try:
        return fn()
    except Exception as exc:
        log.exception("Tool %s falhou", name)
        return {"erro": str(exc)}


# ── Request schema ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    thread_id: str = ""
    nivel_automacao: dict = {}


# ── SSE helper ───────────────────────────────────────────────────────────────

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ── Streaming generator ──────────────────────────────────────────────────────

def _db_criar_ou_obter_conversa(thread_id: str) -> tuple[int, bool]:
    """Retorna (conversa_id, is_new). Cria conversa no DB se thread_id não for numérico."""
    if thread_id.isdigit():
        return int(thread_id), False
    now = datetime.utcnow()
    db = get_session()
    try:
        c = Conversa(titulo="Nova conversa", criada_em=now, atualizada_em=now,
                     ativa=1, total_msgs=0, total_tokens=0, custo_usd=0.0)
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id, True
    finally:
        db.close()


def _db_salvar_mensagens(conversa_id: int, user_text: str, assistant_text: str) -> None:
    """Salva par user/assistant no DB e atualiza metadados da conversa."""
    db = get_session()
    try:
        now = datetime.utcnow()
        for role, content in [("user", user_text), ("assistant", assistant_text)]:
            if content.strip():
                db.add(Mensagem(
                    conversa_id=conversa_id, role=role, content=content,
                    tokens_in=0, tokens_out=0, custo_usd=0.0, criada_em=now,
                ))
        c = db.get(Conversa, conversa_id)
        if c:
            c.total_msgs = (c.total_msgs or 0) + 2
            c.atualizada_em = now
            if c.titulo == "Nova conversa" and user_text.strip():
                c.titulo = user_text.strip()[:60]
        db.commit()
    finally:
        db.close()


async def _stream_chat(request: ChatRequest) -> AsyncIterator[str]:
    if not _HAS_ANTHROPIC:
        yield _sse({"type": "TEXT_MESSAGE_START", "messageId": "err", "role": "assistant"})
        yield _sse({"type": "TEXT_MESSAGE_CONTENT", "messageId": "err", "delta": "Pacote anthropic não instalado no servidor."})
        yield _sse({"type": "TEXT_MESSAGE_END", "messageId": "err"})
        yield _sse({"type": "RUN_FINISHED"})
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        yield _sse({"type": "TEXT_MESSAGE_START", "messageId": "err", "role": "assistant"})
        yield _sse({"type": "TEXT_MESSAGE_CONTENT", "messageId": "err", "delta": "ANTHROPIC_API_KEY não configurada no servidor."})
        yield _sse({"type": "TEXT_MESSAGE_END", "messageId": "err"})
        yield _sse({"type": "RUN_FINISHED"})
        return

    # Criar ou recuperar conversa no DB
    loop = asyncio.get_event_loop()
    conversa_id, is_new = await loop.run_in_executor(
        None, _db_criar_ou_obter_conversa, request.thread_id
    )
    if is_new:
        yield _sse({"type": "CONVERSA_ID", "conversaId": conversa_id})

    client = _anthropic_lib.Anthropic(api_key=api_key)

    # Converter mensagens
    messages: list[dict] = [{"role": m.role, "content": m.content} for m in request.messages]

    # Texto do usuário (última mensagem) e texto acumulado do assistente
    user_text = next((m.content for m in reversed(request.messages) if m.role == "user"), "")
    assistant_text_acc: list[str] = []

    loop = asyncio.get_event_loop()

    # Loop de agentic tool use
    while True:
        msg_id = str(uuid.uuid4())[:8]
        text_started = False
        tool_calls_in_turn: list[dict] = []

        def _call_api(msgs=messages):
            return client.messages.create(
                model=MODEL,
                max_tokens=8192,
                system=_SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=msgs,
                timeout=120,
            )

        try:
            response = await loop.run_in_executor(None, _call_api)
        except Exception as exc:
            log.exception("Anthropic API error")
            yield _sse({"type": "TEXT_MESSAGE_START", "messageId": msg_id, "role": "assistant"})
            yield _sse({"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id, "delta": f"Erro na API: {exc}"})
            yield _sse({"type": "TEXT_MESSAGE_END", "messageId": msg_id})
            yield _sse({"type": "RUN_FINISHED"})
            return

        # Processar blocos de conteúdo
        for block in response.content:
            if block.type == "text":
                if not text_started:
                    yield _sse({"type": "TEXT_MESSAGE_START", "messageId": msg_id, "role": "assistant"})
                    text_started = True
                # Simular streaming em chunks
                text = block.text
                assistant_text_acc.append(text)
                chunk_size = 20
                for i in range(0, len(text), chunk_size):
                    chunk = text[i : i + chunk_size]
                    yield _sse({"type": "TEXT_MESSAGE_CONTENT", "messageId": msg_id, "delta": chunk})
                    await asyncio.sleep(0)

            elif block.type == "tool_use":
                tool_call_id = block.id
                tool_name = block.name
                tool_input = dict(block.input) if block.input else {}

                yield _sse({
                    "type": "TOOL_CALL_START",
                    "toolCallId": tool_call_id,
                    "toolCallName": tool_name,
                    "parentMessageId": msg_id,
                })
                yield _sse({
                    "type": "TOOL_CALL_ARGS_DELTA",
                    "toolCallId": tool_call_id,
                    "delta": json.dumps(tool_input, ensure_ascii=False),
                })
                yield _sse({"type": "TOOL_CALL_END", "toolCallId": tool_call_id})

                # Executar tool em executor (bloqueante)
                tool_result = await loop.run_in_executor(
                    None, _dispatch_tool, tool_name, tool_input
                )
                # Emite resultado para o frontend poder renderizar charts/dados
                yield _sse({
                    "type": "TOOL_CALL_RESULT",
                    "toolCallId": tool_call_id,
                    "toolCallName": tool_name,
                    "result": json.dumps(tool_result, ensure_ascii=False, default=str),
                })
                tool_calls_in_turn.append({
                    "tool_use_id": tool_call_id,
                    "result": tool_result,
                })

        if text_started:
            yield _sse({"type": "TEXT_MESSAGE_END", "messageId": msg_id})

        # Se stop_reason == "end_turn" ou sem tool calls — terminamos
        if response.stop_reason == "end_turn" or not tool_calls_in_turn:
            # Salvar mensagens no DB
            assistant_text = " ".join(assistant_text_acc).strip()
            await loop.run_in_executor(
                None, _db_salvar_mensagens, conversa_id, user_text, assistant_text
            )
            yield _sse({"type": "RUN_FINISHED"})
            return

        # Adicionar turn do assistente e resultados das tools
        messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]
        tool_results_content = [
            {
                "type": "tool_result",
                "tool_use_id": tc["tool_use_id"],
                "content": json.dumps(tc["result"], ensure_ascii=False, default=str),
            }
            for tc in tool_calls_in_turn
        ]
        messages.append({"role": "user", "content": tool_results_content})  # type: ignore[arg-type]
        # Continua o loop para próxima resposta


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat")
async def maestro_chat(
    body: ChatRequest,
    _email: Annotated[str, Depends(require_auth)],
):
    """Streaming chat com o Maestro via AG-UI events (SSE)."""
    return StreamingResponse(
        _stream_chat(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
