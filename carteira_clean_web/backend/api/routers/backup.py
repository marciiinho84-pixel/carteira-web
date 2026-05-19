"""
POST /api/v1/backup          → cria backup imediato
GET  /api/v1/backup/listar   → últimos 5 backups
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from carteira_clean_web.backend.scripts.backup import fazer_backup, listar_backups

router = APIRouter(prefix="/backup", tags=["Backup"])


@router.post("", status_code=201)
def criar_backup():
    """Cria backup imediato do banco SQLite."""
    try:
        info = fazer_backup()
        return {"ok": True, **info}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"ok": False, "erro": str(exc)})


@router.get("/listar")
def listar(limit: int = 5):
    """Lista os últimos N backups disponíveis."""
    return listar_backups(limit=limit)
