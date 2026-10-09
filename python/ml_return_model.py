"""
ml_return_model.py
------------------
Return prediction model for the Thornbury Goods dataset.

Predicts whether an order line item gets returned, using only info available
at checkout. Trains on Jan 2023 - Jun 2024, tests on Jul - Dec 2024, and
compares a simple category baseline against logistic regression and
gradient boosting. Writes two charts to charts/ and a results table to
data/cleaned/model_results.csv.

Run: python3 ml_return_model.py  (after load_to_sqlite.py)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

SEED = 42
BASE = os.path.dirname(__file__)
CLEANED = os.path.join(BASE, "..", "data", "cleaned")
CHARTS = os.path.join(BASE, "..", "charts")
os.makedirs(CHARTS, exist_ok=True)

# same palette/styling as eda.py
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
               "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "axes.edgecolor": GRIDLINE,
    "axes.labelcolor": INK_SECONDARY,
    "text.color": INK_PRIMARY,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "axes.grid": True,
    "grid.color": GRIDLINE,
    "grid.linewidth": 0.8,
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# return rates hardcoded in generate_data.py, used to sanity check the model
GENERATOR_RETURN_RATE = {
    "Electronics": 0.07, "Home & Kitchen": 0.05, "Fashion": 0.16, "Beauty": 0.04,
    "Sports & Outdoors": 0.06, "Books & Media": 0.02, "Toys & Games": 0.05, "Grocery": 0.01,
}

# ===========================================================================
# 1. Feature table (one row per line item)
# ===========================================================================
facts = pd.read_csv(os.path.join(CLEANED, "vw_order_facts.csv"), parse_dates=["order_date", "signup_date"])
customers = pd.read_csv(os.path.join(CLEANED, "clean_customers.csv"))
df = facts.merge(customers[["customer_id", "age_approx", "marketing_opt_in"]], on="customer_id", how="left")

df["basket_size"] = df.groupby("order_id")["order_item_id"].transform("count")
df["has_discount_code"] = df["discount_code"].notna().astype(int)
df["is_weekend"] = df["order_weekday"].isin(["Saturday", "Sunday"]).astype(int)
df["order_month_num"] = df["order_date"].dt.month
df["tenure_days"] = (df["order_date"] - df["signup_date"]).dt.days.clip(lower=0)

# customer return history, only counting days BEFORE the current order
daily = (df.groupby(["customer_id", "order_date"])
           .agg(prior_items=("returned", "size"), prior_returns=("returned", "sum"))
           .sort_index())
history = daily.groupby(level=0).cumsum() - daily
df = df.join(history, on=["customer_id", "order_date"])

# order_status left out on purpose: "Partially Returned" leaks the target
CAT_COLS = ["category", "payment_method", "shipping_region", "acquisition_channel"]
NUM_COLS = ["unit_price_at_sale", "quantity", "discount_pct", "has_discount_code",
            "is_weekend", "order_month_num", "basket_size", "tenure_days",
            "age_approx", "marketing_opt_in", "prior_items", "prior_returns"]
FEATURES = CAT_COLS + NUM_COLS

# ===========================================================================
# 2. Train/test split by date
# ===========================================================================
train = df[df["order_date"] < "2024-07-01"]
test = df[df["order_date"] >= "2024-07-01"]
X_train, y_train = train[FEATURES], train["returned"]
X_test, y_test = test[FEATURES], test["returned"]

print(f"Train: {len(train):,} items, {y_train.mean():.1%} returned")
print(f"Test:  {len(test):,} items, {y_test.mean():.1%} returned")

# ===========================================================================
# 3. Models
# ===========================================================================
# baseline: just predict the category's return rate from the training period
cat_rate = train.groupby("category")["returned"].mean()
baseline_pred = X_test["category"].map(cat_rate).fillna(y_train.mean()).values

logreg = Pipeline([
    ("prep", ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ("num", StandardScaler(), NUM_COLS),
    ])),
    ("model", LogisticRegression(max_iter=2000)),
])

gbm = Pipeline([
    ("prep", ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS),
        ("num", "passthrough", NUM_COLS),
    ])),
    ("model", HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                             min_samples_leaf=50, l2_regularization=1.0,
                                             random_state=SEED)),
])

logreg.fit(X_train, y_train)
gbm.fit(X_train, y_train)

preds = {
    "Category baseline": baseline_pred,
    "Logistic regression": logreg.predict_proba(X_test)[:, 1],
    "Gradient boosting": gbm.predict_proba(X_test)[:, 1],
}

# ===========================================================================
# 4. Evaluation
# ===========================================================================
def top10_capture(y_true, scores):
    # what share of all returns are in the riskiest 10% of items
    y_true = np.asarray(y_true)
    top = np.argsort(-scores)[:int(len(scores) * 0.1)]
    return y_true[top].sum() / y_true.sum()

results = pd.DataFrame([{
    "model": name,
    "roc_auc": roc_auc_score(y_test, p),
    "avg_precision": average_precision_score(y_test, p),
    "brier": brier_score_loss(y_test, p),
    "top10_capture": top10_capture(y_test, p),
} for name, p in preds.items()]).round(3)
results.to_csv(os.path.join(CLEANED, "model_results.csv"), index=False)

print(f"\nRandom guess: ROC AUC 0.5, avg precision {y_test.mean():.3f}, top 10% capture 0.10")
print(results.to_string(index=False))

# ===========================================================================
# 5. Permutation importance (logistic regression)
# ===========================================================================
perm = permutation_importance(logreg, X_test, y_test, scoring="roc_auc", n_repeats=20, random_state=SEED)
imp = pd.DataFrame({"feature": FEATURES, "drop": perm.importances_mean, "std": perm.importances_std})
imp = imp.sort_values("drop")

print("\nPermutation importance (ROC AUC drop):")
print(imp.sort_values("drop", ascending=False).round(4).to_string(index=False))

fig, ax = plt.subplots(figsize=(9, 6))
colors = [CATEGORICAL[0] if v > 0.01 else INK_MUTED for v in imp["drop"]]
ax.barh(imp["feature"], imp["drop"], xerr=imp["std"], color=colors, error_kw={"ecolor": INK_MUTED, "lw": 1})
ax.axvline(0, color="#c3c2b7", linewidth=1)
ax.grid(axis="y", visible=False)
ax.set_xlabel("Drop in ROC AUC When Feature Is Shuffled")
ax.set_title("Return Model Feature Importance: Category Does Almost All the Work")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "10_return_model_feature_importance.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 6. Predicted vs actual return rate by category
# ===========================================================================
check = test[["category", "returned"]].copy()
check["predicted"] = preds["Logistic regression"]
by_cat = check.groupby("category").agg(actual=("returned", "mean"), predicted=("predicted", "mean"))
by_cat["generator_rate"] = by_cat.index.map(GENERATOR_RETURN_RATE)
by_cat = by_cat.sort_values("generator_rate")
print("\nReturn rate by category (test set):")
print(by_cat.round(3).to_string())

fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(len(by_cat))
ax.bar(x - 0.19, by_cat["predicted"], 0.38, color=CATEGORICAL[0], label="Predicted (avg)")
ax.bar(x + 0.19, by_cat["actual"], 0.38, color="#9ec5f4", label="Actual, Jul-Dec 2024")
ax.scatter(x, by_cat["generator_rate"], color=CATEGORICAL[1], marker="D", s=40, zorder=3,
           label="Rate set in generate_data.py")
ax.set_xticks(x)
ax.set_xticklabels(by_cat.index, rotation=25, ha="right")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))
ax.grid(axis="x", visible=False)
ax.set_ylabel("Return Rate")
ax.set_title("Predicted vs. Actual Return Rate by Category (Test Set)")
ax.legend(frameon=False, loc="upper left")
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "11_return_model_by_category.png"), dpi=150)
plt.close(fig)
