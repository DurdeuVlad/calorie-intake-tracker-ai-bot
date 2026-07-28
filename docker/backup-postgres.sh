#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIRECTORY:-backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_dir}/foodjournal-${timestamp}.sql"
temporary_file="${backup_file}.partial.$$"

umask 077
mkdir -p "${backup_dir}"
if [[ -e "${backup_file}" ]]; then
  echo "Refusing to overwrite ${backup_file}" >&2
  exit 1
fi

trap 'rm -f "${temporary_file}"' EXIT
docker compose exec -T postgres pg_dump --clean --if-exists --username foodjournal --dbname foodjournal > "${temporary_file}"
mv "${temporary_file}" "${backup_file}"
trap - EXIT
echo "Created ${backup_file}. Encrypt and move it to protected storage."
