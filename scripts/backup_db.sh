#!/bin/bash
# backup_db.sh — Backup do PostgreSQL para Cloud Storage.
# Usa pg_dump via postgres container; upload direto para GCS.
# Cron: 0 22 * * * /home/marciiinho84/carteira-web/scripts/backup_db.sh >> /home/marciiinho84/logs/backup.log 2>&1

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M)
PROJECT_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
BUCKET="gs://carteira-backup-474073"
BACKUP_FILE="/tmp/carteira_${TIMESTAMP}.dump"
LOG_DIR="${HOME}/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/backup.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"; }

log "=== Início backup ${TIMESTAMP} ==="

# pg_dump dentro do container postgres (já tem pg_dump nativo).
# $POSTGRES_PASSWORD está no ambiente do container.
sudo docker exec -T carteira-web-postgres-1 \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U carteira -d carteira --format=custom --compress=9' \
    > "$BACKUP_FILE"

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Dump criado: ${BACKUP_FILE} (${SIZE})"

# Upload para GCS
/usr/bin/gcloud storage cp "$BACKUP_FILE" "${BUCKET}/carteira_${TIMESTAMP}.dump"
log "Upload OK: ${BUCKET}/carteira_${TIMESTAMP}.dump"

# Limpa temporário local
rm -f "$BACKUP_FILE"
log "=== Backup concluído ==="
