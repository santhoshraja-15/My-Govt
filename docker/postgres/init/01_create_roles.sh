#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  -- Create application roles
  DO \$\$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mygovt_app') THEN
      CREATE ROLE mygovt_app LOGIN PASSWORD '${MYGOVT_APP_PASSWORD:-changeme_app}';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mygovt_ai_readonly') THEN
      CREATE ROLE mygovt_ai_readonly LOGIN PASSWORD '${MYGOVT_AI_READONLY_PASSWORD:-changeme_ai}';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mygovt_etl') THEN
      CREATE ROLE mygovt_etl LOGIN PASSWORD '${MYGOVT_ETL_PASSWORD:-changeme_etl}';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mygovt_admin') THEN
      CREATE ROLE mygovt_admin LOGIN PASSWORD '${MYGOVT_ADMIN_PASSWORD:-changeme_admin}';
    END IF;
  END \$\$;

  -- Grant privileges
  GRANT ALL PRIVILEGES ON DATABASE mygovt TO mygovt_app;
  GRANT ALL PRIVILEGES ON DATABASE mygovt TO mygovt_admin;
  GRANT CONNECT ON DATABASE mygovt TO mygovt_ai_readonly;
  GRANT CONNECT ON DATABASE mygovt TO mygovt_etl;
EOSQL

echo "Database roles created."
