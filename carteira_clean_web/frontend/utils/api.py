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


def get(endpoint: str, params: dict = None) -> dict | list | None:
    try:
        r = requests.get(_url(endpoint), params=params, timeout=TIMEOUT_LEVE)
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
