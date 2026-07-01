#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# HIPAA Scheduler — encrypted Postgres backup
#
# Runs a pg_dump against the compose `postgres` service, encrypts the dump
# with age using the recipient public key, and uploads to S3-compatible
# storage. Designed to run under cron on the Docker host, NOT inside the
# container network:
#
#   0 2 * * *  /opt/hipaa-scheduler/backup.sh >> /var/log/hs-backup.log 2>&1
#
# Retention: 35 daily + 6 monthly (first-of-month copy stays 6 years to meet
# HIPAA audit retention). Retention pruning is expected to be enforced by
# object storage lifecycle rules; this script does not delete.
#
# Requirements on host: docker, awscli (or s5cmd), age.
# All secrets are read from .env in the same directory as this script.
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "backup.sh: .env not found in $SCRIPT_DIR" >&2
  exit 1
fi

: "${POSTGRES_USER:?POSTGRES_USER required}"
: "${POSTGRES_DB:?POSTGRES_DB required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET required}"
: "${BACKUP_ENCRYPTION_RECIPIENT:?BACKUP_ENCRYPTION_RECIPIENT (age public key) required}"

BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-hipaa-scheduler/postgres}"
S3_ENDPOINT_ARG=""
if [[ -n "${S3_ENDPOINT:-}" ]]; then
  S3_ENDPOINT_ARG="--endpoint-url ${S3_ENDPOINT}"
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
DAY="$(date -u +%Y-%m-%d)"
DOM="$(date -u +%d)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

DUMP="$TMP/hs-${TS}.sql.gz"
ENC="$DUMP.age"

echo "[$(date -u +%FT%TZ)] pg_dump start"
docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain --no-owner --no-privileges \
  | gzip -9 > "$DUMP"

DUMP_SIZE=$(stat -c%s "$DUMP" 2>/dev/null || stat -f%z "$DUMP")
echo "[$(date -u +%FT%TZ)] pg_dump complete (${DUMP_SIZE} bytes) — encrypting"

age -r "$BACKUP_ENCRYPTION_RECIPIENT" -o "$ENC" "$DUMP"
rm -f "$DUMP"

echo "[$(date -u +%FT%TZ)] uploading daily copy"
# shellcheck disable=SC2086
aws s3 cp $S3_ENDPOINT_ARG "$ENC" \
  "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/daily/${DAY}/hs-${TS}.sql.gz.age" \
  --sse AES256 --only-show-errors

# First of month → also drop into monthly/ (lifecycle rules keep 6 years there)
if [[ "$DOM" == "01" ]]; then
  echo "[$(date -u +%FT%TZ)] first-of-month, uploading monthly copy"
  # shellcheck disable=SC2086
  aws s3 cp $S3_ENDPOINT_ARG "$ENC" \
    "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/monthly/${DAY}/hs-${TS}.sql.gz.age" \
    --sse AES256 --only-show-errors
fi

echo "[$(date -u +%FT%TZ)] backup complete"
