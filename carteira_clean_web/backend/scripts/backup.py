"""
Backup do banco PostgreSQL da Carteira Clean.

Funções públicas:
  fazer_backup()          → pg_dump em /data/backups/ e loga
  listar_backups(n)       → últimos N backups com tamanho e data
  backup_se_necessario()  → faz backup apenas se não houver um hoje
"""

import logging
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

_HERE = Path(__file__).resolve().parent
_LOG_DIR = _HERE.parent / "logs"

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/data/backups"))
MAX_BACKUPS = 30


def _pg_params() -> dict:
    raw = os.environ.get("DATABASE_URL", "")
    u = urlparse(raw.replace("postgresql+psycopg2", "postgresql"))
    return {
        "host": u.hostname or "postgres",
        "port": str(u.port or 5432),
        "user": u.username or "carteira",
        "password": u.password or "",
        "db": (u.path or "/carteira").lstrip("/"),
    }


def fazer_backup() -> dict:
    """pg_dump do PostgreSQL para BACKUP_DIR/carteira-YYYYMMDD-HHMMSS.dump.
    Mantém os últimos MAX_BACKUPS, apaga os mais antigos.
    Retorna dict com arquivo, tamanho e timestamp."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"carteira-{ts}.dump"

    p = _pg_params()
    env = {**os.environ, "PGPASSWORD": p["password"]}
    cmd = [
        "pg_dump",
        f"--host={p['host']}",
        f"--port={p['port']}",
        f"--username={p['user']}",
        f"--dbname={p['db']}",
        "--format=custom",
        "--compress=9",
        f"--file={dest}",
    ]
    result = subprocess.run(cmd, env=env, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump falhou (código {result.returncode}): {result.stderr.decode()}")

    # Purge antigos
    todos = sorted(BACKUP_DIR.glob("carteira-*.dump"), reverse=True)
    for antigo in todos[MAX_BACKUPS:]:
        antigo.unlink(missing_ok=True)

    tamanho = dest.stat().st_size
    _logar(f"Backup criado: {dest.name} ({tamanho:,} bytes)")

    return {
        "arquivo": dest.name,
        "tamanho_bytes": tamanho,
        "criado_em": ts,
    }


def listar_backups(limit: int = 5) -> list[dict]:
    """Retorna os últimos `limit` backups com nome, tamanho e data."""
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("carteira-*.dump"), reverse=True)
    result = []
    for b in backups[:limit]:
        stat = b.stat()
        result.append({
            "arquivo": b.name,
            "tamanho_bytes": stat.st_size,
            "criado_em": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result


def backup_se_necessario() -> bool:
    """Faz backup apenas se ainda não houver um com data de hoje.
    Retorna True se um novo backup foi criado, False se já existia."""
    hoje = date.today().strftime("%Y%m%d")
    if BACKUP_DIR.exists() and list(BACKUP_DIR.glob(f"carteira-{hoje}*.dump")):
        return False
    try:
        fazer_backup()
        return True
    except Exception as exc:
        _logar(f"ERRO ao fazer backup automático: {exc}", level=logging.ERROR)
        return False


def _logar(msg: str, level: int = logging.INFO) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("carteira.backup")
    if not logger.handlers:
        handler = logging.FileHandler(_LOG_DIR / "backup.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    logger.log(level, msg)
