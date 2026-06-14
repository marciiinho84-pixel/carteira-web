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

        # Preço atual
        preco_atual = None
        if familia in COTIZADO_PUBLICO:
            preco_atual = preco_em(precos_pub.get(tkr, {}), hoje)
        if preco_atual is None:
            preco_atual = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)

        # Valor atual
        if familia in AGREGADO_PRIVADO:
            valor_atual = preco_atual if preco_atual else p.custo_total
        else:
            valor_atual = p.qtd * preco_atual if preco_atual else p.custo_total

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

        preco_atual = None
        if familia in COTIZADO_PUBLICO:
            preco_atual = preco_em(precos_pub.get(tkr, {}), hoje)
        if preco_atual is None:
            preco_atual = preco_em(precos_man.get(tkr, {}), hoje, max_lookback_dias=60)

        if familia in AGREGADO_PRIVADO:
            valor_atual = preco_atual if preco_atual else p.custo_total
        else:
            valor_atual = p.qtd * preco_atual if preco_atual else p.custo_total

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
