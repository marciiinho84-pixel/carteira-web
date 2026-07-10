"""
MCP Tools: obter_posicoes, obter_performance, obter_cotacao

Lêem do cache em memória (sem recalcular).
obter_cotacao busca dados ao vivo via yfinance com cache local de 15 min.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO, AGREGADO_PRIVADO
from carteira_clean_web.backend.engine.utils import preco_em
from carteira_clean_web.backend.engine.valorizacao import valorizar_posicao, determinar_preco_atual
from carteira_clean_web.backend.mcp.schemas import (
    PorClasse, Resumo, Posicao, ResultadoPosicoes,
    RetornoBenchmark, Risco, ResultadoPerformance,
    MinhaPosicao, ResultadoCotacao,
)

# ── Cache local de cotações (module-level, TTL = 15 min) ──────────
_cache_cotacoes: dict = {}
CACHE_TTL_MINUTOS = 15


def _obter_do_cache(ticker: str) -> dict | None:
    if ticker not in _cache_cotacoes:
        return None
    entrada = _cache_cotacoes[ticker]
    idade_s = (datetime.now() - entrada["timestamp"]).total_seconds()
    if idade_s > CACHE_TTL_MINUTOS * 60:
        return None
    return entrada


def _salvar_no_cache(ticker: str, dados: dict):
    _cache_cotacoes[ticker] = {"dados": dados, "timestamp": datetime.now()}


def _formatar_ticker_yfinance(ticker: str) -> str:
    """
    WEGE3   → WEGE3.SA   (ação B3: letras + números)
    MSFT34  → MSFT34.SA  (BDR: letras + 34/11/etc.)
    WEGE3.SA → WEGE3.SA  (já formatado)
    MSFT    → MSFT       (ativo US: só letras)
    ^BVSP   → ^BVSP      (índice)
    """
    ticker = ticker.upper().strip()
    if ticker.endswith(".SA") or ticker.startswith("^"):
        return ticker
    # padrão B3: 3-5 letras seguidas de 1-2 dígitos
    if re.match(r"^[A-Z]{3,5}\d{1,2}$", ticker):
        return f"{ticker}.SA"
    # parece ativo internacional (só letras ou padrão não-B3)
    return ticker


def fn_obter_posicoes() -> dict:
    """Retorna todas as posições ativas com P&L e alertas."""
    # MCP server roda em processo separado — tentar carregar do disco se memória vazia
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()

    if not engine_cache.esta_calculado():
        return {
            "erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."
        }

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    patrimonio_total = 0.0
    patrimonio_gerida = 0.0
    if not df_evo.empty:
        ult = df_evo.iloc[-1]
        patrimonio_total = ult["patrimonio_total"]
        patrimonio_gerida = ult["patrimonio_gerida"]

    # ── Montar lista de posições ativas ────────────────────────────
    posicoes_raw = []
    for tkr in sorted(posicoes_dict.keys()):
        p = posicoes_dict[tkr]
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")

        # Ignorar posições zeradas (exceto AGREGADO_PRIVADO que tem valor sem qtd)
        if p.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue

        v = valorizar_posicao(p, tkr, ativos, precos_pub, precos_man, hoje)
        preco_atual = v["preco_atual"]
        valor_atual = v["valor_atual"]

        preco_atual = preco_atual if preco_atual else 0.0

        posicoes_raw.append({
            "ticker": tkr,
            "classe": info.get("classe", "—"),
            "familia": familia,
            "setor": info.get("setor", "—"),
            "composite": info.get("composite", "Gerida"),
            "qtd": p.qtd,
            "preco_atual": preco_atual,
            "valor_atual": valor_atual,
            "custo_total": p.custo_total,
            "custo_medio": p.custo_medio,
        })

    # Ordenar por valor DESC para determinar maior posição
    posicoes_raw.sort(key=lambda x: -x["valor_atual"])

    if not posicoes_raw:
        return {"erro": "Nenhuma posição ativa encontrada."}

    maior_valor = posicoes_raw[0]["valor_atual"] if posicoes_raw else 0.0

    # ── Resumo por classe ──────────────────────────────────────────
    por_classe: dict[str, float] = defaultdict(float)
    for p in posicoes_raw:
        por_classe[p["classe"]] += p["valor_atual"]

    total_posicoes = sum(por_classe.values())

    resumo_por_classe = {
        cls: PorClasse(
            valor=round(val, 2),
            pct=round(val / patrimonio_total * 100, 2) if patrimonio_total > 0 else 0.0,
        )
        for cls, val in sorted(por_classe.items(), key=lambda x: -x[1])
    }

    # P&L total (soma de todas as posições)
    custo_total_carteira = sum(p["custo_total"] for p in posicoes_raw)
    pl_total_reais = total_posicoes - custo_total_carteira
    pl_total_pct = (pl_total_reais / custo_total_carteira * 100) if custo_total_carteira > 0 else 0.0

    resumo = Resumo(
        por_classe=resumo_por_classe,
        total_posicoes_ativas=len(posicoes_raw),
        pl_total_reais=round(pl_total_reais, 2),
        pl_total_pct=round(pl_total_pct, 4),
    )

    # ── Construir objetos Posicao ──────────────────────────────────
    posicoes_out = []
    for p in posicoes_raw:
        cm = p["custo_medio"]
        preco = p["preco_atual"]
        pl_pct = ((preco - cm) / cm * 100) if cm and cm > 0 else None
        pl_reais = p["valor_atual"] - p["custo_total"]
        pct_carteira = (p["valor_atual"] / patrimonio_total * 100) if patrimonio_total > 0 else 0.0

        posicoes_out.append(Posicao(
            ticker=p["ticker"],
            nome=p["ticker"],  # nome = ticker (não há campo nome separado)
            classe=p["classe"],
            setor=p["setor"],
            composite=p["composite"],
            qtd=round(p["qtd"], 6),
            preco_atual=round(preco, 4),
            valor_atual=round(p["valor_atual"], 2),
            custo_medio=round(cm, 4) if cm else None,
            pl_percentual=round(pl_pct, 4) if pl_pct is not None else None,
            pl_reais=round(pl_reais, 2),
            pct_carteira=round(pct_carteira, 2),
            maior_posicao=(p["valor_atual"] >= maior_valor * 0.9999),
        ))

    # ── Alertas automáticos ────────────────────────────────────────
    alertas = []

    # Caixa FIC FUNC sempre informado
    caixa_fic = next((p for p in posicoes_raw if p["ticker"] == "CAIXA FIC FUNC"), None)
    if caixa_fic:
        alertas.append(f"💰 Caixa FIC FUNC disponível: R$ {caixa_fic['valor_atual']:,.2f}")

    # Concentração por ativo (> 80% do total)
    for p in posicoes_raw:
        pct = p["valor_atual"] / patrimonio_total * 100 if patrimonio_total > 0 else 0
        if pct > 80:
            alertas.append(
                f"⚠️ {p['ticker']} representa {pct:.1f}% do patrimônio total"
            )

    # Concentração por classe (> 50% da classe)
    for p in posicoes_raw:
        total_classe = por_classe.get(p["classe"], 0)
        if total_classe > 0:
            pct_cls = p["valor_atual"] / total_classe * 100
            if pct_cls > 50 and len([x for x in posicoes_raw if x["classe"] == p["classe"]]) > 1:
                alertas.append(
                    f"⚠️ {p['ticker']} é {pct_cls:.1f}% da classe {p['classe']}"
                )

    # Patrimônio abaixo do patamar
    if patrimonio_total < 1_350_000:
        alertas.append(
            f"📉 Patrimônio total (R$ {patrimonio_total:,.0f}) abaixo do patamar de R$ 1.350.000"
        )

    resultado = ResultadoPosicoes(
        data_referencia=str(hoje),
        patrimonio_total=round(patrimonio_total, 2),
        resumo=resumo,
        posicoes=posicoes_out,
        alertas=alertas,
    )
    return resultado.model_dump()


# ── TOOL 2 ────────────────────────────────────────────────────────

_PERIODOS_VALIDOS = {"ytd", "1m", "3m", "6m", "1a"}


def fn_obter_performance(periodo: str = "ytd", benchmark: str = "ambos") -> dict:
    """Retorna performance da carteira no período comparada com benchmarks."""
    # Normalizar inputs
    periodo = periodo.lower().strip()
    benchmark = benchmark.upper().strip()
    if periodo not in _PERIODOS_VALIDOS:
        return {"erro": f"Período inválido: '{periodo}'. Use: ytd, 1m, 3m, 6m, 1a"}

    # Garantir cache carregado
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    estado = engine_cache.get_estado()
    df_evo = estado["df_evo"]
    if df_evo.empty:
        return {"erro": "Série de evolução vazia — recalcule a carteira."}

    hoje = estado["hoje"]

    # ── Determinar data de início desejada ────────────────────────
    if periodo == "ytd":
        data_ini_desejada = df_evo["data"].iloc[0]  # primeiro dia disponível
    elif periodo == "1m":
        data_ini_desejada = hoje - timedelta(days=30)
    elif periodo == "3m":
        data_ini_desejada = hoje - timedelta(days=90)
    elif periodo == "6m":
        data_ini_desejada = hoje - timedelta(days=180)
    else:  # "1a"
        data_ini_desejada = hoje - timedelta(days=365)

    # Ajustar para o dia útil mais próximo disponível na série
    datas_disponiveis = list(df_evo["data"])
    datas_disponiveis_sorted = sorted(datas_disponiveis)

    if periodo == "ytd":
        # YTD sempre usa o início da série — sem ajuste
        data_inicio_real = datas_disponiveis_sorted[0]
        periodo_efetivo = "ytd"
    elif data_ini_desejada <= datas_disponiveis_sorted[0]:
        # Período maior que dados disponíveis — usar o máximo disponível
        data_inicio_real = datas_disponiveis_sorted[0]
        periodo_efetivo = f"máximo disponível ({datas_disponiveis_sorted[0]} até {data_fim_real})"
    else:
        # Encontrar data mais próxima disponível (anterior ou igual à desejada)
        candidatos = [d for d in datas_disponiveis_sorted if d <= data_ini_desejada]
        data_inicio_real = candidatos[-1] if candidatos else datas_disponiveis_sorted[0]
        periodo_efetivo = periodo

    data_fim_real = datas_disponiveis_sorted[-1]

    # ── Filtrar série para o período ──────────────────────────────
    mask = (df_evo["data"] >= data_inicio_real) & (df_evo["data"] <= data_fim_real)
    df_periodo = df_evo[mask].copy()

    if df_periodo.empty or len(df_periodo) < 2:
        return {"erro": "Dados insuficientes para o período solicitado."}

    # ── Cálculo TWR sub-período ───────────────────────────────────
    # twr_cum é acumulado desde o início da série. Para sub-período:
    # twr_subp = (1 + twr_cum_fim) / (1 + twr_cum_inicio_anterior) - 1
    # Usamos a linha ANTERIOR ao início do período como base
    idx_inicio = df_evo[df_evo["data"] == data_inicio_real].index[0]

    if idx_inicio > 0:
        row_base = df_evo.loc[idx_inicio - 1]
    else:
        # Início da série — base é 0
        row_base = None

    row_fim = df_periodo.iloc[-1]

    def _retorno_subperiodo(col_cum: str) -> float:
        v_fim = float(row_fim[col_cum])
        if row_base is not None:
            v_base = float(row_base[col_cum])
            return (1 + v_fim) / (1 + v_base) - 1
        return v_fim

    twr_gerida = _retorno_subperiodo("twr_gerida")
    cdi_subp = _retorno_subperiodo("cdi_acum")
    ibov_subp = _retorno_subperiodo("ibov_acum")

    # ── Dias positivos / negativos (baseado no patrimônio_gerida) ─
    pat = df_periodo["patrimonio_gerida"]
    retornos_diarios = pat.pct_change().dropna()
    dias_positivos = int((retornos_diarios > 0).sum())
    dias_negativos = int((retornos_diarios < 0).sum())
    dias_uteis = len(df_periodo)

    # ── Drawdown máximo no período ────────────────────────────────
    drawdown_max = float(df_periodo["drawdown"].min()) if "drawdown" in df_periodo.columns else 0.0

    # ── Benchmarks solicitados ────────────────────────────────────
    benchmarks_out = {}
    incluir_cdi = benchmark in ("CDI", "AMBOS")
    incluir_ibov = benchmark in ("IBOV", "AMBOS")

    if incluir_cdi and cdi_subp != 0:
        benchmarks_out["CDI"] = RetornoBenchmark(
            retorno_pct=round(cdi_subp * 100, 4),
            alpha_pct=round((twr_gerida - cdi_subp) * 100, 4),
            ganhando=twr_gerida > cdi_subp,
        )
    elif incluir_cdi:
        benchmarks_out["CDI"] = RetornoBenchmark(
            retorno_pct=0.0, alpha_pct=0.0, ganhando=False
        )

    if incluir_ibov:
        benchmarks_out["IBOV"] = RetornoBenchmark(
            retorno_pct=round(ibov_subp * 100, 4),
            alpha_pct=round((twr_gerida - ibov_subp) * 100, 4),
            ganhando=twr_gerida > ibov_subp,
        )

    resultado = ResultadoPerformance(
        periodo=periodo,
        periodo_efetivo=periodo_efetivo,
        data_inicio=str(data_inicio_real),
        data_fim=str(data_fim_real),
        dias_uteis=dias_uteis,
        twr_gerida_pct=round(twr_gerida * 100, 4),
        benchmarks=benchmarks_out,
        risco=Risco(
            drawdown_max_pct=round(drawdown_max * 100, 4),
            dias_positivos=dias_positivos,
            dias_negativos=dias_negativos,
        ),
    )
    return resultado.model_dump()


# ── TOOL 3 ────────────────────────────────────────────────────────

def fn_obter_cotacao(ticker: str) -> dict:
    """Busca cotação ao vivo via yfinance e cruza com posição na carteira."""
    ticker_original = ticker.upper().strip()
    ticker_yf = _formatar_ticker_yfinance(ticker_original)

    # Verificar cache
    cache_entry = _obter_do_cache(ticker_yf)
    cache_idade = 0

    if cache_entry:
        dados_mercado = cache_entry["dados"]
        cache_idade = int((datetime.now() - cache_entry["timestamp"]).total_seconds() / 60)
    else:
        try:
            import yfinance as yf
            ativo = yf.Ticker(ticker_yf)
            info = ativo.info

            preco = info.get("regularMarketPrice") or info.get("currentPrice")
            if not preco:
                return {
                    "ticker": ticker_original,
                    "ticker_yfinance": ticker_yf,
                    "erro": (
                        f"Ticker '{ticker_original}' não encontrado ou sem cotação disponível. "
                        f"Verifique se é um ativo negociado em bolsa."
                    ),
                }

            preco_anterior = info.get("previousClose") or preco
            variacao = preco - preco_anterior
            variacao_pct = (variacao / preco_anterior * 100) if preco_anterior else 0.0

            dados_mercado = {
                "nome": info.get("longName") or info.get("shortName") or ticker_original,
                "preco_atual": round(float(preco), 2),
                "variacao_dia_pct": round(float(variacao_pct), 2),
                "variacao_dia_reais": round(float(variacao), 2),
                "minimo_52s": round(float(info.get("fiftyTwoWeekLow") or 0), 2),
                "maximo_52s": round(float(info.get("fiftyTwoWeekHigh") or 0), 2),
                "volume_dia": int(info.get("regularMarketVolume") or 0),
                "mercado_aberto": info.get("marketState") == "REGULAR",
            }
            _salvar_no_cache(ticker_yf, dados_mercado)

        except Exception as e:
            return {
                "ticker": ticker_original,
                "ticker_yfinance": ticker_yf,
                "erro": f"Erro ao buscar cotação: {e}",
            }

    # Cruzar com posições da carteira
    posicoes_resultado = fn_obter_posicoes()
    minha_pos = MinhaPosicao(tenho=False)

    if "posicoes" in posicoes_resultado:
        for pos in posicoes_resultado["posicoes"]:
            if pos["ticker"].upper() == ticker_original:
                cm = pos.get("custo_medio")
                preco_atual = dados_mercado["preco_atual"]
                pl_pct = None
                if cm and cm > 0:
                    pl_pct = round((preco_atual - cm) / cm * 100, 2)
                qtd = pos["qtd"]
                minha_pos = MinhaPosicao(
                    tenho=True,
                    qtd=round(qtd, 6),
                    custo_medio=round(cm, 4) if cm else None,
                    valor_atual=round(qtd * preco_atual, 2),
                    pl_pct=pl_pct,
                    pct_carteira=pos["pct_carteira"],
                )
                break

    resultado = ResultadoCotacao(
        ticker=ticker_original,
        ticker_yfinance=ticker_yf,
        nome=dados_mercado["nome"],
        preco_atual=dados_mercado["preco_atual"],
        variacao_dia_pct=dados_mercado["variacao_dia_pct"],
        variacao_dia_reais=dados_mercado["variacao_dia_reais"],
        minimo_52s=dados_mercado["minimo_52s"],
        maximo_52s=dados_mercado["maximo_52s"],
        volume_dia=dados_mercado["volume_dia"],
        mercado_aberto=dados_mercado["mercado_aberto"],
        minha_posicao=minha_pos,
        cache_idade_minutos=cache_idade,
    )
    return resultado.model_dump()


# ── TOOL 4 — DIÁRIO (decisões de investimento) ────────────────────

_PERIODOS_DIARIO = {"7d": 7, "30d": 30, "90d": 90, "all": None}


def fn_obter_diario(
    periodo: str = "30d",
    busca: str | None = None,
    ticker: str | None = None,
) -> dict:
    """Retorna entradas do diário de decisões.

    Mapeamento da tabela `decisoes`:
      data    ← data_decisao
      titulo  ← "{acao} {ativo}" (ex.: "COMPRA WEGE3")
      conteudo ← tese (+ notas, se houver)
    """
    from datetime import date
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.db.models import Decisao

    periodo = (periodo or "30d").lower().strip()
    if periodo not in _PERIODOS_DIARIO:
        return {"erro": f"Período inválido: '{periodo}'. Use: 7d, 30d, 90d, all"}

    dias = _PERIODOS_DIARIO[periodo]
    data_minima = date.today() - timedelta(days=dias) if dias else None

    session = get_session()
    try:
        q = session.query(Decisao).order_by(Decisao.data_decisao.desc())
        if data_minima:
            q = q.filter(Decisao.data_decisao >= data_minima)
        if ticker:
            q = q.filter(Decisao.ativo == ticker.upper().strip())
        decisoes = q.limit(50).all()

        entradas = []
        busca_lower = busca.lower().strip() if busca else None
        for d in decisoes:
            tese = (d.tese or "").strip()
            notas = (d.notas or "").strip()
            conteudo = tese
            if notas:
                conteudo = f"{tese}\n\nNotas: {notas}" if tese else f"Notas: {notas}"

            if busca_lower:
                if (busca_lower not in conteudo.lower()
                        and busca_lower not in (d.ativo or "").lower()):
                    continue

            entradas.append({
                "data": str(d.data_decisao),
                "titulo": f"{d.acao} {d.ativo}",
                "ativo": d.ativo,
                "acao": d.acao,
                "horizonte": d.horizonte,
                "conteudo": conteudo,
                "revisao_em": str(d.revisao_em) if d.revisao_em else None,
                "resultado_revisao": d.resultado_revisao,
            })
            if len(entradas) >= 20:
                break

        return {
            "periodo": periodo,
            "total": len(entradas),
            "entradas": entradas,
        }
    finally:
        session.close()


# ── TOOL 5 — SINAIS TÉCNICOS E FUNDAMENTOS ───────────────────────

def fn_obter_sinais(
    tickers: list[str] | None = None,
    apenas_ativos: bool = False,
) -> dict:
    """Retorna sinais técnicos (RSI/MACD/MM) e fundamentos para ativos da carteira ou lista."""
    from carteira_clean_web.backend.engine.sinais_tecnicos import calcular_sinais_lote
    from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

    if not tickers:
        if not engine_cache.esta_calculado():
            engine_cache.carregar_disco()
        if not engine_cache.esta_calculado():
            return {"erro": "Cache vazio. Recalcule a carteira."}
        estado = engine_cache.get_estado()
        posicoes = estado["posicoes"]
        ativos_meta = estado["ativos"]
        tickers = [
            t for t, p in posicoes.items()
            if ativos_meta.get(t, {}).get("familia", "") in COTIZADO_PUBLICO
            and p.qtd > 1e-9
        ]

    if not tickers:
        return {"erro": "Nenhum ticker encontrado."}

    sinais = calcular_sinais_lote(tickers)

    if apenas_ativos:
        sinais = [s for s in sinais if s.get("tem_sinal_ativo") and not s.get("erro")]

    return {
        "total": len(sinais),
        "apenas_ativos": apenas_ativos,
        "sinais": sinais,
    }


# ── TOOL 6 — FUNDAMENTOS ─────────────────────────────────────────

def fn_obter_fundamentos(tickers: list[str] | None = None) -> dict:
    """Retorna indicadores fundamentalistas (P/L, P/VP, ROE, etc.) da carteira ou lista."""
    from carteira_clean_web.backend.engine.fundamentals_client import fetch_fundamentos
    from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

    if not tickers:
        if not engine_cache.esta_calculado():
            engine_cache.carregar_disco()
        if not engine_cache.esta_calculado():
            return {"erro": "Cache vazio. Recalcule a carteira."}
        estado = engine_cache.get_estado()
        posicoes = estado["posicoes"]
        ativos_meta = estado["ativos"]
        tickers = [
            t for t, p in posicoes.items()
            if ativos_meta.get(t, {}).get("familia", "") in COTIZADO_PUBLICO
            and p.qtd > 1e-9
        ]

    if not tickers:
        return {"erro": "Nenhum ticker encontrado."}

    fundamentos = fetch_fundamentos(tickers)

    return {
        "total": len(fundamentos),
        "fundamentos": fundamentos,
    }


# ── TOOL 6b — CONSULTAR FUNDAMENTOS (do DB) ──────────────────────

def fn_consultar_fundamentos(tickers: list[str] | None = None) -> dict:
    """Retorna os últimos indicadores fundamentalistas persistidos no DB.

    Lê da tabela `fundamentos` (MAX fetched_at por ticker+indicador).
    Para tickers sem dados no DB, faz fallback via live yfinance e persiste.
    """
    from sqlalchemy import func

    from carteira_clean_web.backend.db.models import Fundamento
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.engine.constantes import COTIZADO_PUBLICO

    if not tickers:
        if not engine_cache.esta_calculado():
            engine_cache.carregar_disco()
        if not engine_cache.esta_calculado():
            return {"erro": "Cache vazio. Recalcule a carteira."}
        estado = engine_cache.get_estado()
        tickers = [
            t
            for t, p in estado["posicoes"].items()
            if estado["ativos"].get(t, {}).get("familia", "") in COTIZADO_PUBLICO
            and p.qtd > 1e-9
        ]

    if not tickers:
        return {"erro": "Nenhum ticker encontrado."}

    session = get_session()
    try:
        # Subquery: MAX(fetched_at) por (ticker, indicador)
        subq = (
            session.query(
                Fundamento.ticker,
                Fundamento.indicador,
                func.max(Fundamento.fetched_at).label("max_fa"),
            )
            .filter(Fundamento.ticker.in_(tickers))
            .group_by(Fundamento.ticker, Fundamento.indicador)
            .subquery()
        )
        rows = (
            session.query(Fundamento)
            .join(
                subq,
                (Fundamento.ticker == subq.c.ticker)
                & (Fundamento.indicador == subq.c.indicador)
                & (Fundamento.fetched_at == subq.c.max_fa),
            )
            .all()
        )
    finally:
        session.close()

    # Agrupa por ticker
    por_ticker: dict[str, dict] = {}
    for row in rows:
        t = row.ticker
        if t not in por_ticker:
            por_ticker[t] = {
                "ticker": t,
                "data_referencia": str(row.data_referencia),
                "fetched_at": row.fetched_at.strftime("%Y-%m-%d %H:%M"),
            }
        por_ticker[t][row.indicador] = row.valor

    # Tickers sem dados no DB → fallback live + persiste
    sem_dados = [t for t in tickers if t not in por_ticker]
    if sem_dados:
        from carteira_clean_web.backend.engine.fundamentals_client import salvar_fundamentos_db
        salvar_fundamentos_db(sem_dados)
        # Re-read after save
        session2 = get_session()
        try:
            subq2 = (
                session2.query(
                    Fundamento.ticker,
                    Fundamento.indicador,
                    func.max(Fundamento.fetched_at).label("max_fa"),
                )
                .filter(Fundamento.ticker.in_(sem_dados))
                .group_by(Fundamento.ticker, Fundamento.indicador)
                .subquery()
            )
            rows2 = (
                session2.query(Fundamento)
                .join(
                    subq2,
                    (Fundamento.ticker == subq2.c.ticker)
                    & (Fundamento.indicador == subq2.c.indicador)
                    & (Fundamento.fetched_at == subq2.c.max_fa),
                )
                .all()
            )
            for row in rows2:
                t = row.ticker
                if t not in por_ticker:
                    por_ticker[t] = {
                        "ticker": t,
                        "data_referencia": str(row.data_referencia),
                        "fetched_at": row.fetched_at.strftime("%Y-%m-%d %H:%M"),
                    }
                por_ticker[t][row.indicador] = row.valor
        finally:
            session2.close()

    for t in tickers:
        if t not in por_ticker:
            por_ticker[t] = {"ticker": t, "sem_dados": True}

    return {
        "total": len(tickers),
        "com_dados": sum(1 for v in por_ticker.values() if not v.get("sem_dados")),
        "fundamentos": list(por_ticker.values()),
    }


# ── TOOL 7 — WATCHLIST ────────────────────────────────────────────

def fn_obter_watchlist() -> dict:
    """Retorna a watchlist com cotações ao vivo e distância até o preço-alvo."""
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.db.models import WatchlistItem

    session = get_session()
    try:
        items = (
            session.query(WatchlistItem)
            .filter(WatchlistItem.ativo == 1)
            .order_by(WatchlistItem.id)
            .all()
        )
        if not items:
            return {"total": 0, "itens": []}

        result = []
        for item in items:
            ticker_yf = _formatar_ticker_yfinance(item.ticker)
            cotacao = None
            try:
                import yfinance as yf
                info = yf.Ticker(ticker_yf).info
                preco = info.get("regularMarketPrice") or info.get("currentPrice")
                if preco:
                    cotacao = float(preco)
            except Exception:
                pass

            alvo = item.preco_alvo
            stop = item.stop_loss
            dist_alvo = round((alvo - cotacao) / cotacao * 100, 2) if (cotacao and alvo) else None
            dist_stop = round((cotacao - stop) / stop * 100, 2) if (cotacao and stop) else None

            sinal = "SEM_DADOS"
            if cotacao and alvo:
                diff = (alvo - cotacao) / cotacao * 100
                sinal = "ACIMA" if diff <= 0 else ("PROXIMO" if diff <= 3 else "NA_ZONA")

            result.append({
                "ticker": item.ticker,
                "preco_alvo": alvo,
                "stop_loss": stop,
                "motivo": item.motivo,
                "data_adicao": str(item.data_adicao),
                "cotacao_atual": round(cotacao, 2) if cotacao else None,
                "distancia_alvo_pct": dist_alvo,
                "distancia_stop_pct": dist_stop,
                "sinal": sinal,
            })

        return {"total": len(result), "itens": result}
    finally:
        session.close()


# ── TOOL 8 — ANÁLISE COMPLETA RV ─────────────────────────────────

def fn_obter_analise_rv() -> dict:
    """Análise completa da carteira RV: posições + sinais técnicos + fundamentos + watchlist.
    Chamadas em paralelo para minimizar latência."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_pos = ex.submit(fn_obter_posicoes)
        fut_sinais = ex.submit(fn_obter_sinais)
        fut_watch = ex.submit(fn_obter_watchlist)
        posicoes_result = fut_pos.result()
        sinais_result = fut_sinais.result()
        watchlist_result = fut_watch.result()

    rv_posicoes = [
        p for p in posicoes_result.get("posicoes", [])
        if p.get("classe") == "Renda Variável"
    ] if "posicoes" in posicoes_result else []

    sinais_map = {s["ticker"]: s for s in sinais_result.get("sinais", [])}

    ativos_rv = []
    for pos in rv_posicoes:
        t = pos["ticker"]
        s = sinais_map.get(t, {})
        ativos_rv.append({
            "ticker": t,
            "valor_atual": pos["valor_atual"],
            "pct_carteira": pos["pct_carteira"],
            "pl_pct": pos.get("pl_percentual"),
            "sinal_combinado": s.get("combinado", {}).get("label"),
            "rsi": s.get("rsi"),
            "rsi_sinal": s.get("rsi_sinal"),
            "macd_sinal": s.get("macd_sinal"),
            "mm_sinal": s.get("mm_sinal"),
            "fund": s.get("fund", {}),
        })

    return {
        "data_referencia": posicoes_result.get("data_referencia"),
        "patrimonio_total": posicoes_result.get("patrimonio_total"),
        "total_rv": len(ativos_rv),
        "ativos_rv": ativos_rv,
        "watchlist": watchlist_result.get("itens", []),
        "alertas": posicoes_result.get("alertas", []),
    }


# ── TOOL 9 — ATRIBUIÇÃO MENSAL ───────────────────────────────────

def fn_brinson(
    mes: str | None = None,
    bloco_ips: str | None = None,
) -> dict:
    """Retorna decomposição Brinson-Fachler por bloco IPS.

    Parâmetros opcionais:
      - mes: "YYYY-MM". Sem filtro → todos os meses.
      - bloco_ips: "SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA" ou "TOTAL".

    Cada linha inclui:
      - w_real, w_alvo (pesos real e IPS em %)
      - R_real_bloco, R_bench_bloco, R_bench_total (retornos em %)
      - efeito_alocacao, efeito_selecao (em pp)
    Linha TOTAL por mês resume o excesso de retorno vs benchmark composto IPS.
    """
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Recalcule a carteira antes de usar o assistente."}

    estado = engine_cache.get_estado()
    df = estado.get("df_bf")
    if df is None or df.empty:
        return {"erro": "Sem dados Brinson-Fachler. Recalcule a carteira."}

    if mes:
        df = df[df["mes"] == mes]
    if bloco_ips:
        df = df[df["bloco_ips"] == bloco_ips]

    if df.empty:
        return {"total": 0, "brinson": [], "totais": []}

    rows = []
    for row in df.itertuples(index=False):
        rows.append({
            "mes":              row.mes,
            "bloco_ips":        row.bloco_ips,
            "w_real_pct":       round(row.w_real * 100, 1),
            "w_alvo_pct":       round(row.w_alvo * 100, 1),
            "desvio_pct":       round((row.w_real - row.w_alvo) * 100, 1),
            "R_real_pct":       round(row.R_real_bloco * 100, 2),
            "R_bench_bloco_pct": round(row.R_bench_bloco * 100, 2),
            "R_bench_total_pct": round(row.R_bench_total * 100, 2),
            "efeito_alocacao_pp": round(row.efeito_alocacao * 100, 3),
            "efeito_selecao_pp":  round(row.efeito_selecao * 100, 3),
            "excesso_total_pp":   round((row.efeito_alocacao + row.efeito_selecao) * 100, 3),
        })

    totais = [r for r in rows if r["bloco_ips"] == "TOTAL"]
    blocos  = [r for r in rows if r["bloco_ips"] != "TOTAL"]
    meses_disp = sorted(df["mes"].unique().tolist())

    return {
        "total": len(rows),
        "meses_disponiveis": meses_disp,
        "totais": totais,
        "brinson": blocos,
    }


def fn_atribuicao(
    mes: str | None = None,
    composite: str | None = None,
    bloco_ips: str | None = None,
) -> dict:
    """Retorna atribuição mensal: quais ativos contribuíram para a performance.

    Parâmetros opcionais:
      - mes: "YYYY-MM" (ex: "2026-05"). Sem filtro → todos os meses.
      - composite: "Gerida", "FUNCEF" ou "TOTAL_CARTEIRA".
      - bloco_ips: "SWING_TRADE", "GROWTH", "RENDA_FIXA", "DEFENSIVOS" ou "FORA_IPS".

    Inclui linhas TOTAL por (mes, composite) e TOTAL_CARTEIRA por mes.
    """
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Recalcule a carteira antes de usar o assistente."}

    estado = engine_cache.get_estado()
    df = estado.get("df_atrib")
    if df is None or df.empty:
        return {"erro": "Sem dados de atribuição. Recalcule a carteira."}

    if mes:
        df = df[df["mes"] == mes]
    if composite:
        df = df[df["composite"] == composite]
    if bloco_ips:
        df = df[df["bloco_ips"].fillna("") == bloco_ips]

    if df.empty:
        return {"total": 0, "atribuicao": [], "resumo_totais": []}

    rows = []
    for row in df.itertuples(index=False):
        rows.append({
            "mes": row.mes,
            "composite": row.composite,
            "ativo": row.ativo,
            "retorno_pct": round(row.retorno_ativo * 100, 2),
            "peso_pct": round(row.peso_medio * 100, 1),
            "contribuicao_pp": round(row.contribuicao * 100, 2),
            "benchmark": getattr(row, "benchmark", None),
            "bloco_ips": getattr(row, "bloco_ips", None),
        })

    totais = [r for r in rows if r["ativo"] == "TOTAL"]
    individuais = [r for r in rows if r["ativo"] != "TOTAL"]
    meses_disp = sorted(df["mes"].unique().tolist())

    return {
        "total": len(rows),
        "meses_disponiveis": meses_disp,
        "resumo_totais": totais,
        "atribuicao": individuais,
    }


# ── TOOL 10 — ADERÊNCIA SETORIAL (Fatia 1) ───────────────────────────────────

def _retorno_recente_idx(serie: dict, dias_corridos: int = 30) -> dict | None:
    """Retorno de uma série {date: valor} nos últimos N dias corridos.

    Busca a data mais próxima <= hoje - N dias como base; retorna None se a
    série tiver menos de 2 pontos ou o valor base for zero.
    """
    if len(serie) < 2:
        return None
    datas = sorted(serie.keys())
    data_fim = datas[-1]
    data_ini_alvo = data_fim - timedelta(days=dias_corridos)
    candidatos = [d for d in datas if d <= data_ini_alvo]
    data_ini = candidatos[-1] if candidatos else datas[0]
    v_ini = serie[data_ini]
    v_fim = serie[data_fim]
    if v_ini <= 0:
        return None
    return {
        "retorno_pct": round((v_fim / v_ini - 1) * 100, 2),
        "data_ini": str(data_ini),
        "data_fim": str(data_fim),
        "fonte": "tabela benchmarks (IDX_*)",
    }


def fn_analise_aderencia_setorial() -> dict:
    """Cruza exposição setorial real vs. IPS com desempenho recente dos índices B3.

    Peça A (janela externa): índices setoriais B3 lidos da tabela benchmarks
                             via carregar_indices_setoriais_da_tabela().
    Peça B (espelho interno): concentração setorial calculada por
                              calc_concentracao_setorial() a partir do cache.

    Todo número na observação é rastreável a Peça A ou Peça B — nada estimado.
    """
    from carteira_clean_web.backend.engine.aderencia_ips import calc_concentracao_setorial
    from carteira_clean_web.backend.engine.precos import carregar_indices_setoriais_da_tabela

    # ── Cache ──────────────────────────────────────────────────────────────────
    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos        = estado["ativos"]
    precos_pub    = estado.get("precos_publicos", {})
    precos_man    = estado.get("precos_manuais", {})
    hoje          = estado["hoje"]

    # bloco_ips pode não estar no cache se o pickle é anterior à migração 0002.
    # Lê diretamente do banco (campo estático, padrão já usado em fn_obter_diario).
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.db.models import Ativo as AtivoModel
    _session = get_session()
    try:
        bloco_ips_db = {
            row.ticker: row.bloco_ips
            for row in _session.query(AtivoModel.ticker, AtivoModel.bloco_ips).all()
        }
    finally:
        _session.close()

    # ── Montar posicoes_raw com valor_atual (Fonte B) ──────────────────────────
    posicoes_raw: list[dict] = []
    for tkr, p in posicoes_dict.items():
        info    = ativos.get(tkr, {})
        familia = info.get("familia", "")
        if p.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue

        valor_atual = valorizar_posicao(p, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]

        posicoes_raw.append({
            "composite":   info.get("composite", "Gerida"),
            "bloco_ips":   bloco_ips_db.get(tkr) or "FORA_IPS",
            "setor":       info.get("setor") or "—",
            "valor_atual": valor_atual,
        })

    # ── Peça B: concentração setorial vs. IPS ─────────────────────────────────
    blocos = calc_concentracao_setorial(posicoes_raw)
    if not blocos:
        return {"erro": "Sem posições Gerida com bloco IPS definido. Recalcule a carteira."}

    patrimonio_gerida = sum(
        p["valor_atual"] for p in posicoes_raw
        if p["composite"] == "Gerida" and p["valor_atual"] > 0
    )

    # ── Peça A: desempenho recente dos índices B3 ──────────────────────────────
    indices_tabela   = carregar_indices_setoriais_da_tabela()
    indices_recentes = {nome: _retorno_recente_idx(serie) for nome, serie in indices_tabela.items()}

    # ── Cruzar A + B → observação textual ─────────────────────────────────────
    secoes: list[str] = []
    for b in blocos:
        bloco  = b["bloco_ips"]
        status = b["status"]
        w_real = b["w_real_pct"]
        w_alvo = b["w_alvo_pct"]
        b_inf  = b["banda_inf_pct"]
        b_sup  = b["banda_sup_pct"]
        desvio = b["desvio_pp"]

        if status == "fora_superior":
            cabec = (f"[FORA BANDA ↑] {bloco}: {w_real}% real / alvo {w_alvo}% "
                     f"/ banda {b_inf}%–{b_sup}% ({desvio:+.1f}pp)")
        elif status == "fora_inferior":
            cabec = (f"[FORA BANDA ↓] {bloco}: {w_real}% real / alvo {w_alvo}% "
                     f"/ banda {b_inf}%–{b_sup}% ({desvio:+.1f}pp)")
        else:
            cabec = (f"[DENTRO] {bloco}: {w_real}% real / alvo {w_alvo}% "
                     f"/ banda {b_inf}%–{b_sup}% ({desvio:+.1f}pp)")

        linhas_set: list[str] = []
        for s in b["setores"][:3]:
            idx = s["indice_referencia"]
            ir  = indices_recentes.get(idx) if idx else None
            trecho = f"  • {s['setor']}: {s['w_bloco_pct']}% do bloco"
            if ir:
                trecho += f" | {idx.replace('IDX_', '')} {ir['retorno_pct']:+.2f}% (1m)"
            elif idx:
                trecho += f" | {idx.replace('IDX_', '')} sem dados ainda"
            linhas_set.append(trecho)

        secoes.append(cabec + ("\n" + "\n".join(linhas_set) if linhas_set else ""))

    return {
        "data_referencia":      str(hoje),
        "patrimonio_gerida_rs": round(patrimonio_gerida, 2),
        "observacao":           "\n\n".join(secoes),
        "blocos":               blocos,           # Peça B — rastreável ao cache
        "indices_recentes":     indices_recentes, # Peça A — rastreável à tabela benchmarks
        "rastreabilidade": {
            "fonte_A": "tabela benchmarks, nomes IDX_*, carregar_indices_setoriais_da_tabela()",
            "fonte_B": "engine cache, posicoes + ativos, calc_concentracao_setorial()",
            "anti_alucinacao": "todo número na observacao deriva de fonte_A ou fonte_B",
        },
    }


# ── TOOL 11 — CONSULTAR TESES (Fatia 4) ──────────────────────────

def fn_consultar_teses(ticker: str | None = None) -> dict:
    """Retorna teses de investimento ativas (ou de um ticker específico)."""
    from carteira_clean_web.backend.db.models import Tese
    from carteira_clean_web.backend.db.session import get_session

    session = get_session()
    try:
        q = session.query(Tese).order_by(Tese.data_criacao.desc())
        if ticker:
            q = q.filter(Tese.ticker == ticker.upper())
        else:
            q = q.filter(Tese.status == "ATIVA")
        teses = q.all()
        from datetime import date
        hoje = date.today()
        itens = []
        for t in teses:
            dias = (hoje - t.data_criacao).days if t.data_criacao else None
            itens.append({
                **t.to_dict(),
                "dias_desde_criacao": dias,
            })
        return {"total": len(itens), "teses": itens}
    finally:
        session.close()


# ── TOOL 12 — CONSULTAR DIÁRIO DE DECISÕES (Fatia 5) ─────────────

def fn_consultar_diario_decisoes(
    ticker: str | None = None,
    periodo: str = "90d",
) -> dict:
    """Retorna entradas do diário de decisão estruturado.

    resultado_percentual é calculado dinamicamente (preco_entrada vs cotação atual).
    """
    from datetime import date, timedelta

    from carteira_clean_web.backend.db.models import DiarioDecisao
    from carteira_clean_web.backend.db.session import get_session

    _periodos = {"7d": 7, "30d": 30, "90d": 90, "all": None}
    dias = _periodos.get(periodo, 90)
    data_min = date.today() - timedelta(days=dias) if dias else None

    session = get_session()
    try:
        q = session.query(DiarioDecisao).order_by(DiarioDecisao.data_decisao.desc())
        if ticker:
            q = q.filter(DiarioDecisao.ticker == ticker.upper())
        if data_min:
            q = q.filter(DiarioDecisao.data_decisao >= data_min)
        entradas = q.limit(50).all()

        # Calcular resultado_percentual dinamicamente
        from carteira_clean_web.backend.api import cache as ec
        if not ec.esta_calculado():
            ec.carregar_disco()
        precos_pub = {}
        precos_man = {}
        hoje_dt = date.today()
        if ec.esta_calculado():
            est = ec.get_estado()
            precos_pub = est.get("precos_publicos", {})
            precos_man = est.get("precos_manuais", {})
            hoje_dt = est.get("hoje", hoje_dt)

        itens = []
        for e in entradas:
            d = e.to_dict()
            if e.preco_entrada:
                preco_atual = (
                    preco_em(precos_pub.get(e.ticker, {}), hoje_dt)
                    or preco_em(precos_man.get(e.ticker, {}), hoje_dt, max_lookback_dias=60)
                )
                if preco_atual:
                    d["resultado_percentual"] = round(
                        (preco_atual - e.preco_entrada) / e.preco_entrada * 100, 2
                    )
                    d["preco_atual"] = round(preco_atual, 2)
            itens.append(d)
        return {"total": len(itens), "entradas": itens}
    finally:
        session.close()


# ── TOOL 13 — RISCO EX-ANTE (Fatia 6) ───────────────────────────

def fn_risco_carteira(tipo: str = "todos") -> dict:
    """Risco ex-ante: exposição por fator, drawdown, liquidez e stress."""
    import math
    import numpy as np

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Recalcule a carteira."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    # Patrimônio e valores por ativo (Gerida apenas)
    valores: dict[str, float] = {}
    for tkr, pos in posicoes_dict.items():
        info = ativos.get(tkr, {})
        if info.get("composite") != "Gerida":
            continue
        familia = info.get("familia", "")
        if pos.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue
        valores[tkr] = valorizar_posicao(pos, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]

    patrimonio_gerida = sum(valores.values()) or 1.0

    result: dict = {"patrimonio_gerida": round(patrimonio_gerida, 2)}

    # ── EXPOSIÇÃO ────────────────────────────────────────────────
    if tipo in ("exposicao", "todos"):
        # Bloco IPS
        por_bloco: dict[str, float] = {}
        for tkr, val in valores.items():
            bloco = ativos.get(tkr, {}).get("bloco_ips") or "FORA_IPS"
            por_bloco[bloco] = por_bloco.get(bloco, 0.0) + val

        # Moeda
        usd_familias = {"BDR", "BDR de ETF"}
        val_usd = sum(v for t, v in valores.items()
                      if ativos.get(t, {}).get("familia") in usd_familias)
        val_brl = patrimonio_gerida - val_usd

        # Classe
        por_classe: dict[str, float] = {}
        for tkr, val in valores.items():
            cls = ativos.get(tkr, {}).get("classe") or "Outros"
            por_classe[cls] = por_classe.get(cls, 0.0) + val

        result["exposicao"] = {
            "bloco_ips": {
                b: {"valor": round(v, 2), "pct": round(v / patrimonio_gerida * 100, 1)}
                for b, v in sorted(por_bloco.items(), key=lambda x: -x[1])
            },
            "moeda": {
                "BRL": {"valor": round(val_brl, 2), "pct": round(val_brl / patrimonio_gerida * 100, 1)},
                "USD": {"valor": round(val_usd, 2), "pct": round(val_usd / patrimonio_gerida * 100, 1)},
            },
            "classe": {
                c: {"valor": round(v, 2), "pct": round(v / patrimonio_gerida * 100, 1)}
                for c, v in sorted(por_classe.items(), key=lambda x: -x[1])
            },
        }

    # ── DRAWDOWN ─────────────────────────────────────────────────
    if tipo in ("drawdown", "todos") and not df_evo.empty:
        import pandas as pd
        df = df_evo.copy()
        df["ano"] = pd.to_datetime(df["data"]).dt.year
        ano_atual = pd.to_datetime(str(hoje)).year

        mdd_ytd = float(df[df["ano"] == ano_atual]["drawdown"].min()) if not df[df["ano"] == ano_atual].empty else 0.0
        mdd_12m = float(df.tail(252)["drawdown"].min())
        mdd_total = float(df["drawdown"].min())

        # Duração aproximada: dias entre último pico (drawdown=0) antes do maior vale
        dd_series = df["drawdown"].values
        idx_min = int(np.argmin(dd_series))
        # Pico antes do mínimo
        pico_idx = next(
            (i for i in range(idx_min - 1, -1, -1) if dd_series[i] >= -0.001),
            0,
        )
        # Recuperação após o mínimo (próximo valor >= 0)
        rec_idx = next(
            (i for i in range(idx_min + 1, len(dd_series)) if dd_series[i] >= -0.001),
            len(dd_series) - 1,
        )
        dur_queda = idx_min - pico_idx
        dur_recuperacao = rec_idx - idx_min if rec_idx < len(dd_series) - 1 else None

        result["drawdown"] = {
            "mdd_ytd_pct": round(mdd_ytd * 100, 2),
            "mdd_12m_pct": round(mdd_12m * 100, 2),
            "mdd_desde_inicio_pct": round(mdd_total * 100, 2),
            "maior_queda_duracao_dias": dur_queda,
            "recuperacao_dias": dur_recuperacao,
        }

    # ── LIQUIDEZ ─────────────────────────────────────────────────
    if tipo in ("liquidez", "todos"):
        mapa_liq = {"Alta": "D+0", "Média": "D+3", "Baixa": "D+30"}
        por_liq: dict[str, float] = {"D+0": 0.0, "D+3": 0.0, "D+30": 0.0, "D+30+": 0.0}
        for tkr, val in valores.items():
            liq_raw = ativos.get(tkr, {}).get("liquidez")
            bucket = mapa_liq.get(liq_raw, "D+30+")
            por_liq[bucket] = por_liq.get(bucket, 0.0) + val

        cum_d3 = por_liq["D+0"] + por_liq["D+3"]
        alerta = cum_d3 / patrimonio_gerida * 100 < 20

        result["liquidez"] = {
            "por_bucket": {
                k: {"valor": round(v, 2), "pct": round(v / patrimonio_gerida * 100, 1)}
                for k, v in por_liq.items()
            },
            "disponivel_ate_d3_pct": round(cum_d3 / patrimonio_gerida * 100, 1),
            "alerta_liquidez_baixa": alerta,
        }

    # ── CENÁRIOS DE STRESS ────────────────────────────────────────
    if tipo in ("stress", "todos") and not df_evo.empty:
        # Beta implícito (regressão 60 dias)
        try:
            df_r = df_evo.tail(62).copy()
            df_r["ret_port"] = df_r["twr_gerida"].diff() / (1 + df_r["twr_gerida"].shift(1))
            df_r["ret_ibov"] = df_r["ibov_acum"].diff() / (1 + df_r["ibov_acum"].shift(1))
            df_r = df_r.dropna(subset=["ret_port", "ret_ibov"]).tail(60)
            if len(df_r) >= 20:
                cov = np.cov(df_r["ret_port"], df_r["ret_ibov"])
                beta = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] != 0 else 0.8
                beta = max(-2.0, min(3.0, beta))  # cap razoável
            else:
                beta = 0.8
        except Exception:
            beta = 0.8

        # Pesos para stress
        usd_familias = {"BDR", "BDR de ETF"}
        peso_usd = sum(v for t, v in valores.items()
                       if ativos.get(t, {}).get("familia") in usd_familias) / patrimonio_gerida
        peso_rv_brl = sum(v for t, v in valores.items()
                          if ativos.get(t, {}).get("classe") == "Renda Variável"
                          and ativos.get(t, {}).get("familia") == "Ação BR") / patrimonio_gerida
        peso_rf_pos = sum(v for t, v in valores.items()
                          if ativos.get(t, {}).get("indexador") in ("CDI", "SELIC")) / patrimonio_gerida
        peso_rf_pre = sum(v for t, v in valores.items()
                          if ativos.get(t, {}).get("indexador") in ("IPCA", "Prefixado")) / patrimonio_gerida

        impacto_ibov = beta * (-0.20) * (1 - peso_usd)
        impacto_usd = peso_usd * 0.30
        impacto_selic_pos = peso_rf_pos * 0.01  # +1% retorno pós-fixados
        impacto_selic_pre = peso_rf_pre * (-0.05)  # aprox -5% mark-to-market duração média

        result["stress"] = {
            "beta_implicito": round(beta, 2),
            "cenarios": {
                "IBOV_menos_20pct": {
                    "descricao": "IBOV cai 20%",
                    "impacto_estimado_pct": round(impacto_ibov * 100, 1),
                    "impacto_rs": round(impacto_ibov * patrimonio_gerida, 2),
                },
                "USD_mais_30pct": {
                    "descricao": "USD sobe 30% (BDRs sobem 30%)",
                    "impacto_estimado_pct": round(impacto_usd * 100, 1),
                    "impacto_rs": round(impacto_usd * patrimonio_gerida, 2),
                },
                "Selic_mais_300bps": {
                    "descricao": "Selic sobe 3pp (pós-fixados +, prefixados/IPCA+ -)",
                    "impacto_pos_fixados_pct": round(impacto_selic_pos * 100, 1),
                    "impacto_pre_ipca_pct": round(impacto_selic_pre * 100, 1),
                    "impacto_liquido_pct": round((impacto_selic_pos + impacto_selic_pre) * 100, 1),
                },
            },
            "nota": "Aproximações de ordem de grandeza. Beta calculado via regressão 60 dias.",
        }

    return result


# ── TOOL 14 — DISCIPLINA DE CAIXA (Fatia 7) ─────────────────────

def fn_disciplina_caixa() -> dict:
    """Monitoramento de caixa e aderência ao plano de aportes."""
    from datetime import date

    from carteira_clean_web.backend.db.models import Evento, RegraAporte
    from carteira_clean_web.backend.db.session import get_session

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Recalcule a carteira."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]
    df_evo = estado["df_evo"]

    # Patrimônio gerido
    patrimonio_gerida = float(df_evo.iloc[-1]["patrimonio_gerida"]) if not df_evo.empty else 0.0

    # Caixa: ativos com setor "Caixa/Conservador"
    caixa_val = 0.0
    for tkr, pos in posicoes_dict.items():
        info = ativos.get(tkr, {})
        if info.get("composite") != "Gerida":
            continue
        if info.get("setor", "").lower() not in ("caixa/conservador", "caixa"):
            continue
        familia = info.get("familia", "")
        if pos.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue
        caixa_val += valorizar_posicao(pos, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]

    caixa_pct = caixa_val / patrimonio_gerida * 100 if patrimonio_gerida > 0 else 0.0
    limiar_pct = 15.0

    # Dias acima do limiar (usando histórico df_evo como proxy de caixa — aproximação)
    dias_acima = 0
    if not df_evo.empty and "patrimonio_rv" in df_evo.columns:
        for _, row in df_evo.iterrows():
            pat = row["patrimonio_gerida"]
            pat_rv = row.get("patrimonio_rv", 0.0)
            if pat > 0:
                caixa_hist_pct = (pat - pat_rv) / pat * 100
                if caixa_hist_pct > limiar_pct:
                    dias_acima += 1

    # Status
    if caixa_pct <= limiar_pct:
        status_caixa = "SAUDAVEL"
    elif dias_acima <= 42:  # 6 semanas
        status_caixa = "ELEVADO_TEMPORARIO"
    else:
        status_caixa = "REQUER_REVISAO"

    # Aporte do mês corrente
    session = get_session()
    try:
        mes_ini = hoje.replace(day=1)
        aportes_mes = session.query(Evento).filter(
            Evento.tipo.in_(("APORTE_EXTERNO", "CONTRIBUICAO", "APORTE")),
            Evento.data >= mes_ini,
            Evento.data <= hoje,
        ).all()
        total_aporte_mes = sum(e.valor or 0 for e in aportes_mes)

        # Regra ativa
        regra = session.query(RegraAporte).filter(RegraAporte.ativo == 1).first()
        regra_dict = regra.to_dict() if regra else None
        alvo_mes = regra.valor_mensal_alvo if regra else None
    finally:
        session.close()

    return {
        "caixa_atual_rs": round(caixa_val, 2),
        "caixa_pct": round(caixa_pct, 1),
        "limiar_alerta_pct": limiar_pct,
        "dias_acima_do_limiar": dias_acima,
        "status": status_caixa,
        "aporte_mes_atual_rs": round(total_aporte_mes, 2),
        "alvo_mensal_rs": alvo_mes,
        "aderencia_aporte": (
            round(total_aporte_mes / alvo_mes * 100, 1) if alvo_mes else None
        ),
        "regra_ativa": regra_dict,
        "patrimonio_gerida": round(patrimonio_gerida, 2),
    }


# ─── Fatia 3: Macro e eventos corporativos ───────────────────────────────────

def fn_consultar_macro(
    indicadores: list[str] | None = None,
    ultimos_n: int = 12,
) -> dict:
    """
    Retorna os últimos pontos de cada indicador macro persistido.

    Indicadores disponíveis:
      SELIC_META   — Taxa Selic meta (% a.a.), BCB SGS 432
      SELIC_DIARIA — CDI / Selic over diária (% a.d.), BCB SGS 12
      IPCA         — Inflação mensal (% a.m.), BCB SGS 433
      USD_BRL      — Câmbio USD/BRL PTAX venda, BCB SGS 1
      IPCA_FOCUS   — Expectativa mediana IPCA anual (Focus), BCB Olinda

    Args:
        indicadores: lista de indicadores ou None (retorna todos)
        ultimos_n: quantas observações retornar por indicador (default 12)
    """
    try:
        from carteira_clean_web.backend.engine.macro_client import ler_macro
        dados = ler_macro(indicadores=indicadores, ultimos_n=ultimos_n)
    except Exception as e:
        return {"erro": str(e), "dados": {}}

    resumo = {}
    for ind, pontos in dados.items():
        if not pontos:
            resumo[ind] = {"ultimo": None, "data": None, "historico": []}
            continue
        mais_recente = pontos[0]
        resumo[ind] = {
            "ultimo": mais_recente["valor"],
            "data": mais_recente["data"],
            "historico": pontos,
        }

    return {
        "indicadores": resumo,
        "total_pontos": sum(len(v["historico"]) for v in resumo.values()),
        "nota": (
            "Dados persistidos via BCB SGS + Olinda (Focus). "
            "Para coletar dados mais recentes: POST /api/v1/macro/coletar"
        ),
    }


def fn_consultar_eventos_corporativos(
    ticker: str | None = None,
    janela_dias: int = 60,
) -> dict:
    """
    Retorna eventos corporativos futuros (earnings, ex-dividend) dos ativos em carteira.

    Args:
        ticker: filtrar por ativo específico (ex: "WEGE3"). None = todos.
        janela_dias: horizonte em dias (default 60)
    """
    try:
        from carteira_clean_web.backend.engine.macro_client import ler_eventos_corporativos
        eventos = ler_eventos_corporativos(ticker=ticker, janela_dias=janela_dias)
    except Exception as e:
        return {"erro": str(e), "eventos": []}

    por_ticker: dict[str, list] = {}
    for ev in eventos:
        t = ev["ticker"]
        por_ticker.setdefault(t, []).append(ev)

    return {
        "eventos": eventos,
        "por_ticker": por_ticker,
        "total": len(eventos),
        "janela_dias": janela_dias,
        "nota": (
            "Fonte: yfinance (earnings_date, ex_dividend_date). "
            "Para coletar dados mais recentes: POST /api/v1/macro/coletar-eventos"
        ),
    }


# ─── Fatia 8: Perfil comportamental ──────────────────────────────────────────

def fn_perfil_comportamental(
    metrica: str = "todos",
    periodo_meses: int = 12,
) -> dict:
    """
    Perfil comportamental calculado sobre o event log.
    Métricas disponíveis: turnover, holding, frequencia, concentracao.
    Não interpreta — apenas computa fatos.

    Args:
        metrica:        "turnover" | "holding" | "frequencia" | "concentracao" | "todos"
        periodo_meses:  janela de análise em meses (default 12)
    """
    from datetime import date, timedelta
    from carteira_clean_web.backend.db.models import Evento as EventoModel, Ativo as AtivoModel
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.engine.comportamento import (
        calcular_turnover, calcular_holding_period,
        calcular_frequencia, calcular_concentracao,
    )
    from carteira_clean_web.backend.engine.aderencia_ips import _BLOCO_MAP

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})
    hoje = estado["hoje"]

    periodo_fim = hoje
    periodo_ini = date(
        hoje.year - ((periodo_meses - 1 + (12 - hoje.month)) // 12),
        ((hoje.month - periodo_meses - 1) % 12) + 1,
        1
    ) if periodo_meses >= 12 else date(
        hoje.year if hoje.month > periodo_meses else hoje.year - 1,
        ((hoje.month - periodo_meses - 1) % 12) + 1,
        1,
    )
    # Simpler: subtract months directly
    m = hoje.month - periodo_meses
    y = hoje.year
    while m <= 0:
        m += 12
        y -= 1
    periodo_ini = date(y, m, 1)

    session = get_session()
    try:
        eventos_db = session.query(EventoModel).filter(
            EventoModel.data >= periodo_ini,
        ).order_by(EventoModel.data).all()
        eventos_dicts = [e.to_dict() for e in eventos_db]

        # Para holding: precisamos de todo o histórico (compras antes do período)
        eventos_todos = session.query(EventoModel).order_by(EventoModel.data).all()
        eventos_todos_dicts = [e.to_dict() for e in eventos_todos]

        bloco_ips_db = {
            row.ticker: row.bloco_ips
            for row in session.query(AtivoModel.ticker, AtivoModel.bloco_ips).all()
        }
    finally:
        session.close()

    # Montar valor_por_ticker e composite_por_ticker a partir do cache
    valor_por_ticker: dict[str, float] = {}
    composite_por_ticker: dict[str, str] = {}
    valor_por_bloco: dict[str, float] = defaultdict(float)

    for tkr, pos in posicoes_dict.items():
        info = ativos.get(tkr, {})
        familia = info.get("familia", "")
        if pos.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
            continue
        val = valorizar_posicao(pos, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]
        valor_por_ticker[tkr] = val
        composite_por_ticker[tkr] = info.get("composite", "Gerida")

        bloco = _BLOCO_MAP.get(tkr) or bloco_ips_db.get(tkr) or "FORA_IPS"
        if info.get("composite", "Gerida") == "Gerida":
            valor_por_bloco[bloco] += val

    resultado: dict = {
        "periodo": f"{periodo_ini} a {periodo_fim}",
        "periodo_meses": periodo_meses,
        "calculado_em": str(hoje),
    }

    metricas_req = {"turnover", "holding", "frequencia", "concentracao"} \
        if metrica == "todos" else {metrica}

    if "turnover" in metricas_req:
        resultado["turnover"] = calcular_turnover(
            eventos_dicts, dict(valor_por_bloco), periodo_ini, periodo_fim,
        )

    if "holding" in metricas_req:
        resultado["holding"] = calcular_holding_period(eventos_todos_dicts, hoje)

    if "frequencia" in metricas_req:
        resultado["frequencia"] = calcular_frequencia(eventos_dicts, periodo_ini, periodo_fim)

    if "concentracao" in metricas_req:
        resultado["concentracao"] = calcular_concentracao(
            valor_por_ticker, composite_por_ticker,
        )

    return resultado


# ─── Fatia 9: Dito vs feito ──────────────────────────────────────────────────

def fn_divergencias_dito_feito(
    tipo: str = "todos",
    periodo_meses: int = 6,
) -> dict:
    """
    Cruzamento dito-vs-feito: compara declarações (IPS, teses, diário)
    com comportamento real (Fatia 8). Retorna fatos — sem recomendações.

    Args:
        tipo:           "horizonte" | "alocacao" | "conviccao" | "invalidacao" | "todos"
        periodo_meses:  janela para padrões comportamentais (default 6 meses)
    """
    from datetime import date
    from carteira_clean_web.backend.db.models import (
        Tese, DiarioDecisao, Ativo as AtivoModel,
    )
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.engine.dito_vs_feito import (
        cruzar_horizonte_holding,
        cruzar_alocacao_ips,
        cruzar_conviccao_resultado,
        cruzar_invalidacao_teses,
    )
    from carteira_clean_web.backend.engine.aderencia_ips import calc_concentracao_setorial, _BLOCO_MAP

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    hoje = engine_cache.get_estado()["hoje"]

    tipos_req = {"horizonte", "alocacao", "conviccao", "invalidacao"} \
        if tipo == "todos" else {tipo}

    divergencias: list[dict] = []

    # ── Dados comuns ────────────────────────────────────────────────────────
    perfil = fn_perfil_comportamental(metrica="todos", periodo_meses=periodo_meses)
    if "erro" in perfil:
        return perfil

    session = get_session()
    try:
        teses_db = session.query(Tese).all()
        teses = [t.to_dict() for t in teses_db]

        decisoes_db = session.query(DiarioDecisao).all()
        decisoes = [d.to_dict() for d in decisoes_db]

        bloco_ips_db = {
            row.ticker: row.bloco_ips
            for row in session.query(AtivoModel.ticker, AtivoModel.bloco_ips).all()
        }
    finally:
        session.close()

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    precos_man = estado.get("precos_manuais", {})

    # ── Cruzamento 1: horizonte vs holding period ──────────────────────────
    if "horizonte" in tipos_req and "holding" in perfil:
        divs = cruzar_horizonte_holding(perfil["holding"])
        divergencias.extend(divs)

    # ── Cruzamento 2: alocação declarada vs real ───────────────────────────
    if "alocacao" in tipos_req:
        posicoes_raw = []
        for tkr, pos in posicoes_dict.items():
            info = ativos.get(tkr, {})
            familia = info.get("familia", "")
            if pos.qtd < 1e-9 and familia not in AGREGADO_PRIVADO:
                continue
            val = valorizar_posicao(pos, tkr, ativos, precos_pub, precos_man, hoje)["valor_atual"]
            bloco = _BLOCO_MAP.get(tkr) or bloco_ips_db.get(tkr) or "FORA_IPS"
            posicoes_raw.append({
                "composite": info.get("composite", "Gerida"),
                "bloco_ips": bloco,
                "setor": info.get("setor") or "—",
                "valor_atual": val,
            })
        blocos_ips = calc_concentracao_setorial(posicoes_raw)
        divs = cruzar_alocacao_ips(blocos_ips)
        divergencias.extend(divs)

    # ── Cruzamento 3: convicção vs resultado ───────────────────────────────
    if "conviccao" in tipos_req and decisoes:
        preco_atual: dict[str, float] = {}
        for tkr, pos in posicoes_dict.items():
            info = ativos.get(tkr, {})
            familia = info.get("familia", "")
            p = determinar_preco_atual(tkr, familia, precos_pub, precos_man, hoje)
            if p:
                preco_atual[tkr] = p
        divs = cruzar_conviccao_resultado(decisoes, preco_atual)
        divergencias.extend(divs)

    # ── Cruzamento 4: critério de invalidação vs estado das teses ─────────
    if "invalidacao" in tipos_req and teses:
        divs = cruzar_invalidacao_teses(teses, hoje)
        divergencias.extend(divs)

    # ── Ordenar: CRITICO → ATENCAO → INFO ─────────────────────────────────
    ordem = {"CRITICO": 0, "ATENCAO": 1, "INFO": 2}
    divergencias.sort(key=lambda d: ordem.get(d.get("severidade", "INFO"), 2))

    criticos = sum(1 for d in divergencias if d.get("severidade") == "CRITICO")
    atencoes = sum(1 for d in divergencias if d.get("severidade") == "ATENCAO")

    return {
        "divergencias": divergencias,
        "total": len(divergencias),
        "criticos": criticos,
        "atencoes": atencoes,
        "periodo_analise": perfil.get("periodo"),
        "calculado_em": str(hoje),
        "nota": "Fatos apenas — sem recomendações. O maestro contextualiza ao ser consultado.",
    }


# ─── Fatia 8b: Vieses comportamentais ────────────────────────────────────────

def fn_vieses_comportamentais(periodo_meses: int = 12) -> dict:
    """
    Detecta 5 vieses comportamentais a partir do event log.
    Apresenta fato mensurável + nome do padrão. Não prescreve ação.

    Vieses: disposition_effect, overtrading, subdiversificacao,
            clustering_temporal, trend_chasing.
    """
    from datetime import date
    from carteira_clean_web.backend.db.models import Evento as EventoModel, Ativo as AtivoModel
    from carteira_clean_web.backend.db.session import get_session
    from carteira_clean_web.backend.engine.vieses import (
        calcular_disposition_effect, calcular_overtrading,
        calcular_subdiversificacao, calcular_clustering_temporal,
        calcular_trend_chasing,
    )

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Recalcule a carteira."}

    estado = engine_cache.get_estado()
    hoje = estado["hoje"]
    m = hoje.month - periodo_meses
    y = hoje.year
    while m <= 0:
        m += 12
        y -= 1
    periodo_ini = date(y, m, 1)

    session = get_session()
    try:
        evs = session.query(EventoModel).order_by(EventoModel.data).all()
        eventos = [e.to_dict() for e in evs]
    finally:
        session.close()

    # Cotações históricas {ticker: {date_str: preco}}
    precos_pub = estado.get("precos_publicos", {})
    cotacoes_hist: dict[str, dict] = {}
    for tkr, serie in precos_pub.items():
        cotacoes_hist[tkr] = {str(k): v for k, v in serie.items()}

    # Dados já calculados da Fatia 8 (reutilizar sem recalcular)
    perfil = fn_perfil_comportamental("todos", periodo_meses)
    turnover = perfil.get("turnover", {})
    concentracao = perfil.get("concentracao", {})
    frequencia = perfil.get("frequencia", {})

    vieses = [
        calcular_disposition_effect(eventos, cotacoes_hist),
        calcular_overtrading(turnover),
        calcular_subdiversificacao(concentracao),
        calcular_clustering_temporal(frequencia),
        calcular_trend_chasing(eventos, cotacoes_hist, periodo_ini, hoje),
    ]

    detectados = [v for v in vieses if v["detectado"]]
    return {
        "vieses": vieses,
        "total_detectados": len(detectados),
        "detectados": [v["nome_vies"] for v in detectados],
        "periodo": f"{periodo_ini} a {hoje}",
        "nota": (
            "Padrões factuais — não são diagnósticos. O investidor avalia "
            "conscientemente se quer manter ou corrigir cada padrão. "
            "Consulte o glossário para explicações detalhadas."
        ),
    }


# ─── Fatia 10: Fundamentalista ────────────────────────────────────────────────

def _carregar_fundamentos_db() -> dict[str, list[dict]]:
    """Carrega todos os fundamentos mais recentes do DB, agrupados por ticker."""
    from carteira_clean_web.backend.db.models import Fundamento
    from carteira_clean_web.backend.db.session import get_session
    session = get_session()
    try:
        rows = session.query(Fundamento).order_by(Fundamento.fetched_at.desc()).all()
        result: dict[str, list[dict]] = {}
        for r in rows:
            result.setdefault(r.ticker, []).append({
                "indicador":      r.indicador,
                "valor":          r.valor,
                "data_referencia": str(r.data_referencia) if r.data_referencia else None,
                "fetched_at":     str(r.fetched_at) if r.fetched_at else "",
            })
        return result
    finally:
        session.close()


def fn_analise_fundamentalista(ticker: str) -> dict:
    """
    Análise fundamentalista em 4 dimensões para um ativo.
    Compara com peers do mesmo setor e com histórico próprio.
    Fonte: tabela fundamentos (yfinance + brapi, peers via taxonomia_setorial).
    """
    from carteira_clean_web.backend.engine import peers as peers_mod
    from carteira_clean_web.backend.engine.fundamentalista import analise_fundamentalista

    ticker = ticker.upper()
    fundamentos = _carregar_fundamentos_db()

    if ticker not in fundamentos:
        return {"erro": f"Sem fundamentos para {ticker}. Execute a coleta: POST /api/v1/macro/coletar"}

    # Peers resolvidos via taxonomia_setorial (brapi) — não mais pelo campo
    # livre ativos.setor, que só encontrava peers dentro da própria carteira.
    candidatos = peers_mod.peers_do_mesmo_setor(ticker)
    fundamentos_setor = {p: fundamentos[p] for p in candidatos if p in fundamentos}
    return analise_fundamentalista(ticker, fundamentos[ticker], fundamentos_setor)


def fn_screening_fundamentalista(
    roe_min: float | None = None,
    dy_min: float | None = None,
    pl_max: float | None = None,
    div_liq_ebitda_max: float | None = None,
    margem_ebitda_min: float | None = None,
) -> dict:
    """
    Filtra ativos da carteira + watchlist por critérios fundamentalistas.
    Todos os parâmetros são opcionais — use os que quiser.

    Args:
        roe_min: ROE mínimo (%)
        dy_min:  DY mínimo (%)
        pl_max:  P/L máximo
        div_liq_ebitda_max: Dív.Líq/EBITDA máximo
        margem_ebitda_min: Margem EBITDA mínima (%)
    """
    from carteira_clean_web.backend.engine.fundamentalista import screening_fundamentalista

    criterios: dict[str, dict] = {}
    if roe_min is not None:            criterios["ROE"] = {"min": roe_min}
    if dy_min is not None:             criterios["DY"]  = {"min": dy_min}
    if pl_max is not None:             criterios["PL"]  = {"max": pl_max}
    if div_liq_ebitda_max is not None: criterios["DIV_LIQ_EBITDA"] = {"max": div_liq_ebitda_max}
    if margem_ebitda_min is not None:  criterios["MARGEM_EBITDA"] = {"min": margem_ebitda_min}

    if not criterios:
        return {"erro": "Informe pelo menos um critério (roe_min, dy_min, pl_max, div_liq_ebitda_max, margem_ebitda_min)."}

    fundamentos = _carregar_fundamentos_db()
    resultado = screening_fundamentalista(criterios, fundamentos)
    return {
        "criterios_aplicados": criterios,
        "ativos_encontrados": len(resultado),
        "lista": resultado,
        "nota": "Fonte: tabela fundamentos (yfinance + brapi). Apenas ativos com dados disponíveis.",
    }


def fn_comparar_multiplos(tickers: list[str]) -> dict:
    """
    Tabela side-by-side de múltiplos fundamentalistas para 2-5 tickers.
    Exemplo: ["PETR4", "PRIO3", "WEGE3"]
    """
    from carteira_clean_web.backend.engine.fundamentalista import comparar_multiplos
    if not tickers or len(tickers) < 2:
        return {"erro": "Informe pelo menos 2 tickers."}
    tickers = [t.upper() for t in tickers[:5]]
    fundamentos = _carregar_fundamentos_db()
    return comparar_multiplos(tickers, fundamentos)


# ─── Fatia 11: Setorial / Regime de mercado ───────────────────────────────────

# Macro relevante por índice setorial B3 (chave estável — não depende do
# texto livre de ativos.setor). Ex.: bancos/financeiro reagem a juros;
# energia/saneamento a juros+inflação (regulação por IPCA); materiais
# básicos/petróleo ao câmbio (commodities dolarizadas).
_MACRO_POR_INDICE: dict[str, list[str]] = {
    "IDX_IFNC": ["SELIC_META"],
    "IDX_IMOB": ["SELIC_META", "IPCA"],
    "IDX_UTIL": ["SELIC_META", "IPCA"],
    "IDX_IEE":  ["SELIC_META", "IPCA"],
    "IDX_IMAT": ["USD_BRL"],
    "IDX_INDX": ["IPCA"],
    "IDX_ICON": ["IPCA", "SELIC_META"],
}


def fn_contexto_setorial(setor: str = "todos") -> dict:
    """
    Contexto setorial: performance recente do índice B3 + macro relevante +
    ativos da carteira no setor.

    Setor do ticker é resolvido via taxonomia_setorial (brapi), não mais
    pelo campo livre `ativos.setor` — evita a fragilidade de string
    hardcoded/curada manualmente (rótulo inconsistente = tool vazia).

    Args:
        setor: código do índice (ex.: "IFNC"), nome amigável (ex.: "Bancos")
               ou "todos".
    """
    from carteira_clean_web.backend.engine.macro_client import ler_macro
    from carteira_clean_web.backend.engine.precos import carregar_indices_setoriais_da_tabela
    from carteira_clean_web.backend.engine import taxonomia

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio. Clique em Recalcular antes de usar o assistente."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]

    taxonomia_map = taxonomia.carregar_taxonomia_completa()

    # Ativos em carteira agrupados pelo índice setorial resolvido via brapi.
    # Sem taxonomia (ainda não coletada, ou ativo não listado em bolsa) →
    # bucket residual "outros", usando o campo livre só como rótulo (não
    # como chave de busca/filtro).
    carteira_por_indice: dict[str, list[str]] = {}
    outros: list[dict] = []
    for tkr, pos in posicoes_dict.items():
        if pos.qtd < 1e-9:
            continue
        setor_brapi = taxonomia_map.get(tkr)
        idx = taxonomia.mapear_setor_para_indice(setor_brapi)
        if idx:
            carteira_por_indice.setdefault(idx, []).append(tkr)
        else:
            outros.append({"ticker": tkr, "setor_cadastro": ativos.get(tkr, {}).get("setor") or "—"})

    # Resolve o(s) índice(s) alvo a partir do parâmetro `setor`.
    if setor == "todos":
        indices_alvo = list(carteira_por_indice.keys())
    else:
        s_lower = setor.strip().lower()
        indices_alvo = []
        for idx in carteira_por_indice.keys():
            codigo = idx.replace("IDX_", "")
            display = taxonomia.DISPLAY_POR_INDICE.get(idx, "")
            if s_lower == codigo.lower() or s_lower in display.lower() or codigo.lower() in s_lower:
                indices_alvo.append(idx)

    todos_inds = list({ind for idx in indices_alvo for ind in _MACRO_POR_INDICE.get(idx, [])})
    macro = ler_macro(indicadores=todos_inds or None, ultimos_n=3) if todos_inds else {}

    indices_tabela = carregar_indices_setoriais_da_tabela()

    resultado_setores = []
    for idx in indices_alvo:
        inds_rel = _MACRO_POR_INDICE.get(idx, [])
        macro_s = {ind: macro.get(ind, []) for ind in inds_rel}
        serie = indices_tabela.get(idx, {})
        resultado_setores.append({
            "indice": idx.replace("IDX_", ""),
            "nome": taxonomia.DISPLAY_POR_INDICE.get(idx, idx),
            "desempenho_recente": _retorno_recente_idx(serie),
            "ativos_carteira": carteira_por_indice.get(idx, []),
            "macro_relevante": {
                ind: pts[0] if pts else None
                for ind, pts in macro_s.items()
            },
        })

    resposta = {
        "setores": resultado_setores,
        "nota": "Correlações históricas como contexto — não previsão.",
    }
    if setor == "todos" and outros:
        resposta["outros_sem_taxonomia"] = outros
    return resposta


def fn_regime_mercado() -> dict:
    """
    Classifica o regime macroeconômico atual em 4 eixos:
    juros (subindo/estável/caindo), inflação, câmbio, bolsa.
    Cruza com exposição da carteira por bloco IPS.
    """
    from carteira_clean_web.backend.engine.macro_client import ler_macro

    macro = ler_macro(indicadores=["SELIC_META", "IPCA_FOCUS", "IPCA", "USD_BRL"], ultimos_n=6)

    def tendencia(pts: list[dict], n: int = 3) -> str:
        vals = [p["valor"] for p in pts[:n] if p.get("valor") is not None]
        if len(vals) < 2:
            return "sem dados"
        if vals[0] > vals[-1] * 1.02:
            return "subindo"
        if vals[0] < vals[-1] * 0.98:
            return "caindo"
        return "estavel"

    selic_pts   = macro.get("SELIC_META", [])
    ipca_pts    = macro.get("IPCA", [])
    focus_pts   = macro.get("IPCA_FOCUS", [])
    usd_pts     = macro.get("USD_BRL", [])

    selic_atual = selic_pts[0]["valor"] if selic_pts else None
    focus_atual = focus_pts[0]["valor"] if focus_pts else None

    # Juros: comparar Selic atual vs Focus 12m
    if selic_atual and focus_atual:
        if focus_atual > selic_atual * 1.01:
            juros_regime = "subindo"
        elif focus_atual < selic_atual * 0.99:
            juros_regime = "caindo"
        else:
            juros_regime = "estavel"
    else:
        juros_regime = tendencia(selic_pts)

    ipca_regime = tendencia(ipca_pts)
    cambio_regime = tendencia(usd_pts, 2)

    regime = {
        "juros": {
            "classificacao": juros_regime,
            "selic_atual": selic_atual,
            "focus_12m": focus_atual,
        },
        "inflacao": {
            "classificacao": "acelerando" if ipca_regime == "subindo" else
                             "desacelerando" if ipca_regime == "caindo" else "controlada",
            "ultimo_ipca": ipca_pts[0]["valor"] if ipca_pts else None,
        },
        "cambio": {
            "classificacao": "depreciacao" if cambio_regime == "subindo" else
                             "apreciacao" if cambio_regime == "caindo" else "estavel",
            "usd_brl_atual": usd_pts[0]["valor"] if usd_pts else None,
        },
        "nota": "Classificação factual com dados BCB. Não é previsão.",
    }
    return regime


# ─── Fatia 12: Análise técnica ───────────────────────────────────────────────

def _buscar_ohlcv(ticker: str, periodo: str = "6mo") -> dict:
    """Busca OHLCV do yfinance. Formata B3 tickers com .SA"""
    import re
    import yfinance as yf
    yf_ticker = ticker + ".SA" if re.match(r"^[A-Z]{3,5}\d{1,2}$", ticker.upper()) else ticker
    t = yf.Ticker(yf_ticker)
    hist = t.history(period=periodo, auto_adjust=True)
    if hist.empty:
        return {}
    return {
        "dates":  [str(d.date()) for d in hist.index],
        "open":   hist["Open"].tolist(),
        "high":   hist["High"].tolist(),
        "low":    hist["Low"].tolist(),
        "close":  hist["Close"].tolist(),
        "volume": hist["Volume"].tolist(),
    }


def fn_analise_tecnica(ticker: str, periodo: str = "6mo") -> dict:
    """
    Análise técnica com sistema de votação (estilo TradingView).

    Indicadores: MM20/50/200, RSI 14, MACD (12,26,9), Bollinger (20,2).
    Sistema de votação: cada indicador vota -1/0/+1.
    Rating geral oscila entre -1 (venda forte) e +1 (compra forte).

    Args:
        ticker: código do ativo (ex: "PETR4", "WEGE3")
        periodo: "1mo" | "3mo" | "6mo" | "1y" | "2y" (default "6mo")
    """
    from carteira_clean_web.backend.engine.tecnico import calcular_indicadores
    ticker = ticker.upper()
    ohlcv = _buscar_ohlcv(ticker, periodo)
    if not ohlcv:
        return {"erro": f"Sem dados OHLCV para {ticker}. Verifique o ticker."}
    return calcular_indicadores(ticker, ohlcv)


def fn_grafico_tecnico(ticker: str, periodo: str = "6mo") -> dict:
    """
    Gera gráfico candlestick interativo (Plotly HTML) com:
    MMs 20/50/200, Bandas de Bollinger, suportes/resistências,
    linhas de entrada/alvo/stop, volume, RSI e MACD em subplots.

    Args:
        ticker: código do ativo
        periodo: "1mo" | "3mo" | "6mo" | "1y" | "2y"

    Retorna o caminho do arquivo HTML gerado em /data/charts/.
    """
    from carteira_clean_web.backend.engine.tecnico import calcular_indicadores, gerar_grafico_html
    ticker = ticker.upper()

    # Busca 2 anos para garantir MM200 calculável; exibe só o período solicitado
    ohlcv_completo = _buscar_ohlcv(ticker, "2y")
    if not ohlcv_completo:
        return {"erro": f"Sem dados OHLCV para {ticker}."}

    # Indicadores calculados sobre histórico completo (MM200 precisa de ≥200 candles)
    indicadores = calcular_indicadores(ticker, ohlcv_completo)
    if "erro" in indicadores:
        return indicadores

    # Passa histórico completo para cálculo das MMs + período de exibição
    _periodo_candles = {"1mo": 22, "3mo": 66, "6mo": 130, "1y": 252, "2y": 504}
    n_exibir = _periodo_candles.get(periodo, 130)

    path = gerar_grafico_html(ticker, ohlcv_completo, indicadores, n_exibir=n_exibir)
    return {
        "ticker": ticker,
        "arquivo": path,
        "rating_geral": indicadores.get("rating_geral"),
        "tendencia": indicadores.get("tendencia"),
        "nota": f"Gráfico salvo em {path}. Abra no browser para interagir.",
    }


# ─── Fatia 13: Notícias e impacto macro ──────────────────────────────────────

def fn_noticias_ativos(
    ticker: str = "carteira",
    dias: int = 7,
) -> dict:
    """
    Retorna notícias recentes dos ativos via yfinance.

    Args:
        ticker: código do ativo (ex: "PETR4"), "carteira" (top-10 por patrimônio)
                ou "watchlist"
        dias:   janela em dias (default 7)
    """
    from carteira_clean_web.backend.engine.noticias import buscar_noticias_ticker

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]
    precos_pub = estado.get("precos_publicos", {})
    hoje = estado["hoje"]

    if ticker.lower() == "carteira":
        # Top-10 por valor atual
        vals = []
        for tkr, pos in posicoes_dict.items():
            if pos.qtd < 1e-9:
                continue
            preco = preco_em(precos_pub.get(tkr, {}), hoje)
            val = pos.qtd * preco if preco else pos.custo_total
            vals.append((tkr, val))
        tickers = [t for t, _ in sorted(vals, key=lambda x: -x[1])[:10]]
    elif ticker.lower() == "watchlist":
        from carteira_clean_web.backend.db.models import WatchlistItem
        from carteira_clean_web.backend.db.session import get_session
        session = get_session()
        try:
            tickers = [w.ticker for w in session.query(WatchlistItem).filter(WatchlistItem.ativo == 1).all()][:10]
        finally:
            session.close()
    else:
        tickers = [ticker.upper()]

    todas_noticias = []
    for t in tickers:
        todas_noticias.extend(buscar_noticias_ticker(t, dias))

    por_ticker: dict[str, list] = {}
    for n in todas_noticias:
        por_ticker.setdefault(n["ticker"], []).append(n)

    return {
        "noticias": todas_noticias,
        "por_ticker": por_ticker,
        "total": len(todas_noticias),
        "tickers_consultados": tickers,
        "janela_dias": dias,
        "nota": "Fonte: yfinance .news. O maestro contextualiza o impacto potencial.",
    }


def fn_impacto_macro(
    evento: str = "",
    indicador: str = "",
    variacao: str = "QUEDA",
) -> dict:
    """
    Avalia o impacto de um evento macro nos ativos da carteira.

    Consulta a matriz de sensibilidade macro→setor e cruza com a carteira.

    Args:
        evento:    texto livre (ex: "queda de 0.5pp na Selic") — interpretado
                   para identificar indicador e variação automaticamente
        indicador: enum macro: SELIC_META | USD_BRL | IPCA | IPCA_FOCUS
        variacao:  "ALTA" ou "QUEDA"
    """
    from carteira_clean_web.backend.db.models import MatrizSensibilidade
    from carteira_clean_web.backend.db.session import get_session

    if not engine_cache.esta_calculado():
        engine_cache.carregar_disco()
    if not engine_cache.esta_calculado():
        return {"erro": "Cache vazio."}

    estado = engine_cache.get_estado()
    posicoes_dict = estado["posicoes"]
    ativos = estado["ativos"]

    # Inferir indicador e variação do texto livre se não fornecidos
    if evento and not indicador:
        ev_lower = evento.lower()
        if "selic" in ev_lower or "juros" in ev_lower:
            indicador = "SELIC_META"
        elif "dólar" in ev_lower or "usd" in ev_lower or "câmbio" in ev_lower:
            indicador = "USD_BRL"
        elif "ipca" in ev_lower or "inflação" in ev_lower:
            indicador = "IPCA"
        if "queda" in ev_lower or "redução" in ev_lower or "corte" in ev_lower or "cai" in ev_lower:
            variacao = "QUEDA"
        elif "alta" in ev_lower or "aumento" in ev_lower or "sobe" in ev_lower:
            variacao = "ALTA"

    if not indicador:
        return {"erro": "Informe 'indicador' (SELIC_META|USD_BRL|IPCA) ou 'evento' em texto livre."}

    session = get_session()
    try:
        linhas = session.query(MatrizSensibilidade).filter(
            MatrizSensibilidade.indicador == indicador.upper(),
            MatrizSensibilidade.variacao  == variacao.upper(),
        ).order_by(MatrizSensibilidade.peso.desc()).all()
    finally:
        session.close()

    if not linhas:
        return {
            "indicador": indicador,
            "variacao": variacao,
            "impactos": [],
            "nota": "Nenhuma regra encontrada na matriz de sensibilidade para este indicador/variação.",
        }

    # Mapear setores afetados → ativos em carteira
    setores_afetados = {l.setor: {"direcao": l.direcao, "logica": l.logica, "peso": l.peso}
                        for l in linhas}
    ativos_afetados = []
    for tkr, pos in posicoes_dict.items():
        if pos.qtd < 1e-9:
            continue
        setor = ativos.get(tkr, {}).get("setor") or "—"
        if setor in setores_afetados:
            info = setores_afetados[setor]
            ativos_afetados.append({
                "ticker":   tkr,
                "setor":    setor,
                "direcao":  info["direcao"],
                "logica":   info["logica"],
                "peso":     info["peso"],
            })

    ativos_afetados.sort(key=lambda x: (-x["peso"], x["direcao"]))

    return {
        "evento":    evento or f"{indicador} {variacao}",
        "indicador": indicador,
        "variacao":  variacao,
        "setores_afetados": [
            {"setor": s, **info} for s, info in setores_afetados.items()
        ],
        "ativos_carteira_afetados": ativos_afetados,
        "total_ativos": len(ativos_afetados),
        "nota": "Correlações estruturais conhecidas — não previsão. A matriz é referência; o maestro pode nuançar.",
    }


# ─── Glossário ────────────────────────────────────────────────────────────────

def fn_consultar_glossario(termo: str = "", categoria: str = "") -> dict:
    """
    Retorna definição de indicadores e vieses comportamentais.

    Args:
        termo:     nome ou código do indicador (ex: "P/L", "ROE", "disposition effect",
                   "RSI", "overtrading") — busca parcial.
        categoria: "fundamentalista" | "tecnico" | "comportamental" — lista todos da categoria.
    """
    from carteira_clean_web.backend.engine.glossario import consultar, listar_por_categoria, GLOSSARIO

    if termo:
        entrada = consultar(termo)
        if entrada:
            return {"encontrado": True, "resultado": entrada}
        return {
            "encontrado": False,
            "sugestoes": [e["nome"] for e in GLOSSARIO.values()],
            "nota": f"'{termo}' não encontrado. Tente uma das sugestões.",
        }
    if categoria:
        lista = listar_por_categoria(categoria)
        return {"categoria": categoria, "total": len(lista), "indicadores": lista}

    return {
        "total": len(GLOSSARIO),
        "categorias": {
            "fundamentalista": [e["nome"] for e in GLOSSARIO.values() if e["categoria"] == "fundamentalista"],
            "tecnico":         [e["nome"] for e in GLOSSARIO.values() if e["categoria"] == "tecnico"],
            "comportamental":  [e["nome"] for e in GLOSSARIO.values() if e["categoria"] == "comportamental"],
        },
        "uso": "fn_consultar_glossario(termo='P/L') ou fn_consultar_glossario(categoria='tecnico')",
    }


# ════════════════════════════════════════════════════════════════════
# CAMADA 3 — TOOLS DE ESCRITA (L2: propõe → confirma → grava)
# A confirmação acontece no diálogo (system prompt). Estas funções
# executam a gravação apenas quando o Maestro as chama, já confirmadas.
# ════════════════════════════════════════════════════════════════════

_ACOES_DIARIO = {"COMPRA", "VENDA", "AUMENTO", "REDUCAO", "MANTER", "WATCHLIST"}
_BLOCOS_IPS = {"SWING_TRADE", "GROWTH", "DEFENSIVOS", "RENDA_FIXA"}
_TIPOS_ALERTA = {"RSI", "banda_IPS", "preco", "invalidacao"}


def fn_registrar_tese(
    ticker: str,
    racional: str,
    bloco_ips: str | None = None,
    cenario_esperado: str | None = None,
    criterio_invalidacao: str | None = None,
    gatilho: str | None = None,
) -> dict:
    """Grava uma nova tese de investimento na tabela `teses`.

    L2: só deve ser chamada após o investidor confirmar os detalhes.

    Args:
        ticker: código do ativo (ex: WEGE3)
        racional: tese central — por que investir
        bloco_ips: SWING_TRADE | GROWTH | DEFENSIVOS | RENDA_FIXA (opcional)
        cenario_esperado: cenário-base esperado (opcional)
        criterio_invalidacao: o que invalidaria a tese (opcional)
        gatilho: gatilho de monitoramento — anexado ao critério (opcional)
    """
    from datetime import date
    from carteira_clean_web.backend.db.models import Tese
    from carteira_clean_web.backend.db.session import get_session

    if not ticker or not racional:
        return {"erro": "ticker e racional são obrigatórios."}

    crit = (criterio_invalidacao or "").strip()
    if gatilho and gatilho.strip():
        crit = (crit + f"\nGatilho: {gatilho.strip()}").strip()

    session = get_session()
    try:
        t = Tese(
            ticker=ticker.upper(),
            bloco_ips=bloco_ips,
            racional=racional.strip(),
            cenario_esperado=(cenario_esperado or "").strip() or None,
            criterio_invalidacao=crit or None,
            nivel_invalidacao="VERDE",
            data_criacao=date.today(),
            status="ATIVA",
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        return {"ok": True, "acao": "tese_registrada", "tese": t.to_dict()}
    except Exception as exc:
        session.rollback()
        return {"erro": f"Falha ao registrar tese: {exc}"}
    finally:
        session.close()


def fn_registrar_decisao_diario(
    ticker: str,
    acao: str,
    racional: str,
    conviccao: int = 3,
    preco: float | None = None,
    cenario_esperado: str | None = None,
    tese_id: int | None = None,
) -> dict:
    """Grava uma decisão no diário estruturado (tabela `diario_decisoes`).

    L2: só deve ser chamada após o investidor confirmar.

    Args:
        ticker: código do ativo
        acao: COMPRA | VENDA | AUMENTO | REDUCAO | MANTER | WATCHLIST
        racional: por que tomou a decisão
        conviccao: 1 a 5 (default 3)
        preco: preço de entrada/referência (opcional)
        cenario_esperado: cenário esperado (opcional)
        tese_id: vincular a uma tese existente (opcional)
    """
    from datetime import date
    from carteira_clean_web.backend.db.models import DiarioDecisao
    from carteira_clean_web.backend.db.session import get_session

    acao_up = (acao or "").upper()
    if acao_up not in _ACOES_DIARIO:
        return {"erro": f"acao inválida: {acao}. Use uma de {sorted(_ACOES_DIARIO)}."}
    try:
        conv = int(conviccao)
    except (TypeError, ValueError):
        conv = 3
    if not 1 <= conv <= 5:
        return {"erro": "conviccao deve estar entre 1 e 5."}
    if not ticker or not racional:
        return {"erro": "ticker e racional são obrigatórios."}

    session = get_session()
    try:
        d = DiarioDecisao(
            data_decisao=date.today(),
            ticker=ticker.upper(),
            acao=acao_up,
            racional=racional.strip(),
            cenario_esperado=(cenario_esperado or "").strip() or None,
            conviccao=conv,
            preco_entrada=preco,
            tese_id=tese_id,
        )
        session.add(d)
        session.commit()
        session.refresh(d)
        return {"ok": True, "acao": "decisao_registrada", "decisao": d.to_dict()}
    except Exception as exc:
        session.rollback()
        return {"erro": f"Falha ao registrar decisão: {exc}"}
    finally:
        session.close()


def fn_atualizar_tese(
    tese_id: int,
    racional: str | None = None,
    bloco_ips: str | None = None,
    cenario_esperado: str | None = None,
    criterio_invalidacao: str | None = None,
    nivel_invalidacao: str | None = None,
) -> dict:
    """Atualiza campos de uma tese existente. L2: só após confirmação.

    Passe apenas os campos a alterar; os demais ficam intactos.
    nivel_invalidacao: VERDE | AMARELO | VERMELHO
    """
    from datetime import date
    from carteira_clean_web.backend.db.models import Tese
    from carteira_clean_web.backend.db.session import get_session

    session = get_session()
    try:
        t = session.get(Tese, tese_id)
        if not t:
            return {"erro": f"Tese {tese_id} não encontrada."}
        if racional is not None:
            t.racional = racional.strip()
        if bloco_ips is not None:
            t.bloco_ips = bloco_ips
        if cenario_esperado is not None:
            t.cenario_esperado = cenario_esperado.strip() or None
        if criterio_invalidacao is not None:
            t.criterio_invalidacao = criterio_invalidacao.strip() or None
        if nivel_invalidacao is not None:
            nv = nivel_invalidacao.upper()
            if nv not in {"VERDE", "AMARELO", "VERMELHO"}:
                return {"erro": "nivel_invalidacao deve ser VERDE, AMARELO ou VERMELHO."}
            t.nivel_invalidacao = nv
        t.data_atualizacao = date.today()
        session.commit()
        session.refresh(t)
        return {"ok": True, "acao": "tese_atualizada", "tese": t.to_dict()}
    except Exception as exc:
        session.rollback()
        return {"erro": f"Falha ao atualizar tese: {exc}"}
    finally:
        session.close()


def fn_invalidar_tese(tese_id: int, motivo: str) -> dict:
    """Marca uma tese como INVALIDADA com o motivo. L2: só após confirmação."""
    from datetime import date
    from carteira_clean_web.backend.db.models import Tese
    from carteira_clean_web.backend.db.session import get_session

    if not motivo or not motivo.strip():
        return {"erro": "motivo da invalidação é obrigatório."}

    session = get_session()
    try:
        t = session.get(Tese, tese_id)
        if not t:
            return {"erro": f"Tese {tese_id} não encontrada."}
        t.status = "INVALIDADA"
        t.nivel_invalidacao = "VERMELHO"
        t.observacao_encerramento = motivo.strip()
        t.data_atualizacao = date.today()
        session.commit()
        session.refresh(t)
        return {"ok": True, "acao": "tese_invalidada", "tese": t.to_dict()}
    except Exception as exc:
        session.rollback()
        return {"erro": f"Falha ao invalidar tese: {exc}"}
    finally:
        session.close()


def fn_criar_alerta(
    tipo: str,
    condicao: str,
    ativo: str | None = None,
    valor_gatilho: float | None = None,
) -> dict:
    """Cadastra um alerta/gatilho monitorável (tabela `alertas`). L2: só após confirmação.

    Args:
        tipo: RSI | banda_IPS | preco | invalidacao
        condicao: operador/descrição (ex: ">=", "<=", "fora_banda")
        ativo: alvo — ticker (RSI/preco), bloco_ips (banda_IPS) ou tese_id (invalidacao)
        valor_gatilho: limiar numérico (ex: 80 para "RSI >= 80")
    """
    from datetime import datetime
    from carteira_clean_web.backend.db.models import Alerta
    from carteira_clean_web.backend.db.session import get_session

    if tipo not in _TIPOS_ALERTA:
        return {"erro": f"tipo inválido: {tipo}. Use {sorted(_TIPOS_ALERTA)}."}
    if not condicao or not condicao.strip():
        return {"erro": "condicao é obrigatória."}

    session = get_session()
    try:
        a = Alerta(
            tipo=tipo,
            ativo=(ativo or "").strip().upper() or None if tipo in {"RSI", "preco", "banda_IPS"} else (ativo or None),
            condicao=condicao.strip(),
            valor_gatilho=valor_gatilho,
            ativo_bool=1,
            disparado_em=None,
            criado_em=datetime.utcnow(),
        )
        session.add(a)
        session.commit()
        session.refresh(a)
        return {"ok": True, "acao": "alerta_criado", "alerta": a.to_dict()}
    except Exception as exc:
        session.rollback()
        return {"erro": f"Falha ao criar alerta: {exc}"}
    finally:
        session.close()


def _checar_alerta(a, sinais_cache: dict, aderencia_cache: list, session) -> dict | None:
    """Avalia um alerta. Retorna dict de disparo se gatilhou, senão None."""
    tipo = a.tipo
    alvo = a.ativo or ""
    valor = a.valor_gatilho
    cond = (a.condicao or "").strip()

    def _cmp(atual: float, operador: str, limiar: float) -> bool:
        if limiar is None:
            return False
        if operador in (">=", ">", "acima", "maior"):
            return atual >= limiar
        if operador in ("<=", "<", "abaixo", "menor"):
            return atual <= limiar
        return abs(atual - limiar) < 1e-9

    if tipo == "RSI":
        sinal = sinais_cache.get(alvo)
        rsi = sinal.get("rsi") if sinal else None
        if rsi is None:
            return None
        if _cmp(rsi, cond, valor):
            return {"alerta_id": a.id, "tipo": tipo, "ativo": alvo,
                    "mensagem": f"{alvo} RSI {rsi:.1f} cruzou {cond} {valor:.0f}",
                    "valor_atual": rsi}
        return None

    if tipo == "preco":
        from carteira_clean_web.backend.api import cache as ec
        if not ec.esta_calculado():
            ec.carregar_disco()
        preco_atual = None
        if ec.esta_calculado():
            est = ec.get_estado()
            precos_pub = est.get("precos_publicos", {})
            hoje = est.get("hoje")
            preco_atual = preco_em(precos_pub.get(alvo, {}), hoje) if hoje else None
        if preco_atual is None:
            return None
        if _cmp(preco_atual, cond, valor):
            return {"alerta_id": a.id, "tipo": tipo, "ativo": alvo,
                    "mensagem": f"{alvo} preço R${preco_atual:.2f} cruzou {cond} R${valor:.2f}",
                    "valor_atual": preco_atual}
        return None

    if tipo == "banda_IPS":
        bloco = next((b for b in aderencia_cache if b["bloco_ips"] == alvo), None)
        if not bloco:
            return None
        if bloco["status"] != "dentro":
            return {"alerta_id": a.id, "tipo": tipo, "ativo": alvo,
                    "mensagem": f"Bloco {alvo} {bloco['status'].replace('_', ' ')} "
                                f"({bloco['w_real_pct']}% vs banda "
                                f"{bloco['banda_inf_pct']}–{bloco['banda_sup_pct']}%)",
                    "valor_atual": bloco["w_real_pct"]}
        return None

    if tipo == "invalidacao":
        from carteira_clean_web.backend.db.models import Tese
        try:
            tese_id = int(alvo)
        except (TypeError, ValueError):
            return None
        t = session.get(Tese, tese_id)
        if not t:
            return None
        if t.status == "INVALIDADA" or t.nivel_invalidacao == "VERMELHO":
            return {"alerta_id": a.id, "tipo": tipo, "ativo": alvo,
                    "mensagem": f"Tese {tese_id} ({t.ticker}) em estado de invalidação "
                                f"(status={t.status}, nível={t.nivel_invalidacao})",
                    "valor_atual": None}
        return None

    return None


def fn_listar_alertas(apenas_ativos: bool = False) -> dict:
    """Lista os alertas cadastrados (habilitados e desabilitados).

    Use quando o investidor perguntar quais alertas existem. Diferente de
    verificar_alertas, que só reporta os que DISPARARAM.

    Args:
        apenas_ativos: se True, retorna só os habilitados.
    """
    from carteira_clean_web.backend.db.models import Alerta
    from carteira_clean_web.backend.db.session import get_session

    session = get_session()
    try:
        q = session.query(Alerta).order_by(Alerta.criado_em.desc())
        if apenas_ativos:
            q = q.filter(Alerta.ativo_bool == 1)
        itens = [a.to_dict() for a in q.all()]
        return {"total": len(itens), "alertas": itens}
    finally:
        session.close()


def fn_verificar_alertas() -> dict:
    """Verifica todos os alertas habilitados e reporta quais dispararam.

    O Maestro deve chamar no início da conversa. Marca disparado_em nos
    que gatilharam. Não envia push — o disparo aparece na conversa.
    """
    from datetime import datetime
    from carteira_clean_web.backend.db.models import Alerta
    from carteira_clean_web.backend.db.session import get_session

    session = get_session()
    try:
        alertas = session.query(Alerta).filter(Alerta.ativo_bool == 1).all()
        if not alertas:
            return {"total": 0, "disparados": [], "nota": "Nenhum alerta cadastrado."}

        # Pré-carrega sinais (RSI) e aderência IPS uma vez só
        tickers_rsi = [a.ativo for a in alertas if a.tipo == "RSI" and a.ativo]
        sinais_cache: dict = {}
        if tickers_rsi:
            try:
                from carteira_clean_web.backend.engine.sinais_tecnicos import calcular_sinais_lote
                for s in calcular_sinais_lote(tickers_rsi):
                    sinais_cache[s["ticker"]] = s
            except Exception as exc:
                log.warning(f"Falha ao calcular sinais p/ alertas: {exc}")

        aderencia_cache: list = []
        if any(a.tipo == "banda_IPS" for a in alertas):
            try:
                res = fn_analise_aderencia_setorial()
                aderencia_cache = res.get("blocos", res.get("aderencia", [])) if isinstance(res, dict) else []
            except Exception as exc:
                log.warning(f"Falha aderência p/ alertas: {exc}")

        disparados = []
        agora = datetime.utcnow()
        for a in alertas:
            try:
                hit = _checar_alerta(a, sinais_cache, aderencia_cache, session)
            except Exception as exc:
                log.warning(f"Alerta {a.id} falhou: {exc}")
                hit = None
            if hit:
                a.disparado_em = agora
                disparados.append(hit)
        session.commit()

        return {
            "total": len(alertas),
            "n_disparados": len(disparados),
            "disparados": disparados,
            "nota": "Nenhum alerta disparou." if not disparados else None,
        }
    finally:
        session.close()


def fn_forcar_coleta(tipo: str) -> dict:
    """Dispara coleta de dados sob demanda. Use quando detectar dado velho.

    Args:
        tipo: cotacoes | fundamentos | macro | eventos
    """
    tipo = (tipo or "").strip().lower()
    try:
        if tipo == "cotacoes":
            from carteira_clean_web.backend.api import cache as ec
            ec.recalcular(no_api=False)
            return {"ok": True, "acao": "coleta_cotacoes", "nota": "Cotações atualizadas e engine recalculado."}
        if tipo == "fundamentos":
            from carteira_clean_web.backend.engine.fundamentals_client import salvar_fundamentos_db
            res = salvar_fundamentos_db()
            return {"ok": True, "acao": "coleta_fundamentos", "resultado": res}
        if tipo == "macro":
            from carteira_clean_web.backend.engine.macro_client import coletar_macro
            res = coletar_macro()
            return {"ok": True, "acao": "coleta_macro", "resultado": res}
        if tipo == "eventos":
            from carteira_clean_web.backend.engine.macro_client import coletar_eventos_corporativos
            res = coletar_eventos_corporativos()
            return {"ok": True, "acao": "coleta_eventos", "resultado": res}
        return {"erro": f"tipo inválido: {tipo}. Use cotacoes, fundamentos, macro ou eventos."}
    except Exception as exc:
        log.exception("Falha em forcar_coleta(%s)", tipo)
        return {"erro": f"Falha na coleta de {tipo}: {exc}"}


def fn_pesquisar_web(query: str, max_results: int = 5) -> dict:
    """Busca na internet via Brave Search API. Use para consenso de analistas,
    preço-alvo, notícias recentes, dados não disponíveis no banco interno.

    DISCIPLINA DE CITAÇÃO (obrigatória):
    - Sempre cite fonte (nome do site + URL) ao apresentar resultado.
    - Dado de web = "contexto externo não verificado".
    - Distinguir dado interno (banco) de externo (web).
    - Nunca apresentar dado de blog/fórum como research de casa de análise.
    - Ao citar casa de análise: "segundo a [casa], ..."

    HIERARQUIA DE FONTES — formular queries direcionadas:
    Tier 1 (dados/múltiplos): tradingview.com, investidor10.com.br,
      statusinvest.com.br, fundamentus.com.br
    Tier 2 (research BR): genialinvestimentos.com.br, nordinvestimentos.com.br,
      suno.com.br, kinea.com.br
    Tier 3 (oficial): b3.com.br, cvm.gov.br, bcb.gov.br
    Tier 4 (notícias): infomoney.com.br, valorinveste.globo.com
    Tier 5 (BDRs/int'l): finance.yahoo.com, seekingalpha.com

    Dica de query: "TICKER informação site:fonte.com" para resultados precisos.
    Ex: "ITUB3 preço alvo consenso site:tradingview.com"

    Args:
        query: texto da busca (formule queries específicas, idealmente com site:)
        max_results: número máximo de resultados (padrão 5, máximo 10)
    """
    import os
    import httpx

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return {"erro": "BRAVE_API_KEY não configurada no ambiente."}

    max_results = min(int(max_results or 5), 10)
    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max_results},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("web", {}).get("results", [])
        resultados = [
            {
                "titulo": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            }
            for r in raw
        ]
        return {
            "query": query,
            "total": len(resultados),
            "resultados": resultados,
            "nota": "Dados externos — citar fonte ao apresentar. Verificar credibilidade antes de usar.",
        }
    except httpx.HTTPStatusError as exc:
        return {"erro": f"Brave Search retornou erro HTTP {exc.response.status_code}: {exc.response.text[:200]}"}
    except Exception as exc:
        log.exception("Falha em pesquisar_web(%s)", query)
        return {"erro": f"Falha na busca web: {exc}"}
