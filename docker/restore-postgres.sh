#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?Usage: RESTORE_CONFIRM=foodjournal bash docker/restore-postgres.sh backups/<dump>.sql}"
restore_database="${RESTORE_DATABASE:-foodjournal_restore}"
if [[ ! "${restore_database}" =~ ^[a-z0-9_]+$ ]] || [[ "${restore_database}" == "foodjournal" ]] || [[ "${restore_database}" == "postgres" ]] || [[ "${restore_database}" == template0 ]] || [[ "${restore_database}" == template1 ]]; then
  echo "RESTORE_DATABASE must be a safe lowercase name other than foodjournal or a system database." >&2
  exit 1
fi
if [[ "${RESTORE_CONFIRM:-}" != "${restore_database}" ]]; then
  echo "Set RESTORE_CONFIRM=${restore_database} to acknowledge replacing that isolated restore database." >&2
  exit 1
fi
if [[ ! -f "${backup_file}" ]]; then
  echo "Backup file not found: ${backup_file}" >&2
  exit 1
fi

docker compose -f python-app/compose.yaml exec -T postgres dropdb --if-exists --username foodjournal "${restore_database}"
docker compose -f python-app/compose.yaml exec -T postgres createdb --username foodjournal "${restore_database}"
cat "${backup_file}" | docker compose -f python-app/compose.yaml exec -T postgres psql --set ON_ERROR_STOP=1 --username foodjournal --dbname "${restore_database}"
echo "Restore completed in isolated database ${restore_database}. Verify migration history and journal data before using it."
