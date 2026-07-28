#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?Usage: RESTORE_CONFIRM=foodjournal bash docker/restore-postgres.sh backups/<dump>.sql}"
if [[ "${RESTORE_CONFIRM:-}" != "foodjournal" ]]; then
  echo "Set RESTORE_CONFIRM=foodjournal to acknowledge an isolated restore." >&2
  exit 1
fi
if [[ ! -f "${backup_file}" ]]; then
  echo "Backup file not found: ${backup_file}" >&2
  exit 1
fi

cat "${backup_file}" | docker compose exec -T postgres psql --set ON_ERROR_STOP=1 --username foodjournal --dbname foodjournal
echo "Restore completed. Verify Flyway history and journal data before using this database."
