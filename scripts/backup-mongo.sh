#!/bin/bash
# EcoQuery MongoDB Backup
# Run before demo day: bash scripts/backup-mongo.sh
# Requires: mongosh or mongodump in PATH

set -e

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUT_DIR="backups/ecoquery_${TIMESTAMP}"
mkdir -p "$OUT_DIR"

MONGO_URL="${MONGODB_URL:-mongodb+srv://kathiravanawork_db_user:***@cluster0.zk5nkqw.mongodb.net/ecoquery}"

echo "==> Backing up EcoQuery MongoDB to $OUT_DIR"

mongodump \
  --uri="$MONGO_URL" \
  --out="$OUT_DIR" \
  --gzip

echo "==> Backup complete: $OUT_DIR"
echo "    Collections: users, queries (ledger), contacts"
echo "==> To restore: mongorestore --uri=\"$MONGO_URL\" \"$OUT_DIR\" --gzip"
