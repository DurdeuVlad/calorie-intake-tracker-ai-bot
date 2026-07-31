#!/bin/sh
set -eu

if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres --tuples-only --no-align \
  --command "SELECT 1 FROM pg_database WHERE datname = 'foodjournal_dev'" | grep -q 1; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres --command "CREATE DATABASE foodjournal_dev"
fi
