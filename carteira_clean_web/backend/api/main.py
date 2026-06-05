"""
main.py — App FastAPI da Carteira Clean.

Executa com:
    python -m carteira_clean_web.backend.api.main
    ou
    uvicorn carteira_clean_web.backend.api.main:app --reload
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from carteira_clean_web.backend.api.routers import (
    ativos, eventos, precos_manuais, calcular, resultados, backup, decisoes, importacao, agenda,
    watchlist, sinais, memoria,
)

log = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: carrega o último resultado do cache em disco.
    Se o cache não existir (primeira execução), recalcula localmente.
    Assim cotações buscadas via API persistem entre restarts.
    """
    # Cria tabelas novas sem afetar as existentes
    from carteira_clean_web.backend.db.models import Base
    from carteira_clean_web.backend.db.session import get_engine
    from sqlalchemy import text
    engine = get_engine()
    Base.metadata.create_all(engine)

    # Migração inline — adiciona colunas novas sem Alembic
    _ddls = [
        "ALTER TABLE conversas ADD COLUMN resumo_historico TEXT",
        "ALTER TABLE mensagens ADD COLUMN incluida_no_resumo INTEGER NOT NULL DEFAULT 0",
    ]
    with engine.connect() as conn:
        for ddl in _ddls:
            try:
                conn.execute(text(ddl))
                conn.commit()
            except Exception:
                pass  # coluna já existe

    from carteira_clean_web.backend.api import cache as engine_cache
    if engine_cache.carregar_disco():
        log.info("Startup: cache carregado do disco — pronto imediatamente")
    else:
        log.info("Startup: sem cache em disco — primeiro boot, buscando preços externos...")
        try:
            engine_cache.recalcular(no_api=False)
            log.info("Startup: engine calculado com API e salvo em disco")
        except Exception as e:
            log.warning(f"Startup engine falhou (não crítico): {e}")
    yield


app = FastAPI(
    title="Carteira Clean API",
    description=(
        "API REST do projeto Carteira Clean. "
        "O engine é inicializado automaticamente na startup."
    ),
    version="2.5.1",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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
app.include_router(agenda.router, prefix=PREFIX)
app.include_router(watchlist.router, prefix=PREFIX)
app.include_router(sinais.router, prefix=PREFIX)
app.include_router(memoria.router, prefix=PREFIX)


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
