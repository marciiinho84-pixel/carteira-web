"""
main.py — App FastAPI da Carteira Clean.

Executa com:
    python -m carteira_clean_web.backend.api.main
    ou
    uvicorn carteira_clean_web.backend.api.main:app --reload
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from carteira_clean_web.backend.api.routers import (
    ativos, eventos, precos_manuais, calcular, resultados, backup, decisoes, importacao,
)

app = FastAPI(
    title="Carteira Clean API",
    description=(
        "API REST do projeto Carteira Clean. "
        "Chame POST /api/v1/calcular antes de acessar os endpoints de resultados."
    ),
    version="2.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/v1"

app.include_router(ativos.router, prefix=PREFIX)
app.include_router(eventos.router, prefix=PREFIX)
app.include_router(precos_manuais.router, prefix=PREFIX)
app.include_router(calcular.router, prefix=PREFIX)
app.include_router(resultados.router, prefix=PREFIX)
app.include_router(backup.router, prefix=PREFIX)
app.include_router(decisoes.router, prefix=PREFIX)
app.include_router(importacao.router, prefix=PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {
        "projeto": "Carteira Clean",
        "versao": "2.2.0",
        "docs": "/docs",
        "dica": "Chame POST /api/v1/calcular para inicializar o engine.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("carteira_clean_web.backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
