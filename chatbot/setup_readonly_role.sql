\set ON_ERROR_STOP on

-- Read-only database user for the chatbot. Run as a database administrator
-- against each database the chatbot should read, e.g.:
--   PGDATABASE=goodwill_db_test psql -X -f chatbot/setup_readonly_role.sql
--
-- Safe to rerun. The role:
--   * can only SELECT; every transaction it opens is read-only,
--   * cannot see customer names, usernames, cities, zip codes or marketplace
--     buyer IDs (only state/country for regional breakdowns),
--   * stops any statement after 5 seconds.
-- Local Postgres.app connections use trust authentication, so no password is
-- set here. On a shared server, add one with ALTER ROLE ... PASSWORD and keep
-- it in chatbot/.env.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'goodwill_chatbot') THEN
        CREATE ROLE goodwill_chatbot LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;

ALTER ROLE goodwill_chatbot SET default_transaction_read_only = on;
ALTER ROLE goodwill_chatbot SET statement_timeout = '5s';
ALTER ROLE goodwill_chatbot SET idle_in_transaction_session_timeout = '30s';

SELECT format('GRANT CONNECT ON DATABASE %I TO goodwill_chatbot', current_database()) \gexec

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM goodwill_chatbot;
REVOKE CREATE ON SCHEMA public FROM goodwill_chatbot;
GRANT USAGE ON SCHEMA public TO goodwill_chatbot;

GRANT SELECT ON source, ingestion_batch, category, product, listing,
                sales_order, order_item, review, sales_order_mv TO goodwill_chatbot;

-- Customer: only non-identifying columns.
GRANT SELECT (customer_id, source_id, state, country, batch_id) ON customer TO goodwill_chatbot;
