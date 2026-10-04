\set ON_ERROR_STOP on

-- Shared loader for normalized CSVs (one file per table, linked by natural keys).
-- Used by ingestion/ingest.py and test-data/historical/load_historical.sql.
--
-- Set csv_dir to the folder holding the CSVs before including this script, e.g.
--   psql -X -v csv_dir=/path/to/csvs -f ingestion/load_normalized.sql
--
-- Rows reference each other by natural keys (source name, marketplace IDs, SKU,
-- batch archive path), never by internal IDs. Existing rows are never updated
-- or deleted: keyed rows that already exist are skipped, so reruns are safe.
-- Everything commits together, and sales_order_mv is refreshed at the end.

\if :{?csv_dir}
\else
    \echo 'csv_dir is not set; pass -v csv_dir=<folder with the normalized CSVs>'
    \quit
\endif

-- \copy does not expand psql variables, so read files relative to csv_dir.
-- (Unquoted on purpose: psql keeps the interpolated value, spaces included, as one argument.)
\cd :csv_dir

BEGIN;
SET LOCAL search_path = public;

DO $$
BEGIN
    IF to_regclass('public.schema_migration') IS NULL
       OR NOT EXISTS (SELECT 1 FROM schema_migration WHERE version = '002_reference_data') THEN
        RAISE EXCEPTION 'Apply database/migrate.sql before loading data';
    END IF;
END $$;

-- ---------------------------------------------------------------- staging
CREATE TEMP TABLE stage_source (name TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_category (name TEXT, parent_name TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_batch (
    source_name TEXT, file_name TEXT, archived_path TEXT, ingested_at TIMESTAMPTZ,
    period_start DATE, period_end DATE) ON COMMIT DROP;
CREATE TEMP TABLE stage_product (
    sku_number TEXT, product_name TEXT, category_name TEXT, parent_category_name TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_listing (
    source_name TEXT, source_listing_id TEXT, sku_number TEXT, listed_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ, status TEXT, batch_archived_path TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_customer (
    source_name TEXT, source_customer_id TEXT, username TEXT, first_name TEXT, last_name TEXT,
    city TEXT, state TEXT, zipcode TEXT, country TEXT, batch_archived_path TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_order (
    source_name TEXT, source_order_id TEXT, source_customer_id TEXT, ordered_at TIMESTAMPTZ,
    status TEXT, shipping_charge_amount NUMERIC, shipping_cost_amount NUMERIC, tax_amount NUMERIC,
    operation_fee_amount NUMERIC, batch_archived_path TEXT) ON COMMIT DROP;
CREATE TEMP TABLE stage_item (
    source_name TEXT, source_order_id TEXT, source_listing_id TEXT, quantity INTEGER,
    unit_price NUMERIC, discount_amount NUMERIC, refund_amount NUMERIC) ON COMMIT DROP;
CREATE TEMP TABLE stage_review (
    source_name TEXT, source_review_id TEXT, source_customer_id TEXT, source_order_id TEXT,
    rating NUMERIC, review_text TEXT, reviewed_at TIMESTAMPTZ, batch_archived_path TEXT) ON COMMIT DROP;

\copy stage_source FROM 'source.csv' WITH (FORMAT csv, HEADER true)
\copy stage_category FROM 'category.csv' WITH (FORMAT csv, HEADER true)
\copy stage_batch FROM 'ingestion_batch.csv' WITH (FORMAT csv, HEADER true)
\copy stage_product FROM 'product.csv' WITH (FORMAT csv, HEADER true)
\copy stage_listing FROM 'listing.csv' WITH (FORMAT csv, HEADER true)
\copy stage_customer FROM 'customer.csv' WITH (FORMAT csv, HEADER true)
\copy stage_order FROM 'sales_order.csv' WITH (FORMAT csv, HEADER true)
\copy stage_item FROM 'order_item.csv' WITH (FORMAT csv, HEADER true)
\copy stage_review FROM 'review.csv' WITH (FORMAT csv, HEADER true)

-- ---------------------------------------------------------------- reference data
INSERT INTO source (name)
SELECT name FROM stage_source
ON CONFLICT (name) DO NOTHING;

-- Category names are not unique keys; match on (name, parent). Roots first.
INSERT INTO category (name)
SELECT DISTINCT s.name FROM stage_category AS s
WHERE s.parent_name IS NULL
  AND NOT EXISTS (SELECT 1 FROM category AS c WHERE c.name = s.name AND c.parent_category_id IS NULL);

INSERT INTO category (parent_category_id, name)
SELECT DISTINCT p.category_id, s.name
FROM stage_category AS s
JOIN LATERAL (
    SELECT MIN(category_id) AS category_id FROM category
    WHERE name = s.parent_name AND parent_category_id IS NULL
) AS p ON p.category_id IS NOT NULL
WHERE s.parent_name IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM category AS c WHERE c.name = s.name AND c.parent_category_id = p.category_id);

-- Roots (parent_name NULL) and their direct subcategories.
CREATE TEMP TABLE category_map ON COMMIT DROP AS
SELECT p.name AS parent_name, c.name AS name, MIN(c.category_id) AS category_id
FROM category AS c LEFT JOIN category AS p ON p.category_id = c.parent_category_id
WHERE p.category_id IS NULL OR p.parent_category_id IS NULL
GROUP BY p.name, c.name;

-- ---------------------------------------------------------------- batches
-- A batch is identified by its archive path, which is unique per archived file.
INSERT INTO ingestion_batch (source_id, file_name, archived_path, ingested_at, period_start, period_end)
SELECT src.source_id, b.file_name, b.archived_path, b.ingested_at, b.period_start, b.period_end
FROM stage_batch AS b
JOIN source AS src ON src.name = b.source_name
WHERE NOT EXISTS (
    SELECT 1 FROM ingestion_batch AS ib WHERE ib.source_id = src.source_id AND ib.archived_path = b.archived_path);

CREATE TEMP TABLE batch_map ON COMMIT DROP AS
SELECT src.name AS source_name, ib.archived_path, MIN(ib.batch_id) AS batch_id
FROM ingestion_batch AS ib JOIN source AS src ON src.source_id = ib.source_id
GROUP BY src.name, ib.archived_path;

-- ---------------------------------------------------------------- products and listings
INSERT INTO product (sku_number, product_name, category_id)
SELECT p.sku_number, p.product_name, cm.category_id
FROM stage_product AS p
JOIN category_map AS cm
  ON cm.name = p.category_name AND cm.parent_name IS NOT DISTINCT FROM p.parent_category_name
WHERE NOT EXISTS (SELECT 1 FROM product AS x WHERE x.sku_number = p.sku_number);

CREATE TEMP TABLE product_map ON COMMIT DROP AS
SELECT sku_number, MIN(product_id) AS product_id FROM product GROUP BY sku_number;

INSERT INTO listing (product_id, source_id, source_listing_id, listed_at, ended_at, status, batch_id)
SELECT pm.product_id, src.source_id, l.source_listing_id, l.listed_at, l.ended_at, l.status, bm.batch_id
FROM stage_listing AS l
JOIN source AS src ON src.name = l.source_name
JOIN product_map AS pm ON pm.sku_number = l.sku_number
JOIN batch_map AS bm ON bm.source_name = l.source_name AND bm.archived_path = l.batch_archived_path
ON CONFLICT (source_id, source_listing_id) DO NOTHING;

-- ---------------------------------------------------------------- customers and orders
INSERT INTO customer (source_id, source_customer_id, username, first_name, last_name,
                      city, state, zipcode, country, batch_id)
SELECT src.source_id, c.source_customer_id, c.username, c.first_name, c.last_name,
       c.city, c.state, c.zipcode, c.country, bm.batch_id
FROM stage_customer AS c
JOIN source AS src ON src.name = c.source_name
JOIN batch_map AS bm ON bm.source_name = c.source_name AND bm.archived_path = c.batch_archived_path
ON CONFLICT (source_id, source_customer_id) DO NOTHING;

INSERT INTO sales_order (source_id, source_order_id, customer_id, ordered_at, status,
                         shipping_charge_amount, shipping_cost_amount, tax_amount,
                         operation_fee_amount, batch_id)
SELECT src.source_id, o.source_order_id, cu.customer_id, o.ordered_at, o.status,
       o.shipping_charge_amount, o.shipping_cost_amount, o.tax_amount,
       o.operation_fee_amount, bm.batch_id
FROM stage_order AS o
JOIN source AS src ON src.name = o.source_name
JOIN batch_map AS bm ON bm.source_name = o.source_name AND bm.archived_path = o.batch_archived_path
LEFT JOIN customer AS cu
       ON cu.source_id = src.source_id AND cu.source_customer_id = o.source_customer_id
ON CONFLICT (source_id, source_order_id) DO NOTHING;

-- order_item has no external line ID (DATABASE_SPEC §9). The loaders emit each
-- listing at most once per order, so (order, listing) identifies a line and
-- lets reruns skip lines that are already present.
INSERT INTO order_item (order_id, listing_id, quantity, unit_price, discount_amount, refund_amount)
SELECT so.order_id, l.listing_id, i.quantity, i.unit_price, i.discount_amount, i.refund_amount
FROM stage_item AS i
JOIN source AS src ON src.name = i.source_name
JOIN sales_order AS so ON so.source_id = src.source_id AND so.source_order_id = i.source_order_id
JOIN listing AS l ON l.source_id = src.source_id AND l.source_listing_id = i.source_listing_id
WHERE NOT EXISTS (
    SELECT 1 FROM order_item AS x WHERE x.order_id = so.order_id AND x.listing_id = l.listing_id);

INSERT INTO review (source_id, source_review_id, customer_id, order_id, rating, review_text,
                    reviewed_at, batch_id)
SELECT src.source_id, r.source_review_id, cu.customer_id, so.order_id, r.rating, r.review_text,
       r.reviewed_at, bm.batch_id
FROM stage_review AS r
JOIN source AS src ON src.name = r.source_name
JOIN batch_map AS bm ON bm.source_name = r.source_name AND bm.archived_path = r.batch_archived_path
LEFT JOIN customer AS cu
       ON cu.source_id = src.source_id AND cu.source_customer_id = r.source_customer_id
LEFT JOIN sales_order AS so
       ON so.source_id = src.source_id AND so.source_order_id = r.source_order_id
ON CONFLICT (source_id, source_review_id) DO NOTHING;

-- Every staged row must now exist; a missing reference means a broken CSV.
DO $$
DECLARE missing BIGINT;
BEGIN
    SELECT COUNT(*) INTO missing FROM stage_product AS p
    WHERE NOT EXISTS (SELECT 1 FROM product AS x WHERE x.sku_number = p.sku_number);
    IF missing > 0 THEN RAISE EXCEPTION '% products could not be loaded (unknown category)', missing; END IF;

    SELECT COUNT(*) INTO missing FROM stage_listing AS l JOIN source AS s ON s.name = l.source_name
    WHERE NOT EXISTS (SELECT 1 FROM listing AS x WHERE x.source_id = s.source_id AND x.source_listing_id = l.source_listing_id);
    IF missing > 0 THEN RAISE EXCEPTION '% listings could not be loaded (unknown SKU or batch)', missing; END IF;

    SELECT COUNT(*) INTO missing FROM stage_order AS o JOIN source AS s ON s.name = o.source_name
    WHERE NOT EXISTS (SELECT 1 FROM sales_order AS x WHERE x.source_id = s.source_id AND x.source_order_id = o.source_order_id);
    IF missing > 0 THEN RAISE EXCEPTION '% orders could not be loaded (unknown batch)', missing; END IF;

    SELECT COUNT(*) INTO missing FROM stage_item AS i JOIN source AS s ON s.name = i.source_name
    WHERE NOT EXISTS (
        SELECT 1 FROM order_item AS x
        JOIN sales_order AS so ON so.order_id = x.order_id
        JOIN listing AS l ON l.listing_id = x.listing_id
        WHERE so.source_id = s.source_id AND so.source_order_id = i.source_order_id
          AND l.source_listing_id = i.source_listing_id);
    IF missing > 0 THEN RAISE EXCEPTION '% order lines could not be loaded (unknown order or listing)', missing; END IF;
END $$;

REFRESH MATERIALIZED VIEW sales_order_mv;

COMMIT;
