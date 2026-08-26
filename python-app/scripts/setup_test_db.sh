#!/usr/bin/env bash
# Bootstraps a Postgres database with the REAL schema by replaying the retained
# V1..V17 PostgreSQL baseline, then applies the Alembic revisions layered on top
# of that baseline. The baseline is kept with the canonical Python app so local
# development and CI do not depend on the Java sister repository.
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

# Keep the app's own settings (used by Alembic's env.py) in sync with the
# psql connection above unless the caller already overrode them.
: "${DATABASE_URL:=jdbc:postgresql://$PGHOST:$PGPORT/$PGDATABASE}"
: "${DATABASE_USERNAME:=$PGUSER}"
: "${DATABASE_PASSWORD:=$PGPASSWORD}"
export DATABASE_URL DATABASE_USERNAME DATABASE_PASSWORD

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

echo "Applying Alembic revisions layered on top of the PostgreSQL baseline"
cd "$APP_DIR"
alembic upgrade head

echo "Test database ready."
