# Backup & Restore Runbook

Nightly encrypted backups via `backup.sh`, uploaded to
`s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/` with a monthly duplicate for
the 6-year HIPAA retention floor.

## Nightly backup (automated)

Cron on the host runs `backup.sh` at 02:07 local. What it does:

1. `pg_dump | gzip -9` → temp file
2. `age -r $BACKUP_ENCRYPTION_RECIPIENT` → `<file>.age`
3. `aws s3 cp --sse AES256` → `daily/YYYY-MM-DD.sql.gz.age`
4. If `date -u +%d` == "01", also copy to `monthly/YYYY-MM.sql.gz.age`

Rotation is delegated to S3 lifecycle policy — the script does not delete.

## Verify backups are actually running

- `aws s3 ls s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/daily/ | tail -5` —
  the newest key should be within 26 hours. If not, backups are broken.
- Cloudwatch (or provider equivalent) alarm on missing object age > 26 h
  in the daily/ prefix. Configure this — the script cannot alert on its
  own absence.

## Test restore (quarterly — required)

A backup you have never restored is not a backup. Do this every quarter:

1. Provision a scratch Postgres instance (docker run is fine, do NOT
   restore into production).
2. Pull the latest backup:
   ```bash
   aws s3 cp s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/daily/<latest>.sql.gz.age .
   age --decrypt -i $AGE_IDENTITY_FILE <latest>.sql.gz.age | gunzip > restore.sql
   psql -h <scratch-host> -U postgres -d postgres -c "CREATE DATABASE restore_test"
   psql -h <scratch-host> -U postgres -d restore_test -f restore.sql
   ```
3. Run `SELECT COUNT(*) FROM patient; SELECT MAX(created_at) FROM appointment;`
   — sanity checks that the restore has current-day data.
4. Drop the scratch DB. Log the exercise in `docs/hipaa/audit-log.md` (date,
   who ran it, outcome, any issues found).

## Restore from backup (real incident)

Assume a scenario where production DB is corrupted or unrecoverable.

1. **Declare an incident** per `incident-response.md`. Restoration is a
   SEV1 event by default.
2. **Freeze writes.** Put nginx in maintenance mode so no new writes land.
3. **Snapshot current corrupted state** if any part of the DB is readable —
   forensics.
4. **Provision replacement Postgres** with the same version (16.x). Enable
   TDE + LUKS BEFORE loading data.
5. **Restore** using the same commands as the test-restore procedure, but
   pointed at the replacement instance and the DATABASE the app expects.
6. **Verify** row counts against the last known-good `monthly/` backup:
   ```sql
   SELECT 'patient' AS t, COUNT(*) FROM patient
   UNION ALL SELECT 'appointment', COUNT(*) FROM appointment
   UNION ALL SELECT 'activity_log', COUNT(*) FROM activity_log;
   ```
   Compare to the pre-incident counts if available.
7. **Point backend at new DB** (update `DATABASE_URL`, `docker compose up -d`).
8. **Lift nginx maintenance**.
9. **Reconcile lost writes.** Any writes between the backup timestamp and
   the incident are lost. Notify the covered entity so they can decide who
   to contact (patients whose appointments were booked in the gap).

## Recovery point / time objectives

- **RPO** — 24 hours. Nightly backup; anything written since is lost on
  restore. Practices needing tighter RPO must use provider PITR (point-in-
  time recovery) on their managed Postgres, which is out of scope for this
  script.
- **RTO** — 4 hours. Restore of a fresh DB from `daily/` object, verified
  with row-count checks, and traffic re-enabled.

## Key management

The age recipient private key (`age-keygen -o key.txt`) is:
- Held ONLY by the on-call ops role — not stored in the repo, not in
  Postgres, not in the object storage bucket
- Backed up in the covered entity's password manager under "hipaa-scheduler
  age recipient"
- Rotated annually; re-encryption of archived backups in the same PR that
  rotates
- Loss = permanent inability to restore. Loss to unauthorized party =
  SEV1 incident under `incident-response.md` T7 pattern

## Do NOT

- Do NOT copy backup files onto workstations to "look at". If you need to
  inspect a backup, spin up a scratch instance and query it.
- Do NOT store the age private key in the same S3 bucket as the backups.
  Defeats the encryption.
- Do NOT skip the quarterly restore drill because "it worked last time".
  Log a completed exercise every 90 days or the audit will flag it.
