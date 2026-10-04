\set ON_ERROR_STOP on

-- Use a disposable database with migrations already applied.
-- Fixture rows, functions, and materialized-view changes roll back at the end.
BEGIN;
SET LOCAL search_path = public;
SET LOCAL timezone = 'UTC';

CREATE FUNCTION pg_temp.assert_true(condition BOOLEAN, message TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF condition IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Assertion failed: %', message;
    END IF;
END;
$$;

CREATE FUNCTION pg_temp.expect_error(statement TEXT, expected_state TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE statement;
    EXCEPTION WHEN OTHERS THEN
        IF SQLSTATE = expected_state THEN
            RETURN;
        END IF;
        RAISE EXCEPTION 'Expected SQLSTATE %, got %: %',
            expected_state, SQLSTATE, SQLERRM;
    END;
    RAISE EXCEPTION 'Expected SQLSTATE %, but statement succeeded: %',
        expected_state, statement;
END;
$$;

DO $$
DECLARE
    ebay BIGINT;
    amazon BIGINT;
    ebay_batch BIGINT;
    amazon_batch BIGINT;
    home_category BIGINT;
    decor_category BIGINT;
    item_product BIGINT;
    old_listing BIGINT;
    sold_listing BIGINT;
    amazon_listing BIGINT;
    buyer BIGINT;
    ebay_order BIGINT;
    amazon_order BIGINT;
    empty_order BIGINT;
    sale_item BIGINT;
    feedback BIGINT;
    row_count BIGINT;
    column_name TEXT;
    relation_name TEXT;
    external_column TEXT;
    invalid_money TEXT;
    fk RECORD;
    mv RECORD;
BEGIN
    PERFORM pg_temp.assert_true(
        (SELECT count(*) = 3 FROM source
         WHERE name IN ('Amazon', 'eBay', 'ShopGoodwill')),
        'all three marketplaces are seeded');
    PERFORM pg_temp.assert_true(
        (SELECT count(*) = 7 FROM category WHERE parent_category_id IS NULL
         AND name IN ('Art', 'Books', 'Clothing', 'Collectibles',
                      'Electronics', 'Home', 'Jewelry & Gemstones')),
        'fixture categories are seeded exactly once');

    -- Separate test sources avoid colliding with normal imports.
    INSERT INTO source (name) VALUES ('__test_ebay') RETURNING source_id INTO ebay;
    INSERT INTO source (name) VALUES ('__test_amazon') RETURNING source_id INTO amazon;
    INSERT INTO ingestion_batch
        (source_id, file_name, archived_path, ingested_at, period_start, period_end)
    VALUES (ebay, 'test.csv', 'test-only/ebay.csv', '2026-10-01 12:00:00+00',
            '2026-09-01', '2026-10-01') RETURNING batch_id INTO ebay_batch;
    INSERT INTO ingestion_batch (source_id, file_name, archived_path, ingested_at)
    VALUES (amazon, 'test.csv', 'test-only/amazon.csv', '2026-10-01 12:00:00+00')
    RETURNING batch_id INTO amazon_batch;

    INSERT INTO category (name) VALUES ('__test_home') RETURNING category_id INTO home_category;
    INSERT INTO category (name, parent_category_id) VALUES ('__test_decor', home_category)
    RETURNING category_id INTO decor_category;
    INSERT INTO product (sku_number, product_name, category_id)
    VALUES ('__test_sku', 'Test lamp', decor_category) RETURNING product_id INTO item_product;

    INSERT INTO listing
        (product_id, source_id, source_listing_id, listed_at, ended_at, status, batch_id)
    VALUES (item_product, ebay, 'old-attempt', '2026-09-01 12:00:00+00',
            '2026-09-08 12:00:00+00', 'ENDED_UNSOLD', ebay_batch)
    RETURNING listing_id INTO old_listing;
    INSERT INTO listing
        (product_id, source_id, source_listing_id, listed_at, status, batch_id)
    VALUES (item_product, ebay, 'shared-id', '2026-09-09 12:00:00+00', 'SOLD', ebay_batch)
    RETURNING listing_id INTO sold_listing;
    INSERT INTO listing
        (product_id, source_id, source_listing_id, listed_at, status, batch_id)
    VALUES (item_product, amazon, 'shared-id', '2026-09-09 12:00:00+00', 'ACTIVE', amazon_batch)
    RETURNING listing_id INTO amazon_listing;
    PERFORM pg_temp.assert_true(
        (SELECT count(*) = 3 FROM listing WHERE product_id = item_product),
        'relisting retains one physical product and prior attempts');

    INSERT INTO customer (source_id, source_customer_id, batch_id)
    VALUES (ebay, 'shared-id', ebay_batch) RETURNING customer_id INTO buyer;
    INSERT INTO customer (source_id, source_customer_id, batch_id, zipcode)
    VALUES (amazon, 'shared-id', amazon_batch, '00123');

    INSERT INTO sales_order
        (source_id, source_order_id, customer_id, ordered_at, status,
         shipping_charge_amount, shipping_cost_amount, tax_amount, operation_fee_amount, batch_id)
    VALUES (ebay, 'shared-id', buyer, '2026-09-10 12:00:00+00', 'demo_sale',
            10, 7, 4.80, 6, ebay_batch) RETURNING order_id INTO ebay_order;
    INSERT INTO sales_order
        (source_id, source_order_id, ordered_at, status, shipping_charge_amount,
         shipping_cost_amount, tax_amount, operation_fee_amount, batch_id)
    VALUES (amazon, 'shared-id', '2026-09-10 12:00:00+00', 'demo_sale',
            0, 8.50, 6.40, 7.50, amazon_batch) RETURNING order_id INTO amazon_order;

    INSERT INTO order_item (order_id, listing_id, quantity, unit_price, discount_amount, refund_amount)
    VALUES (ebay_order, sold_listing, 1, 80, 0, 0) RETURNING order_item_id INTO sale_item;
    INSERT INTO order_item (order_id, listing_id, quantity, unit_price, discount_amount, refund_amount)
    VALUES (amazon_order, amazon_listing, 1, 100, 10, 0);

    INSERT INTO review (source_id, source_review_id, customer_id, order_id,
                        rating, reviewed_at, batch_id)
    VALUES (ebay, 'shared-id', buyer, ebay_order, 5, '2026-09-11 12:00:00+00', ebay_batch)
    RETURNING review_id INTO feedback;
    INSERT INTO review (source_id, source_review_id, rating, reviewed_at, batch_id)
    VALUES (amazon, 'shared-id', 100, '2026-09-11 12:00:00+00', amazon_batch);

    REFRESH MATERIALIZED VIEW sales_order_mv;
    SELECT * INTO STRICT mv FROM sales_order_mv WHERE order_id = ebay_order;
    PERFORM pg_temp.assert_true(
        mv.merchandise_revenue = 80 AND mv.refund_impact = 0
        AND mv.customer_transaction_total = 94.80 AND mv.total_transaction_revenue = 77,
        'spec eBay example');
    SELECT * INTO STRICT mv FROM sales_order_mv WHERE order_id = amazon_order;
    PERFORM pg_temp.assert_true(
        mv.merchandise_revenue = 90 AND mv.customer_transaction_total = 96.40
        AND mv.total_transaction_revenue = 74, 'spec Amazon example');

    INSERT INTO sales_order
        (source_id, source_order_id, ordered_at, status, shipping_charge_amount,
         shipping_cost_amount, tax_amount, operation_fee_amount, batch_id)
    VALUES (amazon, 'empty-order', '2026-09-10 05:00:00-07', 'demo_incomplete',
            0, 0, 0, 0, amazon_batch) RETURNING order_id INTO empty_order;
    REFRESH MATERIALIZED VIEW sales_order_mv;
    SELECT * INTO STRICT mv FROM sales_order_mv WHERE order_id = empty_order;
    PERFORM pg_temp.assert_true(
        mv.merchandise_revenue IS NULL AND mv.refund_impact IS NULL
        AND mv.customer_transaction_total IS NULL AND mv.total_transaction_revenue IS NULL,
        'empty orders retain a row with unknown derived totals');
    PERFORM pg_temp.assert_true(
        (SELECT ordered_at = TIMESTAMPTZ '2026-09-10 12:00:00+00'
         FROM sales_order WHERE order_id = empty_order), 'timestamp offset preserves instant');
    PERFORM pg_temp.assert_true(
        (SELECT count(*) FROM sales_order_mv) = (SELECT count(*) FROM sales_order),
        'view contains exactly one row per order');

    UPDATE order_item SET refund_amount = 20 WHERE order_item_id = sale_item;
    PERFORM pg_temp.assert_true(
        (SELECT refund_impact = 0 FROM sales_order_mv WHERE order_id = ebay_order),
        'materialized values change only after refresh');
    REFRESH MATERIALIZED VIEW sales_order_mv;
    SELECT * INTO STRICT mv FROM sales_order_mv WHERE order_id = ebay_order;
    PERFORM pg_temp.assert_true(
        mv.refund_impact = -20 AND mv.customer_transaction_total = 74.80
        AND mv.total_transaction_revenue = 57, 'positive stored refund reduces totals');

    -- Multiple lines for the same listing are explicitly allowed. Discounts and
    -- refunds are line totals, and order-level amounts must be counted once.
    INSERT INTO order_item (order_id, listing_id, quantity, unit_price, discount_amount, refund_amount)
    VALUES (ebay_order, sold_listing, 2, 10, 3, 4);
    REFRESH MATERIALIZED VIEW sales_order_mv;
    SELECT * INTO STRICT mv FROM sales_order_mv WHERE order_id = ebay_order;
    PERFORM pg_temp.assert_true(
        mv.merchandise_revenue = 97 AND mv.refund_impact = -24
        AND mv.shipping_charge_amount = 10 AND mv.shipping_cost_amount = 7
        AND mv.tax_amount = 4.80 AND mv.operation_fee_amount = 6
        AND mv.customer_transaction_total = 87.80 AND mv.total_transaction_revenue = 70,
        'multiline order counts shipping/tax/fees once and line discounts once');

    -- Same external IDs work across sources; duplicates within a source fail.
    FOR relation_name, external_column IN
        SELECT * FROM (VALUES ('listing', 'source_listing_id'),
                             ('customer', 'source_customer_id'),
                             ('sales_order', 'source_order_id'),
                             ('review', 'source_review_id')) AS pairs(relation_name, external_column)
    LOOP
        PERFORM pg_temp.expect_error(format(
            'UPDATE %I SET source_id = %s WHERE source_id = %s AND %I = %L',
            relation_name, ebay, amazon, external_column, 'shared-id'), '23505');
    END LOOP;

    INSERT INTO listing (product_id, source_id, source_listing_id, listed_at, status, batch_id)
    VALUES (item_product, ebay, 'shared-id', '2026-09-09 12:00:00+00', 'SOLD', ebay_batch)
    ON CONFLICT (source_id, source_listing_id) DO UPDATE SET status = EXCLUDED.status;
    SELECT count(*) INTO row_count FROM listing WHERE source_id = ebay;
    PERFORM pg_temp.assert_true(row_count = 2, 'listing upsert preserves historic attempts');

    PERFORM pg_temp.expect_error(format(
        'UPDATE listing SET status = %L WHERE listing_id = %s', 'RELISTED', sold_listing), '23514');
    PERFORM pg_temp.expect_error(format(
        'UPDATE listing SET ended_at = %L WHERE listing_id = %s', '2020-01-01', sold_listing), '23514');
    PERFORM pg_temp.expect_error(format(
        'UPDATE ingestion_batch SET period_end = %L WHERE batch_id = %s',
        '2020-01-01', ebay_batch), '23514');

    FOREACH column_name IN ARRAY ARRAY['shipping_charge_amount', 'shipping_cost_amount',
                                     'tax_amount', 'operation_fee_amount']
    LOOP
        PERFORM pg_temp.expect_error(format(
            'UPDATE sales_order SET %I = -1 WHERE order_id = %s', column_name, ebay_order), '23514');
        PERFORM pg_temp.expect_error(format(
            'UPDATE sales_order SET %I = NULL WHERE order_id = %s', column_name, ebay_order), '23502');
        FOREACH invalid_money IN ARRAY ARRAY['NaN', 'Infinity', '-Infinity'] LOOP
            PERFORM pg_temp.expect_error(format(
                'UPDATE sales_order SET %I = %L WHERE order_id = %s',
                column_name, invalid_money, ebay_order), '23514');
        END LOOP;
    END LOOP;
    FOREACH column_name IN ARRAY ARRAY['unit_price', 'discount_amount', 'refund_amount']
    LOOP
        PERFORM pg_temp.expect_error(format(
            'UPDATE order_item SET %I = -1 WHERE order_item_id = %s', column_name, sale_item), '23514');
        PERFORM pg_temp.expect_error(format(
            'UPDATE order_item SET %I = NULL WHERE order_item_id = %s', column_name, sale_item), '23502');
        FOREACH invalid_money IN ARRAY ARRAY['NaN', 'Infinity', '-Infinity'] LOOP
            PERFORM pg_temp.expect_error(format(
                'UPDATE order_item SET %I = %L WHERE order_item_id = %s',
                column_name, invalid_money, sale_item), '23514');
        END LOOP;
    END LOOP;
    PERFORM pg_temp.expect_error(format(
        'UPDATE order_item SET quantity = 0 WHERE order_item_id = %s', sale_item), '23514');
    PERFORM pg_temp.expect_error(format(
        'UPDATE order_item SET quantity = -1 WHERE order_item_id = %s', sale_item), '23514');
    PERFORM pg_temp.expect_error(format(
        'INSERT INTO sales_order (source_id, source_order_id, ordered_at, status, '
        'shipping_charge_amount, tax_amount, operation_fee_amount, batch_id) '
        'VALUES (%s, ''missing-cost'', ''2026-09-10 12:00:00+00'', ''demo_sale'', 0, 0, 0, %s)',
        ebay, ebay_batch), '23502');
    PERFORM pg_temp.expect_error(format(
        'UPDATE listing SET product_id = -1 WHERE listing_id = %s', sold_listing), '23503');
    PERFORM pg_temp.expect_error(format(
        'UPDATE sales_order SET customer_id = -1 WHERE order_id = %s', ebay_order), '23503');
    PERFORM pg_temp.expect_error(format(
        'UPDATE review SET order_id = -1 WHERE review_id = %s', feedback), '23503');

    -- Exercise every FK, including optional references and category hierarchy.
    FOR fk IN
        SELECT c.conrelid::regclass AS table_name, a.attname AS column_name
        FROM pg_constraint AS c
        JOIN pg_attribute AS a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
        WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
          AND c.conrelid IN ('ingestion_batch'::regclass, 'category'::regclass,
              'product'::regclass, 'listing'::regclass, 'customer'::regclass,
              'sales_order'::regclass, 'order_item'::regclass, 'review'::regclass)
    LOOP
        PERFORM pg_temp.expect_error(format(
            'UPDATE %s SET %I = -1 WHERE ctid = (SELECT ctid FROM %s LIMIT 1)',
            fk.table_name, fk.column_name, fk.table_name), '23503');
    END LOOP;
    PERFORM pg_temp.expect_error(format(
        'DELETE FROM product WHERE product_id = %s', item_product), '23503');
    PERFORM pg_temp.expect_error(
        'INSERT INTO source (name) VALUES (''Amazon'')', '23505');

    -- Global SKU uniqueness and comparable rating scales remain undecided.
    INSERT INTO product (sku_number, product_name, category_id)
    VALUES ('__test_sku', 'Another test item', decor_category);
    UPDATE order_item SET unit_price = 0.123456789 WHERE order_item_id = sale_item;
    PERFORM pg_temp.assert_true(
        (SELECT unit_price = 0.123456789 FROM order_item WHERE order_item_id = sale_item),
        'numeric values are not rounded to a fixed scale');
    PERFORM pg_temp.assert_true(
        (SELECT zipcode = '00123' FROM customer WHERE source_id = amazon),
        'postal codes retain leading zeros');
    PERFORM pg_temp.assert_true(
        (SELECT customer_id IS NULL FROM sales_order WHERE order_id = amazon_order),
        'orders can exist without a fabricated customer');

    RAISE NOTICE 'Database behavior tests passed';
END;
$$;

ROLLBACK;
