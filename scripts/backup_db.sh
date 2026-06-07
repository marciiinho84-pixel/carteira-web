#!/bin/bash
# backup_db.sh — Backup consistente do carteira.db para Cloud Storage.
# Usa sqlite3.Connection.backup() via docker exec (backup online, sem travar escritas).
# Roda como cron 1x/dia; requer SA com storage.objectCreator no bucket.

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M)
PROJECT_DIR="/home/marciiinho84/carteira-web"
BUCKET="gs://carteira-backup-474073"
CONTAINER="carteira-web-backend-1"
TMP_IN_VOLUME="${PROJECT_DIR}/data/carteira_backup_tmp.db"
BACKUP_FILE="/tmp/carteira_${TIMESTAMP}.db"
LOG_FILE="${PROJECT_DIR}/data/backup.log"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"; }

log "=== Início backup ${TIMESTAMP} ==="

# 1. Backup consistente dentro do container (acessa /data montado)
log "Criando snapshot consistente do SQLite..."
sudo docker exec "$CONTAINER" python3 -c "
import sqlite3
src, dst = '/data/carteira.db', '/data/carteira_backup_tmp.db'
with sqlite3.connect(src) as con:
    bk = sqlite3.connect(dst)
    con.backup(bk)
    bk.close()
"
log "Snapshot criado em ${TMP_IN_VOLUME}"

# 2. Move para /tmp com nome datado (fora do bind mount)
mv "$TMP_IN_VOLUME" "$BACKUP_FILE"

# 3. Upload para GCS
log "Enviando para ${BUCKET}..."
/usr/bin/gcloud storage cp "$BACKUP_FILE" "${BUCKET}/"
log "Upload OK: ${BUCKET}/carteira_${TIMESTAMP}.db"

# 4. Limpa temporário
rm -f "$BACKUP_FILE"
log "=== Backup concluído ==="
