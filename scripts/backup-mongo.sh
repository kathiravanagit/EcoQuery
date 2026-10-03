#!/bin/bash
# EcoQuery MongoDB Backup
#   bash scripts/backup-mongo.sh
# Requires: mongodump in PATH (MongoDB Database Tools)
#
# Restores are tested, not assumed:
#   python scripts/verify_backup_restore.py
# runs a full dump -> drop -> restore -> compare cycle against throwaway
# databases. Run it after changing this script or upgrading the tools.

set -euo pipefail

# No fallback URI. A default here once meant an unset MONGODB_URL quietly
# backed up whatever that hardcoded value pointed at while printing
# "Backup complete" -- the operator's belief and the reality on disk going
# different ways. Refusing is the only safe answer.
if [ -z "${MONGODB_URL:-}" ]; then
  echo "ERROR: MONGODB_URL is not set." >&2
  echo "  export MONGODB_URL='mongodb+srv://...'" >&2
  echo "  (the connection string lives in Render's environment, not in this repo)" >&2
  exit 2
fi

if ! command -v mongodump >/dev/null 2>&1; then
  echo "ERROR: mongodump not found. Install the MongoDB Database Tools:" >&2
  echo "  https://www.mongodb.com/try/download/database-tools" >&2
  exit 2
fi

TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
OUT_DIR="backups/ecoquery_${TIMESTAMP}"
mkdir -p "$OUT_DIR"

echo "==> Backing up EcoQuery MongoDB to $OUT_DIR"

mongodump \
  --uri="$MONGODB_URL" \
  --out="$OUT_DIR" \
  --gzip

# mongodump exits zero having written nothing -- an empty dump and a healthy
# one look identical to `$?`. Count the collections before claiming success.
BSON_COUNT=$(find "$OUT_DIR" -name '*.bson.gz' 2>/dev/null | wc -l | tr -d ' ')
if [ "$BSON_COUNT" -eq 0 ]; then
  echo "ERROR: mongodump produced no collections. $OUT_DIR is not a backup." >&2
  exit 1
fi

echo "==> Backup complete: $OUT_DIR ($BSON_COUNT collections, gzipped)"
# Taken from the dump rather than a list someone would have to remember to
# update: the names in this script had already drifted from the database.
COLLECTIONS=$(find "$OUT_DIR" -name '*.bson.gz' | sed -e 's#^.*/##' -e 's/\.bson\.gz$//' | sort | tr '\n' ' ')
echo "    Collections: $COLLECTIONS"
echo "    (backups/ is gitignored -- the dump never enters the repository)"
echo
echo "==> To verify a backup really restores:"
echo "      python scripts/verify_backup_restore.py"
echo "==> To restore it over the database it came from:"
echo "      mongorestore --uri=\"\$MONGODB_URL\" --gzip --drop --dir=\"$OUT_DIR\""
echo "    --drop replaces the existing collections first. Without it every"
echo "    document fails on a duplicate _id and mongorestore still exits 0"
echo "    having restored nothing, so confirm with a count afterwards:"
echo "      mongosh \"\$MONGODB_URL\" --eval 'db.users.countDocuments()'"
