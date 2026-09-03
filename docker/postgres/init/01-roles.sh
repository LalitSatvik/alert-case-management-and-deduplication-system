#!/bin/sh
# docker/postgres/init/01-roles.sh
#
# Runs once, as the bootstrap superuser, the first time the cluster initialises
# (empty data directory only). The official postgres image executes every
# *.sh / *.sql in this directory in name order; a shell script is used here so
# the role passwords can come from the environment instead of being hardcoded.
#
# Required env (set by the `postgres` service in docker-compose.yml from .env):
#   POSTGRES_OWNER_PASSWORD  password for acms_owner (owns the schema; Alembic)
#   POSTGRES_APP_PASSWORD    password for app_user  (least-privilege runtime role)
#
# Keep these in sync with the credentials embedded in DATABASE_URL /
# MIGRATION_DATABASE_URL in .env.
set -eu

: "${POSTGRES_OWNER_PASSWORD:?POSTGRES_OWNER_PASSWORD is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

# Create the roles and the application database on the bootstrap connection.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
	-v owner_pw="$POSTGRES_OWNER_PASSWORD" \
	-v app_pw="$POSTGRES_APP_PASSWORD" <<-'EOSQL'
	CREATE ROLE acms_owner LOGIN PASSWORD :'owner_pw';
	CREATE ROLE app_user   LOGIN PASSWORD :'app_pw';
	CREATE DATABASE acms OWNER acms_owner;
EOSQL

# Baseline grants for app_user, applied inside the new database. Table-level
# grants are handled by an Alembic migration (the tables do not exist yet).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname acms <<-'EOSQL'
	GRANT CONNECT ON DATABASE acms TO app_user;
	GRANT USAGE ON SCHEMA public TO app_user;
EOSQL
