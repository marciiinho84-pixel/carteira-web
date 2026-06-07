# Restauração do banco carteira.db

## Listar backups disponíveis

```bash
gcloud storage ls gs://carteira-backup-474073/
```

## Restaurar (procedimento completo)

```bash
# 1. Baixar o backup desejado (substitua DATA pelo nome do arquivo)
gcloud storage cp gs://carteira-backup-474073/carteira_YYYYMMDD_HHMM.db /tmp/

# 2. Parar os containers (para evitar escrita durante a troca)
cd ~/carteira-web
sudo docker compose down

# 3. Preservar o banco corrompido antes de sobrescrever
cp ./data/carteira.db ./data/carteira.db.bak_$(date +%Y%m%d)

# 4. Substituir pelo backup
cp /tmp/carteira_YYYYMMDD_HHMM.db ./data/carteira.db

# 5. Subir novamente
sudo docker compose up -d

# 6. Confirmar que o backend ficou healthy
sudo docker compose ps
```

## Verificar integridade do backup antes de restaurar

```bash
sqlite3 /tmp/carteira_YYYYMMDD_HHMM.db "PRAGMA integrity_check; SELECT name FROM sqlite_master WHERE type='table';"
```

## Localização dos backups

- Bucket: `gs://carteira-backup-474073` (us-central1, privado)
- Retenção: 90 dias (lifecycle delete automático)
- Frequência: diária às 03h30 (cron na VM)
- Log local: `~/carteira-web/data/backup.log`
