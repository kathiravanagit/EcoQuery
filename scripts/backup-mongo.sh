#!/bin/bash
# EcoQuery MongoDB Backup
# Run before demo day: bash scripts/backup-mongo.sh
# Requires: mongosh or mongodump in PATH

set -e

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUT_DIR="backups/ecoquery_${TIMESTAMP}"
mkdir -p "$OUT_DIR"

if [ -z "$MONGODB_URL" ]; then
  echo "Error: MONGODB_URL environment variable is required." >&2
  echo "Example: MONGODB_URL='mongodb+srv://...' bash scripts/backup-mongo.sh" >&2
  exit 1
fi

echo "==> Backing up EcoQuery MongoDB to $OUT_DIR"

mongodump \
  --uri="$MONGODB_URL" \
  --out="$OUT_DIR" \
  --gzip

echo "==> Backup complete: $OUT_DIR"
echo "    Collections: users, queries (ledger), contacts"
