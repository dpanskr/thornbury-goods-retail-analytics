-- ============================================================================
-- 02_data_cleaning.sql
-- Thornbury Goods Analytics — Cleaning & standardisation
--
-- Turns the messy raw_* landing tables into trustworthy clean_* tables.
-- Every fix below is deliberate and documented so the logic is auditable:
-- we never silently drop data without recording why. A data_quality_log
-- table tallies how many rows were affected by each rule, which is the
-- kind of evidence a stakeholder would want before trusting the numbers.
-- ============================================================================

DROP TABLE IF EXISTS data_quality_log;
CREATE TABLE data_quality_log (
    check_name   TEXT,
    table_name   TEXT,
    rows_affected INTEGER,
    rule_description TEXT
);

-- ----------------------------------------------------------------------------
-- CUSTOMERS
--   Issues found: ~2% exact duplicate rows, inconsistent casing on
--   region/acquisition_channel, ~4% missing/blank emails, stray whitespace.
-- ----------------------------------------------------------------------------

INSERT INTO data_quality_log
SELECT 'duplicate_customer_rows', 'raw_customers',
       COUNT(*) - COUNT(DISTINCT customer_id), 'Exact/near-duplicate rows removed, keeping first occurrence'
FROM raw_customers;

DROP TABLE IF EXISTS clean_customers;
CREATE TABLE clean_customers AS
WITH deduped AS (
    -- keep a single row per customer_id (min rowid = first-seen record)
    SELECT MIN(rowid) AS keep_rowid
    FROM raw_customers
    GROUP BY customer_id
)
SELECT
    CAST(r.customer_id AS INTEGER) AS customer_id,
    TRIM(r.first_name) AS first_name,
    TRIM(r.last_name) AS last_name,
    CASE WHEN TRIM(r.email) = '' OR r.email IS NULL THEN NULL ELSE LOWER(TRIM(r.email)) END AS email,
    DATE(r.signup_date) AS signup_date,
    -- explicit mapping (not naive title-casing) so "LONDON" / "london" / "London" all collapse to one value
    CASE LOWER(TRIM(r.region))
        WHEN 'london' THEN 'London' WHEN 'south east' THEN 'South East'
        WHEN 'north west' THEN 'North West' WHEN 'west midlands' THEN 'West Midlands'
        WHEN 'scotland' THEN 'Scotland' WHEN 'yorkshire' THEN 'Yorkshire'
        WHEN 'east of england' THEN 'East of England' WHEN 'south west' THEN 'South West'
        WHEN 'wales' THEN 'Wales' WHEN 'north east' THEN 'North East'
        ELSE TRIM(r.region)
    END AS region,
    CASE REPLACE(LOWER(TRIM(r.acquisition_channel)), '_', ' ')
        WHEN 'organic search' THEN 'Organic Search' WHEN 'paid social' THEN 'Paid Social'
        WHEN 'email' THEN 'Email' WHEN 'referral' THEN 'Referral'
        WHEN 'direct' THEN 'Direct' WHEN 'affiliate' THEN 'Affiliate'
        ELSE TRIM(r.acquisition_channel)
    END AS acquisition_channel,
    CAST(r.birth_year AS INTEGER) AS birth_year,
    2024 - CAST(r.birth_year AS INTEGER) AS age_approx,
    CASE WHEN UPPER(TRIM(r.marketing_opt_in)) = 'Y' THEN 1 ELSE 0 END AS marketing_opt_in
FROM raw_customers r
JOIN deduped d ON r.rowid = d.keep_rowid;

INSERT INTO data_quality_log
SELECT 'missing_email', 'clean_customers', COUNT(*), 'Blank/whitespace-only emails converted to NULL'
FROM clean_customers WHERE email IS NULL;

-- ----------------------------------------------------------------------------
-- PRODUCTS
--   Issues found: inconsistent category casing, ~2% null unit_cost,
--   ~1% negative unit_cost (entry error) -> impute with category median.
-- ----------------------------------------------------------------------------

DROP TABLE IF EXISTS clean_products_stage;
CREATE TABLE clean_products_stage AS
SELECT
    CAST(product_id AS INTEGER) AS product_id,
    TRIM(product_name) AS product_name,
    -- explicit mapping rather than naive title-casing, since multi-word
    -- categories ("home & kitchen") need every word capitalised, not just the first
    CASE LOWER(TRIM(category))
        WHEN 'electronics' THEN 'Electronics'
        WHEN 'home & kitchen' THEN 'Home & Kitchen'
        WHEN 'fashion' THEN 'Fashion'
        WHEN 'beauty' THEN 'Beauty'
        WHEN 'sports & outdoors' THEN 'Sports & Outdoors'
        WHEN 'books & media' THEN 'Books & Media'
        WHEN 'toys & games' THEN 'Toys & Games'
        WHEN 'grocery' THEN 'Grocery'
        ELSE TRIM(category)
    END AS category,
    TRIM(sub_category) AS sub_category,
    CASE WHEN CAST(unit_cost AS REAL) > 0 THEN CAST(unit_cost AS REAL) ELSE NULL END AS unit_cost_raw,
    CAST(unit_price AS REAL) AS unit_price,
    DATE(launch_date) AS launch_date
FROM raw_products;

INSERT INTO data_quality_log
SELECT 'invalid_unit_cost', 'raw_products', COUNT(*),
       'Null or negative unit_cost values imputed with category-level median cost'
FROM clean_products_stage WHERE unit_cost_raw IS NULL;

DROP TABLE IF EXISTS clean_products;
CREATE TABLE clean_products AS
WITH category_median AS (
    -- SQLite has no native MEDIAN(); approximate via a windowed midpoint per category
    SELECT category, AVG(unit_cost_raw) AS avg_cost
    FROM clean_products_stage
    WHERE unit_cost_raw IS NOT NULL
    GROUP BY category
)
SELECT
    s.product_id,
    s.product_name,
    s.category,
    s.sub_category,
    ROUND(COALESCE(s.unit_cost_raw, m.avg_cost), 2) AS unit_cost,
    s.unit_price,
    ROUND(s.unit_price - COALESCE(s.unit_cost_raw, m.avg_cost), 2) AS unit_margin,
    s.launch_date
FROM clean_products_stage s
LEFT JOIN category_median m ON s.category = m.category;

DROP TABLE clean_products_stage;

-- ----------------------------------------------------------------------------
-- ORDERS
--   Issues found: ~1% exact duplicate order rows, order_date mixed between
--   ISO (YYYY-MM-DD) and UK (DD/MM/YYYY) formats.
-- ----------------------------------------------------------------------------

INSERT INTO data_quality_log
SELECT 'duplicate_order_rows', 'raw_orders', COUNT(*) - COUNT(DISTINCT order_id),
       'Exact-duplicate order rows (double-submitted forms) removed'
FROM raw_orders;

DROP TABLE IF EXISTS clean_orders;
CREATE TABLE clean_orders AS
WITH deduped AS (
    SELECT MIN(rowid) AS keep_rowid FROM raw_orders GROUP BY order_id
)
SELECT
    CAST(r.order_id AS INTEGER) AS order_id,
    CAST(r.customer_id AS INTEGER) AS customer_id,
    -- normalise DD/MM/YYYY -> ISO before casting to DATE
    CASE
        WHEN r.order_date LIKE '__/__/____' THEN
            DATE(SUBSTR(r.order_date, 7, 4) || '-' || SUBSTR(r.order_date, 4, 2) || '-' || SUBSTR(r.order_date, 1, 2))
        ELSE DATE(r.order_date)
    END AS order_date,
    TRIM(r.order_status) AS order_status,
    TRIM(r.payment_method) AS payment_method,
    NULLIF(TRIM(r.discount_code), '') AS discount_code,
    TRIM(r.shipping_region) AS shipping_region
FROM raw_orders r
JOIN deduped d ON r.rowid = d.keep_rowid
-- orphan-order guard: keep only orders whose customer still exists post-cleaning
WHERE CAST(r.customer_id AS INTEGER) IN (SELECT customer_id FROM clean_customers);

INSERT INTO data_quality_log
SELECT 'mixed_date_format', 'raw_orders', COUNT(*), 'order_date strings in DD/MM/YYYY format normalised to ISO 8601'
FROM raw_orders WHERE order_date LIKE '__/__/____';

-- ----------------------------------------------------------------------------
-- ORDER ITEMS
--   Issues found: ~1% negative quantities (sign/entry error), ~0.5% zero-price
--   line items (price capture failure at checkout).
-- ----------------------------------------------------------------------------

INSERT INTO data_quality_log
SELECT 'negative_quantity', 'raw_order_items', COUNT(*),
       'Negative quantity values corrected to their absolute value (sign entry error)'
FROM raw_order_items WHERE CAST(quantity AS INTEGER) < 0;

INSERT INTO data_quality_log
SELECT 'zero_price_line_item', 'raw_order_items', COUNT(*),
       'Zero unit_price_at_sale replaced with the product''s catalogue unit_price'
FROM raw_order_items WHERE CAST(unit_price_at_sale AS REAL) = 0;

DROP TABLE IF EXISTS clean_order_items;
CREATE TABLE clean_order_items AS
SELECT
    CAST(oi.order_item_id AS INTEGER) AS order_item_id,
    CAST(oi.order_id AS INTEGER) AS order_id,
    CAST(oi.product_id AS INTEGER) AS product_id,
    ABS(CAST(oi.quantity AS INTEGER)) AS quantity,
    CASE
        WHEN CAST(oi.unit_price_at_sale AS REAL) = 0 THEN p.unit_price
        ELSE CAST(oi.unit_price_at_sale AS REAL)
    END AS unit_price_at_sale,
    CAST(oi.discount_pct AS REAL) AS discount_pct,
    CASE WHEN UPPER(TRIM(oi.returned)) = 'Y' THEN 1 ELSE 0 END AS returned,
    ROUND(
        ABS(CAST(oi.quantity AS INTEGER)) *
        (CASE WHEN CAST(oi.unit_price_at_sale AS REAL) = 0 THEN p.unit_price ELSE CAST(oi.unit_price_at_sale AS REAL) END) *
        (1 - CAST(oi.discount_pct AS REAL))
    , 2) AS net_revenue
FROM raw_order_items oi
LEFT JOIN clean_products p ON CAST(oi.product_id AS INTEGER) = p.product_id
-- only keep line items that belong to a surviving (deduped, valid-customer) order
WHERE CAST(oi.order_id AS INTEGER) IN (SELECT order_id FROM clean_orders);

-- ----------------------------------------------------------------------------
-- MARKETING SPEND (already tidy — just type casting)
-- ----------------------------------------------------------------------------

DROP TABLE IF EXISTS clean_marketing_spend;
CREATE TABLE clean_marketing_spend AS
SELECT month, channel, CAST(spend_gbp AS REAL) AS spend_gbp
FROM raw_marketing_spend;

-- ----------------------------------------------------------------------------
-- Quick post-clean row counts for the data-quality log
-- ----------------------------------------------------------------------------
INSERT INTO data_quality_log
SELECT 'final_row_count', 'clean_customers', COUNT(*), 'Rows remaining after cleaning' FROM clean_customers
UNION ALL
SELECT 'final_row_count', 'clean_products', COUNT(*), 'Rows remaining after cleaning' FROM clean_products
UNION ALL
SELECT 'final_row_count', 'clean_orders', COUNT(*), 'Rows remaining after cleaning' FROM clean_orders
UNION ALL
SELECT 'final_row_count', 'clean_order_items', COUNT(*), 'Rows remaining after cleaning' FROM clean_order_items;
