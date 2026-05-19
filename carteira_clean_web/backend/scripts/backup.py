"""
Backup automático do banco SQLite da Carteira Clean.

Funções públicas:
  fazer_backup()          → cria backup em ~/Carteira/backups/ e loga
  listar_backups(n)       → últimos N backups com tamanho e data
  backup_se_necessario()  → faz backup apenas se não houver um hoje
"""

import logging
import shutil
from datetime import date, datetime
from pathlib import Path

# Caminhos
_HERE = Path(__file__).resolve().parent          # .../backend/scripts/
_DB_PATH = _HERE.parent.parent / "carteira.db"  # .../carteira_clean_web/carteira.db
_LOG_DIR = _HERE.parent / "logs"                # .../backend/logs/

BACKUP_DIR = Path.home() / "Carteira" / "backups"
MAX_BACKUPS = 30


def fazer_backup(db_path: Path | None = None) -> dict:
    """Copia o banco para ~/Carteira/backups/carteira-YYYYMMDD-HHMMSS.db.
    Mantém os últimos MAX_BACKUPS, apaga os mais antigos.
    Retorna dict com arquivo, tamanho e timestamp."""
    src = Path(db_path) if db_path else _DB_PATH
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = BACKUP_DIR / f"carteira-{ts}.db"
    shutil.copy2(src, dest)

    # Purge antigos
    todos = sorted(BACKUP_DIR.glob("carteira-*.db"), reverse=True)
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
    backups = sorted(BACKUP_DIR.glob("carteira-*.db"), reverse=True)
    result = []
    for b in backups[:limit]:
        stat = b.stat()
        result.append({
            "arquivo": b.name,
            "tamanho_bytes": stat.st_size,
            "criado_em": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return result


def backup_se_necessario(db_path: Path | None = None) -> bool:
    """Faz backup apenas se ainda não houver um com data de hoje.
    Retorna True se um novo backup foi criado, False se já existia."""
    hoje = date.today().strftime("%Y%m%d")
    if BACKUP_DIR.exists() and list(BACKUP_DIR.glob(f"carteira-{hoje}*.db")):
        return False
    try:
        fazer_backup(db_path)
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
