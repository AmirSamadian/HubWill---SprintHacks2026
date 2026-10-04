-- Apply through ../migrate.sql; do not edit after deployment.
-- No financial, status, quantity, or business timestamp defaults are inferred.
CREATE TABLE source (
    source_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT source_pkey PRIMARY KEY,
    name TEXT NOT NULL CONSTRAINT source_name_key UNIQUE
);

CREATE TABLE ingestion_batch (
    batch_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT ingestion_batch_pkey PRIMARY KEY,
    source_id BIGINT NOT NULL,
    file_name TEXT NOT NULL,
    archived_path TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL,
    period_start DATE,
    period_end DATE,
    CONSTRAINT ingestion_batch_source_fkey FOREIGN KEY (source_id) REFERENCES source (source_id),
    CONSTRAINT ingestion_batch_period_check CHECK (period_end >= period_start)
);
CREATE INDEX ingestion_batch_source_id_idx ON ingestion_batch (source_id);
CREATE INDEX ingestion_batch_ingested_at_idx ON ingestion_batch (ingested_at);

CREATE TABLE category (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT category_pkey PRIMARY KEY,
    parent_category_id BIGINT,
    name TEXT NOT NULL,
    CONSTRAINT category_parent_fkey FOREIGN KEY (parent_category_id) REFERENCES category (category_id)
);
CREATE INDEX category_parent_category_id_idx ON category (parent_category_id);
CREATE INDEX category_name_idx ON category (name);

CREATE TABLE product (
    product_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT product_pkey PRIMARY KEY,
    sku_number TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category_id BIGINT NOT NULL,
    CONSTRAINT product_category_fkey FOREIGN KEY (category_id) REFERENCES category (category_id)
);
CREATE INDEX product_category_id_idx ON product (category_id);
CREATE INDEX product_sku_number_idx ON product (sku_number);

CREATE TABLE listing (
    listing_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT listing_pkey PRIMARY KEY,
    product_id BIGINT NOT NULL,
    source_id BIGINT NOT NULL,
    source_listing_id TEXT NOT NULL,
    listed_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    batch_id BIGINT NOT NULL,
    CONSTRAINT listing_product_fkey FOREIGN KEY (product_id) REFERENCES product (product_id),
    CONSTRAINT listing_source_fkey FOREIGN KEY (source_id) REFERENCES source (source_id),
    CONSTRAINT listing_batch_fkey FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id),
    CONSTRAINT listing_source_external_key UNIQUE (source_id, source_listing_id),
    CONSTRAINT listing_status_check CHECK (status IN ('ACTIVE', 'SOLD', 'ENDED_UNSOLD', 'CANCELLED')),
    CONSTRAINT listing_end_check CHECK (ended_at IS NULL OR ended_at >= listed_at)
);
CREATE INDEX listing_product_id_idx ON listing (product_id);
CREATE INDEX listing_batch_id_idx ON listing (batch_id);
CREATE INDEX listing_source_status_listed_at_idx ON listing (source_id, status, listed_at);

CREATE TABLE customer (
    customer_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT customer_pkey PRIMARY KEY,
    source_id BIGINT NOT NULL,
    source_customer_id TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    city TEXT,
    state TEXT,
    zipcode TEXT,
    country TEXT,
    batch_id BIGINT NOT NULL,
    CONSTRAINT customer_source_fkey FOREIGN KEY (source_id) REFERENCES source (source_id),
    CONSTRAINT customer_batch_fkey FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id),
    CONSTRAINT customer_source_external_key UNIQUE (source_id, source_customer_id)
);
CREATE INDEX customer_batch_id_idx ON customer (batch_id);
CREATE INDEX customer_source_id_idx ON customer (source_id);

-- PostgreSQL sorts NaN above Infinity; the upper bound rejects both special
-- values while leaving finite NUMERIC precision and scale unconstrained.
CREATE TABLE sales_order (
    order_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT sales_order_pkey PRIMARY KEY,
    source_id BIGINT NOT NULL,
    source_order_id TEXT NOT NULL,
    customer_id BIGINT,
    ordered_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    shipping_charge_amount NUMERIC NOT NULL,
    shipping_cost_amount NUMERIC NOT NULL,
    tax_amount NUMERIC NOT NULL,
    operation_fee_amount NUMERIC NOT NULL,
    batch_id BIGINT NOT NULL,
    CONSTRAINT sales_order_source_fkey FOREIGN KEY (source_id) REFERENCES source (source_id),
    CONSTRAINT sales_order_customer_fkey FOREIGN KEY (customer_id) REFERENCES customer (customer_id),
    CONSTRAINT sales_order_batch_fkey FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id),
    CONSTRAINT sales_order_source_external_key UNIQUE (source_id, source_order_id),
    CONSTRAINT sales_order_shipping_charge_check CHECK (shipping_charge_amount >= 0 AND shipping_charge_amount < 'Infinity'::NUMERIC),
    CONSTRAINT sales_order_shipping_cost_check CHECK (shipping_cost_amount >= 0 AND shipping_cost_amount < 'Infinity'::NUMERIC),
    CONSTRAINT sales_order_tax_check CHECK (tax_amount >= 0 AND tax_amount < 'Infinity'::NUMERIC),
    CONSTRAINT sales_order_operation_fee_check CHECK (operation_fee_amount >= 0 AND operation_fee_amount < 'Infinity'::NUMERIC)
);
CREATE INDEX sales_order_customer_id_idx ON sales_order (customer_id);
CREATE INDEX sales_order_batch_id_idx ON sales_order (batch_id);
CREATE INDEX sales_order_source_ordered_at_idx ON sales_order (source_id, ordered_at);
CREATE INDEX sales_order_status_idx ON sales_order (status);

CREATE TABLE order_item (
    order_item_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT order_item_pkey PRIMARY KEY,
    order_id BIGINT NOT NULL,
    listing_id BIGINT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC NOT NULL,
    discount_amount NUMERIC NOT NULL,
    refund_amount NUMERIC NOT NULL,
    CONSTRAINT order_item_order_fkey FOREIGN KEY (order_id) REFERENCES sales_order (order_id),
    CONSTRAINT order_item_listing_fkey FOREIGN KEY (listing_id) REFERENCES listing (listing_id),
    CONSTRAINT order_item_quantity_check CHECK (quantity > 0),
    CONSTRAINT order_item_unit_price_check CHECK (unit_price >= 0 AND unit_price < 'Infinity'::NUMERIC),
    CONSTRAINT order_item_discount_check CHECK (discount_amount >= 0 AND discount_amount < 'Infinity'::NUMERIC),
    CONSTRAINT order_item_refund_check CHECK (refund_amount >= 0 AND refund_amount < 'Infinity'::NUMERIC)
);
CREATE INDEX order_item_order_id_idx ON order_item (order_id);
CREATE INDEX order_item_listing_id_idx ON order_item (listing_id);

CREATE TABLE review (
    review_id BIGINT GENERATED ALWAYS AS IDENTITY CONSTRAINT review_pkey PRIMARY KEY,
    source_id BIGINT NOT NULL,
    source_review_id TEXT NOT NULL,
    customer_id BIGINT,
    order_id BIGINT,
    rating NUMERIC NOT NULL,
    review_text TEXT,
    reviewed_at TIMESTAMPTZ NOT NULL,
    batch_id BIGINT NOT NULL,
    CONSTRAINT review_source_fkey FOREIGN KEY (source_id) REFERENCES source (source_id),
    CONSTRAINT review_customer_fkey FOREIGN KEY (customer_id) REFERENCES customer (customer_id),
    CONSTRAINT review_order_fkey FOREIGN KEY (order_id) REFERENCES sales_order (order_id),
    CONSTRAINT review_batch_fkey FOREIGN KEY (batch_id) REFERENCES ingestion_batch (batch_id),
    CONSTRAINT review_source_external_key UNIQUE (source_id, source_review_id)
);
CREATE INDEX review_customer_id_idx ON review (customer_id);
CREATE INDEX review_order_id_idx ON review (order_id);
CREATE INDEX review_batch_id_idx ON review (batch_id);
CREATE INDEX review_source_reviewed_at_idx ON review (source_id, reviewed_at);

-- Aggregate lines before joining headers, so header amounts are counted once.
-- LEFT JOIN retains empty orders. Missing line facts stay NULL, not zero.
CREATE MATERIALIZED VIEW sales_order_mv AS
WITH line_totals AS (
    SELECT
        order_id,
        SUM(quantity * unit_price - discount_amount) AS merchandise_revenue,
        -SUM(refund_amount) AS refund_impact
    FROM order_item
    GROUP BY order_id
)
SELECT
    so.order_id,
    lt.merchandise_revenue,
    lt.refund_impact,
    so.shipping_charge_amount,
    so.shipping_cost_amount,
    so.tax_amount,
    so.operation_fee_amount,
    lt.merchandise_revenue + lt.refund_impact
        + so.shipping_charge_amount + so.tax_amount AS customer_transaction_total,
    lt.merchandise_revenue + lt.refund_impact
        + so.shipping_charge_amount - so.shipping_cost_amount
        - so.operation_fee_amount AS total_transaction_revenue
FROM sales_order AS so
LEFT JOIN line_totals AS lt ON lt.order_id = so.order_id;

CREATE UNIQUE INDEX sales_order_mv_order_id_idx ON sales_order_mv (order_id);
