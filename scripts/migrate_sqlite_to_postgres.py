"""
migrate_sqlite_to_postgres.py

Migra TODOS os dados do SQLite para o PostgreSQL após o schema estar criado.

Uso (dentro do container backend):
  python3 scripts/migrate_sqlite_to_postgres.py \
    --sqlite /data/carteira.db \
    --pg "postgresql+psycopg2://carteira:SENHA@postgres:5432/carteira"

O script assume que 'alembic upgrade head' já rodou no PostgreSQL
(schema criado, seeds de cotacoes/benchmarks inseridos pela migration).

Estratégia por tabela:
  - ativos, eventos, decisoes, importacoes, importacao_evento,
    precos_manuais, conversas, mensagens, memorias_assistente,
    watchlist, agenda_eventos:
      INSERT simples (tabelas vazias no PG, criadas pelo create_all).

  - cotacoes, benchmarks, fundamentos, macro_indicadores:
      INSERT ... ON CONFLICT DO NOTHING
      (migrations já seedederam parte dos dados)

  - teses, diario_decisoes, regra_aportes, eventos_corporativos,
    metricas_comportamento, matriz_sensibilidade:
      INSERT simples (dados do usuário ou seed da migration 0008).

Tabelas ignoradas: sqlite_sequence, alembic_version.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from sqlalchemy import create_engine, inspect, text, MetaData, Table, Boolean

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate")

SKIP_TABLES = {"sqlite_sequence", "alembic_version"}

# Tabelas onde pode haver conflito com seeds das migrations
UPSERT_IGNORE = {"cotacoes", "benchmarks", "macro_indicadores", "fundamentos"}

# Ordem de inserção que respeita FKs (pai antes do filho)
TABLE_ORDER = [
    "ativos",
    "watchlist",
    "cotacoes",
    "benchmarks",
    "fundamentos",
    "teses",
    "eventos",
    "decisoes",
    "importacoes",
    "importacao_evento",
    "precos_manuais",
    "agenda_eventos",
    "diario_decisoes",
    "regra_aportes",
    "macro_indicadores",
    "eventos_corporativos",
    "metricas_comportamento",
    "matriz_sensibilidade",
    "conversas",
    "mensagens",
    "memorias_assistente",
]


def _coerce(val, col_type=None):
    """Converte tipos SQLite→Python compatíveis com PostgreSQL."""
    if col_type is not None and isinstance(col_type, Boolean) and isinstance(val, int):
        return bool(val)
    return val


def migrate(sqlite_url: str, pg_url: str, dry_run: bool = False):
    src = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    dst = create_engine(pg_url, pool_pre_ping=True)

    src_insp = inspect(src)
    dst_insp = inspect(dst)

    src_tables = set(src_insp.get_table_names())
    dst_tables = set(dst_insp.get_table_names())

    # Monta a lista na ordem definida + qualquer tabela que não esteja na lista
    ordered = [t for t in TABLE_ORDER if t in src_tables and t not in SKIP_TABLES]
    remaining = sorted(src_tables - set(ordered) - SKIP_TABLES)
    tables_to_migrate = ordered + remaining

    log.info("Tabelas a migrar: %s", tables_to_migrate)

    src_meta = MetaData()
    src_meta.reflect(bind=src)
    dst_meta = MetaData()
    dst_meta.reflect(bind=dst)

    with dst.begin() as dst_conn:
        # Desabilitar FKs temporariamente no PostgreSQL
        dst_conn.execute(text("SET session_replication_role = replica"))

        for tname in tables_to_migrate:
            if tname not in dst_tables:
                log.warning("  SKIP %s — não existe no PostgreSQL", tname)
                continue

            src_tbl = Table(tname, src_meta, autoload_with=src)

            with src.connect() as src_conn:
                rows = src_conn.execute(src_tbl.select()).fetchall()
                columns = [c.key for c in src_tbl.columns]

            if not rows:
                log.info("  %s — 0 linhas, pulando", tname)
                continue

            # Mapa de tipo de destino por coluna para coerção correta (ex: bool)
            dst_tbl = dst_meta.tables.get(tname)
            dst_col_types = {}
            if dst_tbl is not None:
                dst_col_types = {c.key: c.type for c in dst_tbl.columns}

            dicts = [
                {col: _coerce(val, dst_col_types.get(col)) for col, val in zip(columns, row)}
                for row in rows
            ]

            if dry_run:
                log.info("  [DRY] %s — %d linhas seriam inseridas", tname, len(dicts))
                continue

            if tname in UPSERT_IGNORE:
                # INSERT sem erro se a linha já existir (chave duplicada)
                col_str = ", ".join(f'"{c}"' for c in columns)
                ph_str  = ", ".join(f":{c}" for c in columns)
                pk_cols = inspect(src).get_pk_constraint(tname).get("constrained_columns", [])
                if pk_cols:
                    pk_str = ", ".join(f'"{c}"' for c in pk_cols)
                    stmt = text(
                        f'INSERT INTO "{tname}" ({col_str}) VALUES ({ph_str}) '
                        f"ON CONFLICT ({pk_str}) DO NOTHING"
                    )
                else:
                    stmt = text(f'INSERT INTO "{tname}" ({col_str}) VALUES ({ph_str})')
                dst_conn.execute(stmt, dicts)
                log.info("  %s — %d linhas (ON CONFLICT DO NOTHING)", tname, len(dicts))
            else:
                # Truncar + inserir
                dst_conn.execute(text(f'TRUNCATE TABLE "{tname}" RESTART IDENTITY CASCADE'))
                col_str = ", ".join(f'"{c}"' for c in columns)
                ph_str  = ", ".join(f":{c}" for c in columns)
                stmt = text(f'INSERT INTO "{tname}" ({col_str}) VALUES ({ph_str})')
                dst_conn.execute(stmt, dicts)
                log.info("  %s — %d linhas inseridas", tname, len(dicts))

        dst_conn.execute(text("SET session_replication_role = DEFAULT"))

    log.info("✅ Migração concluída.")


def main():
    parser = argparse.ArgumentParser(description="Migra dados SQLite → PostgreSQL")
    parser.add_argument("--sqlite", required=True, help="Caminho do SQLite (ex: /data/carteira.db)")
    parser.add_argument("--pg",     required=True, help="URL PostgreSQL (postgresql+psycopg2://...)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem inserir dados")
    args = parser.parse_args()

    sqlite_url = f"sqlite:///{args.sqlite}" if not args.sqlite.startswith("sqlite") else args.sqlite
    migrate(sqlite_url, args.pg, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
