#!/usr/bin/env bash
# Bootstraps a Postgres database with the REAL schema for tests/local dev:
# replays the retained V1..V17 baseline (scripts/apply_baseline.sh), then
# applies the Alembic revisions layered on top. Production containers apply
# only the Alembic layer themselves on boot -- see run.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

bash "$SCRIPT_DIR/apply_baseline.sh"

echo "Applying Alembic revisions layered on top of the PostgreSQL baseline"
cd "$APP_DIR"
alembic upgrade head

echo "Test database ready."
