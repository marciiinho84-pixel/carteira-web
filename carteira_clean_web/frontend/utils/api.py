"""
Cliente HTTP para a API FastAPI da Carteira Clean.
Todas as chamadas passam por aqui — tratamento de erro centralizado.
"""

import requests
import streamlit as st
from datetime import datetime

API_BASE = "http://localhost:8000/api/v1"
TIMEOUT_LEVE = 10
TIMEOUT_CALCULAR = 120
TIMEOUT_SINAIS = 90


def _url(endpoint: str) -> str:
    return f"{API_BASE}/{endpoint.lstrip('/')}"


def _tratar_erro(e: Exception, contexto: str = "") -> None:
    if isinstance(e, requests.exceptions.ConnectionError):
        st.error("❌ API não disponível. Verifique se o servidor está rodando na porta 8000.")
    elif isinstance(e, requests.exceptions.Timeout):
        st.error("⏱️ O servidor demorou demais para responder. Tente novamente.")
    elif isinstance(e, requests.exceptions.HTTPError):
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        st.error(f"❌ {contexto}: {detail}" if contexto else f"❌ {detail}")
    else:
        st.error(f"❌ Erro inesperado{' em ' + contexto if contexto else ''}: {str(e)}")


def get(endpoint: str, params: dict = None, timeout: int = TIMEOUT_LEVE) -> dict | list | None:
    try:
        r = requests.get(_url(endpoint), params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _tratar_erro(e, endpoint)
        return None


def post(endpoint: str, data: dict = None, params: dict = None) -> dict | None:
    try:
        r = requests.post(_url(endpoint), json=data, params=params,
                          timeout=TIMEOUT_CALCULAR)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _tratar_erro(e, endpoint)
        return None


def patch(endpoint: str, data: dict = None) -> dict | None:
    try:
        r = requests.patch(_url(endpoint), json=data, timeout=TIMEOUT_LEVE)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _tratar_erro(e, endpoint)
        return None


def delete(endpoint: str) -> bool:
    try:
        r = requests.delete(_url(endpoint), timeout=TIMEOUT_LEVE)
        r.raise_for_status()
        return True
    except Exception as e:
        _tratar_erro(e, endpoint)
        return False


# ─── Helpers de estado global ─────────────────────────────────────

def garantir_calculado(force: bool = False) -> bool:
    """Garante que o engine foi calculado. Recalcula se necessário.
    Retorna True se o estado está disponível."""
    status = get("status")
    if status is None:
        return False
    if status.get("n_eventos", 0) == 0 or force:
        with st.spinner("Calculando carteira..."):
            resultado = post("calcular", params={"no_api": "true"})
        if resultado and resultado.get("ok"):
            st.session_state["calculado_em"] = resultado.get("calculado_em", "")
            return True
        return False
    if "calculado_em" not in st.session_state:
        st.session_state["calculado_em"] = status.get("calculado_em", "")
    return True


def get_carteira_rv_dados() -> dict | None:
    """Consolida dados RV de múltiplos endpoints para a página Carteira RV."""
    posicoes_all = get("posicoes")
    rv_raw = get("carteira-rv")
    evo_all = get("evolucao")
    eventos_all = get("eventos")

    if posicoes_all is None or rv_raw is None or evo_all is None:
        return None
    eventos_all = eventos_all or []

    # Mapa setor por ticker (a partir do endpoint carteira-rv)
    ticker_setor: dict = {}
    for s in rv_raw.get("setores", []):
        for t in s.get("ativos", []):
            ticker_setor[t] = s["setor"]

    # Posições RV (excluindo FUNCEF, RF, Multimercado)
    posicoes_rv = [p for p in posicoes_all if p.get("classe") == "Renda Variável"]

    # Totais
    valor_atual = sum(p["valor_atual"] for p in posicoes_rv)
    var_dia_rv = sum((p.get("var_dia") or 0) for p in posicoes_rv)
    val_ontem = valor_atual - var_dia_rv
    var_dia_pct = var_dia_rv / val_ontem if val_ontem > 0 else 0.0

    # Movers
    rv_com_var = [p for p in posicoes_rv if p.get("var_dia_pct") is not None]
    _noop = {"ticker": "—", "pct": 0.0, "contrib_rs": 0.0}
    maior_alta = max(rv_com_var, key=lambda p: p["var_dia_pct"], default=None)
    maior_queda = min(rv_com_var, key=lambda p: p["var_dia_pct"], default=None)
    maior_impacto = max(posicoes_rv, key=lambda p: abs(p.get("var_dia") or 0), default=None)

    def _mover(p):
        if p is None:
            return dict(_noop)
        return {"ticker": p["ticker"], "pct": p.get("var_dia_pct") or 0.0,
                "contrib_rs": p.get("var_dia") or 0.0}

    # Posições enriquecidas para heatmap
    posicoes_out = [
        {
            "ticker": p["ticker"],
            "setor": ticker_setor.get(p["ticker"], "Outros"),
            "qtd": p["qtd"],
            "valor_atual": p["valor_atual"],
            "pct_rv": p["valor_atual"] / valor_atual if valor_atual > 0 else 0,
            "variacao_dia_pct": p.get("var_dia_pct") or 0.0,
            "contrib_dia_rs": p.get("var_dia") or 0.0,
            "pl_total_pct": p["pnl_pct"],
            "pl_total_rs": p["pnl"],
        }
        for p in posicoes_rv
    ]

    # Série de performance YTD (twr_rv, ibov, cdi em %)
    performance_serie = [
        {
            "time": r["data"],
            "twr_rv": round(float(r["twr_rv"]) * 100, 4),
            "ibov": round(float(r["ibov_acum"]) * 100, 4),
            "cdi": round(float(r["cdi_acum"]) * 100, 4),
        }
        for r in evo_all
    ]

    # Caixa
    caixa = {
        "atual": rv_raw["caixa_atual"],
        "entrando_d2": rv_raw["entrando_5d"],
        "saindo_d2": rv_raw["saindo_5d"],
        "projetado": rv_raw["saldo_projetado"],
    }

    # Setores com valor por ativo
    ticker_valor = {p["ticker"]: p["valor_atual"] for p in posicoes_rv}
    setores = []
    for s in rv_raw.get("setores", []):
        ativos_det = sorted(
            [{"ticker": t, "valor": ticker_valor.get(t, 0),
              "pct_setor": ticker_valor.get(t, 0) / s["valor"] if s["valor"] > 0 else 0}
             for t in s.get("ativos", [])],
            key=lambda x: -x["valor"],
        )
        setores.append({
            "nome": s["setor"],
            "valor_total": s["valor"],
            "pct_rv": s["pct_rv"],
            "ativos": ativos_det,
        })

    # Marcadores de compra/venda para o gráfico TV
    rv_tickers = {p["ticker"] for p in posicoes_rv}
    ops_por_data: dict = {}
    for ev in eventos_all:
        if ev.get("ativo") not in rv_tickers:
            continue
        if ev.get("tipo") not in ("COMPRA", "VENDA"):
            continue
        d = str(ev["data"])
        if d not in ops_por_data:
            ops_por_data[d] = {"COMPRA": [], "VENDA": []}
        ops_por_data[d][ev["tipo"]].append(ev["ativo"])

    markers = []
    for d, tipos in sorted(ops_por_data.items()):
        for tipo, tkrs in tipos.items():
            if tkrs:
                markers.append({
                    "time": d,
                    "tipo": tipo,
                    "label": tkrs[0] if len(tkrs) == 1 else f"{len(tkrs)}x",
                })

    # Concentração por ativo (top 5)
    top_concentracao = sorted(posicoes_out, key=lambda p: -p["pct_rv"])[:5]

    return {
        "valor_atual": valor_atual,
        "variacao_dia_valor": var_dia_rv,
        "variacao_dia_pct": var_dia_pct,
        "movers": {
            "maior_alta": _mover(maior_alta),
            "maior_queda": _mover(maior_queda),
            "maior_impacto": _mover(maior_impacto),
        },
        "posicoes": posicoes_out,
        "top_concentracao": top_concentracao,
        "markers": markers,
        "performance_serie": performance_serie,
        "caixa": caixa,
        "setores": setores,
    }


def get_agenda_eventos(dias: int = 30) -> list:
    """Retorna eventos de agenda nos próximos N dias, ordenados por data."""
    data = get(f"agenda?dias={dias}")
    if not data:
        return []
    return sorted(data, key=lambda x: x.get("data", ""))


def criar_agenda_evento(data_ev: str, ativo: str, tipo: str, descricao: str = "") -> dict | None:
    """Cria um evento de agenda."""
    return post("agenda", data={"data": data_ev, "ativo": ativo, "tipo": tipo, "descricao": descricao})


def deletar_agenda_evento(evento_id: int) -> bool:
    return delete(f"agenda/{evento_id}")


def put(endpoint: str, data: dict = None) -> dict | None:
    try:
        r = requests.put(_url(endpoint), json=data, timeout=TIMEOUT_LEVE)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        _tratar_erro(e, endpoint)
        return None


def get_watchlist() -> list:
    return get("watchlist") or []


def post_watchlist(data: dict) -> dict | None:
    return post("watchlist", data=data)


def delete_watchlist(item_id: int) -> bool:
    return delete(f"watchlist/{item_id}")


def get_sinais(tickers: list[str], apenas_ativos: bool = True) -> list:
    data = get("sinais", params={
        "tickers": ",".join(tickers),
        "apenas_ativos": str(apenas_ativos).lower(),
    }, timeout=TIMEOUT_SINAIS)
    return data or []


def get_sinais_carteira_rv(apenas_ativos: bool = True) -> list:
    data = get("sinais/carteira_rv",
               params={"apenas_ativos": str(apenas_ativos).lower()},
               timeout=TIMEOUT_SINAIS)
    return data or []


def get_diario_recentes(limit: int = 3) -> list:
    """Retorna as N decisões mais recentes do diário."""
    data = get("decisoes")
    if not data:
        return []
    return sorted(data, key=lambda x: x.get("data_decisao", ""), reverse=True)[:limit]


def tempo_desde_calculo() -> str:
    """Retorna string legível do tempo desde o último cálculo."""
    calc_em = st.session_state.get("calculado_em", "")
    if not calc_em:
        return "nunca calculado"
    try:
        dt = datetime.fromisoformat(calc_em)
        delta = datetime.now() - dt
        s = int(delta.total_seconds())
        if s < 60:
            return f"{s}s atrás"
        if s < 3600:
            return f"{s // 60}min atrás"
        return f"{s // 3600}h atrás"
    except Exception:
        return "calculado"
