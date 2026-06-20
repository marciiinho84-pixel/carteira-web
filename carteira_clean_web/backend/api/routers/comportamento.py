"""
routers/comportamento.py — Endpoints de perfil comportamental e dito-vs-feito.

GET  /comportamento/perfil   → métricas comportamentais (Fatia 8)
GET  /comportamento/divergencias → cruzamento dito-vs-feito (Fatia 9)
"""
from fastapi import APIRouter, Query

router = APIRouter(tags=["comportamento"])


@router.get("/comportamento/perfil")
def get_perfil_comportamental(
    metrica: str = Query(default="todos",
                         description="turnover | holding | frequencia | concentracao | todos"),
    periodo_meses: int = Query(default=12, ge=1, le=60),
):
    from carteira_clean_web.backend.mcp.tools.portfolio import fn_perfil_comportamental
    return fn_perfil_comportamental(metrica=metrica, periodo_meses=periodo_meses)


@router.get("/comportamento/divergencias")
def get_divergencias(
    tipo: str = Query(default="todos",
                      description="horizonte | alocacao | conviccao | invalidacao | todos"),
    periodo_meses: int = Query(default=6, ge=1, le=60),
):
    from carteira_clean_web.backend.mcp.tools.portfolio import fn_divergencias_dito_feito
    return fn_divergencias_dito_feito(tipo=tipo, periodo_meses=periodo_meses)
