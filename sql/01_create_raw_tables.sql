-- ============================================================================
-- 01_create_raw_tables.sql
-- Thornbury Goods Analytics — Raw (landing zone) table definitions
--
-- These tables mirror the CSVs exactly as they arrive from the source
-- systems: no type enforcement, no dedup, no standardisation. Everything is
-- stored as TEXT so malformed values (bad dates, stray whitespace, negative
-- quantities, etc.) load without erroring out. Cleaning happens downstream
-- in 02_data_cleaning.sql.
-- ============================================================================

DROP TABLE IF EXISTS raw_customers;
CREATE TABLE raw_customers (
    customer_id         TEXT,
    first_name          TEXT,
    last_name           TEXT,
    email               TEXT,
    signup_date         TEXT,
    region              TEXT,
    acquisition_channel TEXT,
    birth_year          TEXT,
    marketing_opt_in    TEXT
);

DROP TABLE IF EXISTS raw_products;
CREATE TABLE raw_products (
    product_id     TEXT,
    product_name   TEXT,
    category       TEXT,
    sub_category   TEXT,
    unit_cost      TEXT,
    unit_price     TEXT,
    launch_date    TEXT
);

DROP TABLE IF EXISTS raw_orders;
CREATE TABLE raw_orders (
    order_id         TEXT,
    customer_id      TEXT,
    order_date       TEXT,
    order_status     TEXT,
    payment_method   TEXT,
    discount_code    TEXT,
    shipping_region  TEXT
);

DROP TABLE IF EXISTS raw_order_items;
CREATE TABLE raw_order_items (
    order_item_id       TEXT,
    order_id            TEXT,
    product_id          TEXT,
    quantity             TEXT,
    unit_price_at_sale  TEXT,
    discount_pct        TEXT,
    returned             TEXT
);

DROP TABLE IF EXISTS raw_marketing_spend;
CREATE TABLE raw_marketing_spend (
    month      TEXT,
    channel    TEXT,
    spend_gbp  TEXT
);

-- Raw CSVs are loaded into these tables via the .import command in
-- python/load_to_sqlite.py (equivalent to sqlite3's `.mode csv` + `.import`).
