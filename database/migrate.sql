\set ON_ERROR_STOP on

-- Run with psql -X -f backend/database/migrate.sql.
-- All pending migrations and their ledger entries commit together.
BEGIN;
SET LOCAL search_path = public;

-- Serialize this runner within the target database, including first setup.
SELECT pg_advisory_xact_lock(2026, 1004);

CREATE TABLE IF NOT EXISTS schema_migration (
    version TEXT CONSTRAINT schema_migration_pkey PRIMARY KEY
);

SELECT NOT EXISTS (
    SELECT 1 FROM schema_migration WHERE version = '001_initial_schema'
) AS apply_001 \gset
\if :apply_001
    \ir migrations/001_initial_schema.sql
    INSERT INTO schema_migration (version) VALUES ('001_initial_schema');
\endif

SELECT NOT EXISTS (
    SELECT 1 FROM schema_migration WHERE version = '002_reference_data'
) AS apply_002 \gset
\if :apply_002
    \ir migrations/002_reference_data.sql
    INSERT INTO schema_migration (version) VALUES ('002_reference_data');
\endif

COMMIT;
