import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# Garante que carteira_clean_web/ seja importável a partir do projeto raiz
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

config = context.config
fileConfig(config.config_file_name)

# ── URL do banco ────────────────────────────────────────────────────────────
# Prioridade: DB_PATH env var (Docker) → default igual ao session.py
_db_env = os.environ.get("DB_PATH")
if _db_env:
    _url = f"sqlite:///{_db_env}"
else:
    # Mirrors session.py: carteira_clean_web/carteira.db (relativo à raiz do projeto)
    _default = Path(__file__).resolve().parents[1] / "carteira_clean_web" / "carteira.db"
    _url = f"sqlite:///{_default}"

config.set_main_option("sqlalchemy.url", _url)

# ── Metadata para autogenerate (opcional — não usado neste projeto ainda) ───
from carteira_clean_web.backend.db.models import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
