-- Load the synthetic historical dataset into an already-migrated database.
-- Run from the repository root:
--   PGDATABASE=goodwill_db psql -X -f test-data/historical/load_historical.sql
--
-- Uses the shared insert-only loader: existing rows are never updated or
-- deleted, and rerunning adds nothing.

\set ON_ERROR_STOP on
\set csv_dir test-data/historical
\ir ../../ingestion/load_normalized.sql

SELECT 'source' AS table_name, COUNT(*) AS row_count FROM source
UNION ALL SELECT 'category', COUNT(*) FROM category
UNION ALL SELECT 'ingestion_batch', COUNT(*) FROM ingestion_batch
UNION ALL SELECT 'product', COUNT(*) FROM product
UNION ALL SELECT 'listing', COUNT(*) FROM listing
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'sales_order', COUNT(*) FROM sales_order
UNION ALL SELECT 'order_item', COUNT(*) FROM order_item
UNION ALL SELECT 'review', COUNT(*) FROM review
UNION ALL SELECT 'sales_order_mv', COUNT(*) FROM sales_order_mv;
