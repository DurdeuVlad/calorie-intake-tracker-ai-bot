#!/usr/bin/env bash
# Replays only the retained PostgreSQL V1..V17 baseline SQL. Alembic
# revisions layered on top are intentionally left unapplied here -- the
# application applies them itself on boot (see run.py). CI uses this script
# alone, without setup_test_db.sh's alembic step, to prove that self-migration
# path actually works.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$APP_DIR/alembic/flyway_baseline"

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGUSER:=foodjournal}"
: "${PGPASSWORD:=foodjournal}"
: "${PGDATABASE:=foodjournal}"
export PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE

echo "Waiting for Postgres at $PGHOST:$PGPORT..."
for _ in $(seq 1 30); do
  if pg_isready -q; then break; fi
  sleep 1
done

echo "Replaying PostgreSQL baseline migrations V1..V17 from $MIGRATIONS_DIR"
for n in $(seq 1 17); do
  file=$(ls "$MIGRATIONS_DIR"/V${n}__*.sql)
  echo "  applying $(basename "$file")"
  psql -v ON_ERROR_STOP=1 -q -f "$file"
done
