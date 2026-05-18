"""
POST /api/v1/calcular   — força recálculo do engine
GET  /api/v1/status     — último cálculo, alertas pendentes
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from carteira_clean_web.backend.api import cache as engine_cache
from carteira_clean_web.backend.api.schemas import StatusOut, AlertaOut

router = APIRouter(tags=["Engine"])


@router.post("/calcular", status_code=200)
def calcular(no_api: bool = Query(False, description="Se True, pula download de preços externos")):
    """Roda o engine completo. Obrigatório antes de acessar /posicoes, /evolucao, etc."""
    try:
        resultado = engine_cache.recalcular(no_api=no_api)
        ult = resultado["df_evo"].iloc[-1] if not resultado["df_evo"].empty else None
        return {
            "ok": True,
            "calculado_em": engine_cache.get_calculado_em().isoformat(),
            "data_referencia": str(ult["data"]) if ult is not None else None,
            "n_eventos": len(resultado["eventos"]),
            "n_ativos": len(resultado["ativos"]),
            "patrimonio_total": round(ult["patrimonio_total"], 2) if ult is not None else None,
            "pnl_vendas_rv": round(sum(v["pnl"] for v in resultado["vendas_rv"]), 2),
            "n_alertas": len(resultado["alertas"]),
        }
    except Exception as e:
        raise HTTPException(500, f"Erro no engine: {str(e)}")


@router.get("/status", response_model=StatusOut)
def status():
    """Retorna status do último cálculo e lista de alertas."""
    if not engine_cache.esta_calculado():
        erro = engine_cache.get_erro()
        return StatusOut(
            erro=erro or "Engine ainda não foi calculado. Chame POST /api/v1/calcular primeiro.",
        )
    estado = engine_cache.get_estado()
    calc_em = engine_cache.get_calculado_em()
    alertas = [
        AlertaOut(nivel=a[0], ativo=a[1], mensagem=a[2])
        for a in estado.get("alertas", [])
    ]
    return StatusOut(
        calculado_em=calc_em.isoformat() if calc_em else None,
        data_referencia=str(estado["hoje"]) if "hoje" in estado else None,
        n_eventos=len(estado.get("eventos", [])),
        n_ativos=len(estado.get("ativos", {})),
        alertas=alertas,
    )
