"""
load_to_sqlite.py
------------------
Loads the raw CSVs into a SQLite database (data/thornbury_goods.db), then runs the
three SQL scripts in order:
  1. sql/01_create_raw_tables.sql
  2. sql/02_data_cleaning.sql
  3. sql/03_transformations_analysis.sql

Finally exports every clean_* table and vw_* analysis view to CSV under
data/cleaned/ so the Python EDA script has plain files to read (mirrors how
you'd hand off "analysis-ready" extracts to a BI tool in a real job).

Run: python3 load_to_sqlite.py
"""

import sqlite3
import pandas as pd
import os

BASE = os.path.dirname(__file__)
RAW_DIR = os.path.join(BASE, "..", "data", "raw")
CLEANED_DIR = os.path.join(BASE, "..", "data", "cleaned")
SQL_DIR = os.path.join(BASE, "..", "sql")
DB_PATH = os.path.join(BASE, "..", "data", "thornbury_goods.db")

os.makedirs(CLEANED_DIR, exist_ok=True)
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)

# 1. Create raw table schema
with open(os.path.join(SQL_DIR, "01_create_raw_tables.sql")) as f:
    conn.executescript(f.read())

# 2. Load CSVs into the raw_* tables
csv_to_table = {
    "customers.csv": "raw_customers",
    "products.csv": "raw_products",
    "orders.csv": "raw_orders",
    "order_items.csv": "raw_order_items",
    "marketing_spend.csv": "raw_marketing_spend",
}
for csv_file, table in csv_to_table.items():
    df = pd.read_csv(os.path.join(RAW_DIR, csv_file), dtype=str, keep_default_na=True)
    df.to_sql(table, conn, if_exists="append", index=False)
    print(f"Loaded {len(df):>6} rows -> {table}")

# 3. Run cleaning script
with open(os.path.join(SQL_DIR, "02_data_cleaning.sql")) as f:
    conn.executescript(f.read())
print("Ran 02_data_cleaning.sql")

# 4. Run analysis/transformation views
with open(os.path.join(SQL_DIR, "03_transformations_analysis.sql")) as f:
    conn.executescript(f.read())
print("Ran 03_transformations_analysis.sql")

# 5. Export clean tables + analysis views to CSV
export_objects = [
    "clean_customers", "clean_products", "clean_orders", "clean_order_items",
    "clean_marketing_spend", "data_quality_log",
    "vw_order_facts", "vw_monthly_trend", "vw_category_performance",
    "vw_weekday_pattern", "vw_channel_efficiency", "vw_cohort_retention",
    "vw_customer_rfm", "vw_discount_effectiveness",
]
for obj in export_objects:
    df = pd.read_sql(f"SELECT * FROM {obj}", conn)
    out_path = os.path.join(CLEANED_DIR, f"{obj}.csv")
    df.to_csv(out_path, index=False)
    print(f"Exported {obj:<26} {len(df):>6} rows -> {out_path.replace(BASE + os.sep, '')}")

conn.close()
print("\nDone. SQLite DB at:", DB_PATH)
