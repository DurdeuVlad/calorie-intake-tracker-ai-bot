#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIRECTORY:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_dir}/foodjournal-${timestamp}.sql"

mkdir -p "${backup_dir}"
if [[ -e "${backup_file}" ]]; then
  echo "Refusing to overwrite ${backup_file}" >&2
  exit 1
fi

umask 077
docker compose exec -T postgres pg_dump --clean --if-exists --username foodjournal --dbname foodjournal > "${backup_file}"
echo "Created ${backup_file}. Encrypt and move it to protected storage."
