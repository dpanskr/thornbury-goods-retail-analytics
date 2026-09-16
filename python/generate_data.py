"""
generate_data.py
-----------------
Synthetic data generator for "Thornbury Goods" — a fictional UK-based online
multi-category retailer. Produces realistic, messy raw CSVs (2023-01-01 to
2024-12-31) with deliberate data-quality issues for the SQL cleaning stage,
and baked-in seasonal/behavioural trends for the EDA stage.

Run: python3 generate_data.py
Outputs land in ../data/raw/
"""

import numpy as np
import pandas as pd
from faker import Faker
from datetime import date, timedelta
import random
import os

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_GB")
Faker.seed(SEED)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
os.makedirs(OUT_DIR, exist_ok=True)

START_DATE = date(2023, 1, 1)
END_DATE = date(2024, 12, 31)
ALL_DAYS = pd.date_range(START_DATE, END_DATE, freq="D")

# ---------------------------------------------------------------------------
# 1. CUSTOMERS
# ---------------------------------------------------------------------------
N_CUSTOMERS = 3000

REGIONS = ["London", "South East", "North West", "West Midlands",
           "Scotland", "Yorkshire", "East of England", "South West",
           "Wales", "North East"]
REGION_WEIGHTS = [0.22, 0.14, 0.12, 0.10, 0.09, 0.09, 0.08, 0.07, 0.05, 0.04]

CHANNELS = ["Organic Search", "Paid Social", "Email", "Referral", "Direct", "Affiliate"]

def acquisition_channel_for_date(d):
    """Channel mix shifts over the two years: Paid Social grows, Organic shrinks."""
    progress = (d - START_DATE).days / (END_DATE - START_DATE).days  # 0 -> 1
    weights = np.array([
        0.34 - 0.10 * progress,   # Organic Search declining
        0.18 + 0.12 * progress,   # Paid Social growing
        0.14,                     # Email steady
        0.12,                     # Referral steady
        0.14 - 0.03 * progress,   # Direct slight decline
        0.08 + 0.01 * progress,   # Affiliate slight growth
    ])
    weights = np.clip(weights, 0.01, None)
    weights = weights / weights.sum()
    return np.random.choice(CHANNELS, p=weights)

customers = []
signup_dates = np.random.choice(ALL_DAYS, size=N_CUSTOMERS,
                                 p=None)  # will overwrite with skew below

# Skew signups: more signups in Nov/Dec (holiday shopping) and Sep (back to school)
day_weights = []
for d in ALL_DAYS:
    w = 1.0
    if d.month in (11, 12):
        w *= 1.8
    if d.month == 9:
        w *= 1.3
    if d.month in (7, 8):
        w *= 0.7
    day_weights.append(w)
day_weights = np.array(day_weights) / sum(day_weights)
signup_dates = np.random.choice(ALL_DAYS, size=N_CUSTOMERS, p=day_weights)

for i in range(1, N_CUSTOMERS + 1):
    fn = fake.first_name()
    ln = fake.last_name()
    sd = pd.Timestamp(signup_dates[i - 1]).date()
    region = np.random.choice(REGIONS, p=REGION_WEIGHTS)
    channel = acquisition_channel_for_date(sd)
    birth_year = np.random.randint(1950, 2006)

    # messiness: inconsistent casing/whitespace, occasional missing email, dup formatting
    email_style = random.random()
    if email_style < 0.05:
        email = None  # missing email
    else:
        email = f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@{fake.free_email_domain()}"
        if random.random() < 0.08:
            email = email.upper()  # inconsistent casing
        if random.random() < 0.05:
            email = " " + email + " "  # stray whitespace

    region_messy = region
    if random.random() < 0.10:
        region_messy = region.lower()
    elif random.random() < 0.05:
        region_messy = region.upper()

    channel_messy = channel
    if random.random() < 0.06:
        channel_messy = channel_messy.replace(" ", "_").lower()

    marketing_opt_in = np.random.choice(["Y", "N"], p=[0.62, 0.38])

    customers.append({
        "customer_id": i,
        "first_name": fn,
        "last_name": ln,
        "email": email,
        "signup_date": sd.isoformat(),
        "region": region_messy,
        "acquisition_channel": channel_messy,
        "birth_year": birth_year,
        "marketing_opt_in": marketing_opt_in,
    })

customers_df = pd.DataFrame(customers)

# inject ~2% duplicate customer rows (simulating accidental re-export/re-signup)
dupe_rows = customers_df.sample(frac=0.02, random_state=SEED).copy()
customers_df = pd.concat([customers_df, dupe_rows], ignore_index=True)

customers_df.to_csv(os.path.join(OUT_DIR, "customers.csv"), index=False)

# ---------------------------------------------------------------------------
# 2. PRODUCTS
# ---------------------------------------------------------------------------
CATEGORY_INFO = {
    "Electronics":        {"n": 22, "price": (25, 800),  "cost_margin": (0.55, 0.72), "growth": 0.28},
    "Home & Kitchen":      {"n": 25, "price": (8, 250),   "cost_margin": (0.45, 0.65), "growth": 0.10},
    "Fashion":             {"n": 30, "price": (10, 150),  "cost_margin": (0.35, 0.55), "growth": 0.05},
    "Beauty":              {"n": 20, "price": (5, 90),    "cost_margin": (0.30, 0.50), "growth": 0.32},
    "Sports & Outdoors":   {"n": 18, "price": (10, 300),  "cost_margin": (0.45, 0.62), "growth": 0.12},
    "Books & Media":       {"n": 15, "price": (5, 40),    "cost_margin": (0.40, 0.55), "growth": -0.18},
    "Toys & Games":        {"n": 15, "price": (8, 120),   "cost_margin": (0.40, 0.58), "growth": 0.08},
    "Grocery":             {"n": 10, "price": (3, 35),    "cost_margin": (0.55, 0.70), "growth": 0.02},
}

PRODUCT_NAME_WORDS = {
    "Electronics": ["Wireless Earbuds", "Bluetooth Speaker", "Smart Watch", "Laptop Stand",
                    "4K Monitor", "Phone Charger", "Noise-Cancelling Headphones", "Tablet",
                    "Smart Plug", "Action Camera", "Portable SSD", "Gaming Mouse"],
    "Home & Kitchen": ["Air Fryer", "Stand Mixer", "Non-Stick Pan Set", "Coffee Maker",
                       "Knife Block Set", "Bedding Set", "Memory Foam Pillow", "Blender",
                       "Storage Ottoman", "Table Lamp"],
    "Fashion": ["Denim Jacket", "Running Trainers", "Wool Jumper", "Leather Wallet",
                "Summer Dress", "Chino Trousers", "Graphic T-Shirt", "Ankle Boots",
                "Wool Scarf", "Baseball Cap"],
    "Beauty": ["Vitamin C Serum", "Hyaluronic Moisturiser", "Matte Lipstick Set",
               "Hair Dryer", "Facial Cleanser", "SPF 50 Sunscreen", "Perfume 50ml",
               "Electric Shaver"],
    "Sports & Outdoors": ["Yoga Mat", "Adjustable Dumbbells", "Camping Tent 2-Person",
                           "Insulated Water Bottle", "Resistance Bands Set", "Cycling Helmet",
                           "Hiking Backpack"],
    "Books & Media": ["Bestselling Novel", "Cookbook", "Children's Picture Book",
                       "Self-Help Guide", "Graphic Novel", "Puzzle Book"],
    "Toys & Games": ["Building Blocks Set", "Board Game", "Remote Control Car",
                      "Puzzle 1000pc", "Plush Toy", "Art & Craft Kit"],
    "Grocery": ["Organic Coffee Beans", "Protein Bar Box", "Herbal Tea Selection",
                "Olive Oil 1L", "Granola Pack", "Dark Chocolate Bar"],
}

products = []
pid = 1
for cat, info in CATEGORY_INFO.items():
    names_pool = PRODUCT_NAME_WORDS[cat]
    for i in range(info["n"]):
        base_name = random.choice(names_pool)
        name = f"{base_name} {random.choice(['Pro', 'Classic', 'Mini', 'Plus', 'V2', ''])}".strip()
        price = round(np.random.uniform(*info["price"]), 2)
        margin = np.random.uniform(*info["cost_margin"])
        cost = round(price * (1 - margin), 2)

        # sub-category
        sub_category = f"{cat} - General" if random.random() < 0.5 else base_name.split()[0]

        # messiness: inconsistent category case, occasional null/negative cost
        cat_messy = cat if random.random() > 0.08 else cat.lower()
        if random.random() < 0.02:
            cost = None
        elif random.random() < 0.01:
            cost = -abs(cost)  # data entry error

        launch_offset = np.random.randint(0, (END_DATE - START_DATE).days - 60)
        launch_date = START_DATE + timedelta(days=int(launch_offset))

        products.append({
            "product_id": pid,
            "product_name": name,
            "category": cat_messy,
            "sub_category": sub_category,
            "unit_cost": cost,
            "unit_price": price,
            "launch_date": launch_date.isoformat(),
            "_growth_factor": info["growth"],  # internal use only, dropped before saving raw item prices influence
        })
        pid += 1

products_df = pd.DataFrame(products)
growth_lookup = products_df.set_index("product_id")["_growth_factor"].to_dict()
price_lookup = products_df.set_index("product_id")["unit_price"].to_dict()
category_lookup = products_df.set_index("product_id")["category"].apply(lambda c: c.title()).to_dict()

products_out = products_df.drop(columns=["_growth_factor"])
products_out.to_csv(os.path.join(OUT_DIR, "products.csv"), index=False)

# ---------------------------------------------------------------------------
# 3 & 4. ORDERS + ORDER ITEMS
# ---------------------------------------------------------------------------
PAYMENT_METHODS = ["Credit Card", "Debit Card", "PayPal", "Apple Pay", "Klarna"]
PAYMENT_WEIGHTS = [0.32, 0.28, 0.20, 0.12, 0.08]

DISCOUNT_CODES = ["WELCOME10", "SAVE15", "FREESHIP", "BLACKFRIDAY25", "SUMMER20", None, None, None, None]

RETURN_RATE_BY_CATEGORY = {
    "Electronics": 0.07, "Home & Kitchen": 0.05, "Fashion": 0.16, "Beauty": 0.04,
    "Sports & Outdoors": 0.06, "Books & Media": 0.02, "Toys & Games": 0.05, "Grocery": 0.01,
}
CANCEL_RATE = 0.03

def daily_order_volume(d):
    """Baseline daily order count with seasonality, weekday effect, YoY growth, and Black Friday/Christmas spikes."""
    base = 14
    days_elapsed = (d - START_DATE).days
    yoy_growth = 1 + 0.18 * (days_elapsed / 365.0)  # ~18%/yr compounding trend

    month = d.month
    seasonal = {
        1: 0.85, 2: 0.85, 3: 0.90, 4: 0.95, 5: 1.0, 6: 1.0,
        7: 0.80, 8: 0.78, 9: 1.05, 10: 1.05, 11: 1.55, 12: 1.65,
    }[month]

    weekday = d.weekday()  # 0=Mon
    weekday_factor = 1.15 if weekday in (5, 6) else 1.0

    # Black Friday week (last Fri of Nov) and Christmas run-up spike
    spike = 1.0
    if month == 11 and 22 <= d.day <= 29:
        spike = 2.6
    if month == 12 and 1 <= d.day <= 20:
        spike = 1.4
    if month == 12 and d.day in (26, 27):
        spike = 1.8  # Boxing Day sales

    lam = base * yoy_growth * seasonal * weekday_factor * spike
    return np.random.poisson(lam)


orders = []
order_items = []
order_id = 1
order_item_id = 1

customer_ids = customers_df["customer_id"].unique().tolist()
customer_signup = customers_df.drop_duplicates("customer_id").set_index("customer_id")["signup_date"].to_dict()

for d in ALL_DAYS:
    d_date = d.date()
    n_orders = daily_order_volume(d_date)
    for _ in range(n_orders):
        cust_id = random.choice(customer_ids)
        signup = pd.Timestamp(customer_signup.get(cust_id, START_DATE.isoformat())).date()
        if signup > d_date:
            continue  # can't order before signing up

        status_roll = random.random()
        # returns evaluated per-item below; here handle cancellations
        status = "Cancelled" if status_roll < CANCEL_RATE else "Completed"

        payment = np.random.choice(PAYMENT_METHODS, p=PAYMENT_WEIGHTS)
        discount_code = random.choice(DISCOUNT_CODES)
        # Black Friday discount surge
        if d_date.month == 11 and 22 <= d_date.day <= 29 and random.random() < 0.6:
            discount_code = "BLACKFRIDAY25"

        shipping_region = np.random.choice(REGIONS, p=REGION_WEIGHTS)

        # order_date formatting messiness: mix ISO and DD/MM/YYYY strings
        if random.random() < 0.12:
            order_date_str = d_date.strftime("%d/%m/%Y")
        else:
            order_date_str = d_date.isoformat()

        n_items = np.random.choice([1, 2, 3, 4, 5], p=[0.45, 0.28, 0.15, 0.08, 0.04])
        chosen_products = random.sample(list(price_lookup.keys()), k=min(n_items, len(price_lookup)))

        any_returned = False
        for prod_id in chosen_products:
            qty = np.random.choice([1, 2, 3], p=[0.75, 0.18, 0.07])
            base_price = price_lookup[prod_id]
            cat = category_lookup[prod_id]

            # apply category growth trend to price slightly via inflation-like YoY bump (small)
            days_elapsed = (d_date - START_DATE).days
            price_trend = 1 + 0.04 * (days_elapsed / 365.0)
            unit_price_at_sale = round(base_price * price_trend, 2)

            discount_pct = 0.0
            if discount_code == "BLACKFRIDAY25":
                discount_pct = 0.25
            elif discount_code == "SAVE15":
                discount_pct = 0.15
            elif discount_code == "SUMMER20":
                discount_pct = 0.20
            elif discount_code == "WELCOME10":
                discount_pct = 0.10

            # messiness: occasional negative/zero quantity data entry errors
            if random.random() < 0.01:
                qty = -qty
            if random.random() < 0.005:
                unit_price_at_sale = 0.0

            item_returned = "N"
            if status == "Completed" and random.random() < RETURN_RATE_BY_CATEGORY.get(cat, 0.05):
                item_returned = "Y"
                any_returned = True

            order_items.append({
                "order_item_id": order_item_id,
                "order_id": order_id,
                "product_id": prod_id,
                "quantity": qty,
                "unit_price_at_sale": unit_price_at_sale,
                "discount_pct": discount_pct,
                "returned": item_returned,
            })
            order_item_id += 1

        final_status = status
        if status == "Completed" and any_returned and random.random() < 0.4:
            final_status = "Partially Returned"

        orders.append({
            "order_id": order_id,
            "customer_id": cust_id,
            "order_date": order_date_str,
            "order_status": final_status,
            "payment_method": payment,
            "discount_code": discount_code,
            "shipping_region": shipping_region,
        })
        order_id += 1

orders_df = pd.DataFrame(orders)
order_items_df = pd.DataFrame(order_items)

# inject ~1% fully duplicated order rows (double-submitted forms)
dupe_orders = orders_df.sample(frac=0.01, random_state=SEED).copy()
orders_df = pd.concat([orders_df, dupe_orders], ignore_index=True)

orders_df.to_csv(os.path.join(OUT_DIR, "orders.csv"), index=False)
order_items_df.to_csv(os.path.join(OUT_DIR, "order_items.csv"), index=False)

# ---------------------------------------------------------------------------
# 5. MARKETING SPEND (monthly, by channel)
# ---------------------------------------------------------------------------
months = pd.period_range("2023-01", "2024-12", freq="M")
BASE_SPEND = {
    "Organic Search": 0,       # SEO cost tracked separately/omitted (organic = "free" clicks)
    "Paid Social": 4500,
    "Email": 800,
    "Referral": 500,
    "Direct": 0,
    "Affiliate": 1800,
}
rows = []
for m in months:
    d = m.to_timestamp().date()
    progress = (d - START_DATE).days / (END_DATE - START_DATE).days
    seasonal_mult = 1.5 if m.month in (11, 12) else (0.8 if m.month in (7, 8) else 1.0)
    for ch, base in BASE_SPEND.items():
        if base == 0:
            continue
        growth_mult = 1 + (0.6 if ch == "Paid Social" else 0.15) * progress
        noise = np.random.uniform(0.9, 1.1)
        spend = round(base * seasonal_mult * growth_mult * noise, 2)
        rows.append({"month": str(m), "channel": ch, "spend_gbp": spend})

marketing_df = pd.DataFrame(rows)
marketing_df.to_csv(os.path.join(OUT_DIR, "marketing_spend.csv"), index=False)

# ---------------------------------------------------------------------------
print("Generated files:")
for f in ["customers.csv", "products.csv", "orders.csv", "order_items.csv", "marketing_spend.csv"]:
    p = os.path.join(OUT_DIR, f)
    print(f"  {f}: {sum(1 for _ in open(p)) - 1} rows")
