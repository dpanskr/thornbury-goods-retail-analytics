"""
eda.py
------
Exploratory Data Analysis for the Thornbury Goods synthetic retail dataset.

Reads the analysis-ready CSVs exported by load_to_sqlite.py (data/cleaned/)
and produces a set of publication-ready PNG charts (charts/) plus a short
printed summary of headline numbers used in the README.

Run: python3 eda.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os

BASE = os.path.dirname(__file__)
CLEANED = os.path.join(BASE, "..", "data", "cleaned")
CHARTS = os.path.join(BASE, "..", "charts")
os.makedirs(CHARTS, exist_ok=True)

# ---------------------------------------------------------------------------
# Palette (validated categorical order + sequential blue ramp — see the
# dataviz design-system reference used for this project)
# ---------------------------------------------------------------------------
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
               "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95"]
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


def style_ax(ax):
    ax.grid(axis="y", alpha=0.6)
    ax.grid(axis="x", visible=False)
    ax.spines["left"].set_color(GRIDLINE)
    ax.spines["bottom"].set_color("#c3c2b7")
    return ax


def gbp(x, pos=None):
    if x >= 1_000_000:
        return f"£{x/1_000_000:.1f}M"
    if x >= 1_000:
        return f"£{x/1_000:.0f}k"
    return f"£{x:.0f}"


# ===========================================================================
# 1. Monthly revenue & order volume trend
# ===========================================================================
trend = pd.read_csv(os.path.join(CLEANED, "vw_monthly_trend.csv"))
trend["order_month"] = pd.to_datetime(trend["order_month"])

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                          gridspec_kw={"height_ratios": [2, 1]})

axes[0].plot(trend["order_month"], trend["revenue"], color=CATEGORICAL[0],
             linewidth=2.5, marker="o", markersize=4)
axes[0].fill_between(trend["order_month"], trend["revenue"], color=CATEGORICAL[0], alpha=0.08)
axes[0].set_title("Thornbury Goods Monthly Revenue: Launch (Jan 2023) Through Dec 2024")
axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(gbp))
style_ax(axes[0])
# annotate Black Friday spikes
for yr in [2023, 2024]:
    bf = trend[(trend["order_month"].dt.year == yr) & (trend["order_month"].dt.month == 11)]
    if not bf.empty:
        axes[0].annotate("Black Friday /\nholiday peak", xy=(bf["order_month"].iloc[0], bf["revenue"].iloc[0]),
                          xytext=(10, 15), textcoords="offset points", fontsize=9, color=INK_SECONDARY)

axes[1].bar(trend["order_month"], trend["orders"], color=CATEGORICAL[2], width=20)
axes[1].set_title("Monthly Order Count", fontsize=11)
style_ax(axes[1])
axes[1].set_xlabel("")

fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "01_monthly_revenue_trend.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 2. Category revenue trend — small multiples (avoids an 8-line spaghetti chart)
# ===========================================================================
cat_perf = pd.read_csv(os.path.join(CLEANED, "vw_category_performance.csv"))
categories = sorted(cat_perf["category"].unique())

fig, axes = plt.subplots(2, 4, figsize=(15, 6), sharex=True)
axes = axes.flatten()
for i, cat in enumerate(categories):
    sub = cat_perf[cat_perf["category"] == cat].sort_values("year")
    ax = axes[i]
    color = CATEGORICAL[i % len(CATEGORICAL)]
    ax.bar(sub["year"].astype(str), sub["revenue"], color=color, width=0.55)
    ax.set_title(cat, fontsize=10, color=INK_PRIMARY)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(gbp))
    style_ax(ax)
    ax.tick_params(axis="both", labelsize=8)

fig.suptitle("Revenue by Category, 2023 vs 2024 — Beauty & Electronics Are Growing Fastest,\nBooks & Media Is Shrinking",
             fontsize=13, fontweight="bold", y=1.03)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "02_category_revenue_small_multiples.png"), dpi=150, bbox_inches="tight")
plt.close(fig)

# ===========================================================================
# 3. Category quadrant: revenue vs margin (2024), bubble = order count
# ===========================================================================
cat_2024 = cat_perf[cat_perf["year"] == 2024].copy()

fig, ax = plt.subplots(figsize=(9, 7))
for i, row in cat_2024.reset_index(drop=True).iterrows():
    color = CATEGORICAL[categories.index(row["category"]) % len(CATEGORICAL)]
    ax.scatter(row["margin_pct"], row["revenue"], s=row["orders"] / 2, color=color,
               alpha=0.85, edgecolor="white", linewidth=1.2, zorder=3)
    ax.annotate(row["category"], (row["margin_pct"], row["revenue"]),
                xytext=(8, 6), textcoords="offset points", fontsize=9.5, color=INK_PRIMARY)

ax.axvline(cat_2024["margin_pct"].mean(), color=INK_MUTED, linestyle="--", linewidth=1, alpha=0.6)
ax.axhline(cat_2024["revenue"].mean(), color=INK_MUTED, linestyle="--", linewidth=1, alpha=0.6)
ax.set_xlabel("Gross Margin %")
ax.set_ylabel("2024 Revenue")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(gbp))
ax.set_title("2024 Category Quadrant — Revenue vs. Margin\n(bubble size = number of orders)")
style_ax(ax)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "03_category_quadrant.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 4. Weekday demand pattern
# ===========================================================================
weekday = pd.read_csv(os.path.join(CLEANED, "vw_weekday_pattern.csv"))
order_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday["order_weekday"] = pd.Categorical(weekday["order_weekday"], categories=order_map, ordered=True)
weekday = weekday.sort_values("order_weekday")

fig, ax = plt.subplots(figsize=(9, 5.5))
colors = [CATEGORICAL[1] if d in ("Saturday", "Sunday") else CATEGORICAL[0] for d in weekday["order_weekday"]]
ax.bar(weekday["order_weekday"], weekday["orders"], color=colors, width=0.6)
ax.set_title("Orders by Day of Week — Weekends Outperform (Highlighted)")
ax.set_ylabel("Total Orders (2023–2024)")
style_ax(ax)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "04_weekday_pattern.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 5. Acquisition channel mix over time (share of orders, stacked area)
# ===========================================================================
facts = pd.read_csv(os.path.join(CLEANED, "vw_order_facts.csv"))
channel_month = (facts.groupby(["order_month", "acquisition_channel"])["order_id"]
                  .nunique().reset_index(name="orders"))
channel_pivot = channel_month.pivot(index="order_month", columns="acquisition_channel", values="orders").fillna(0)
channel_share = channel_pivot.div(channel_pivot.sum(axis=1), axis=0)
channel_share.index = pd.to_datetime(channel_share.index)
channel_share = channel_share.sort_index()

channel_order = ["Organic Search", "Paid Social", "Email", "Referral", "Direct", "Affiliate"]
channel_share = channel_share[[c for c in channel_order if c in channel_share.columns]]

fig, ax = plt.subplots(figsize=(11, 6))
ax.stackplot(channel_share.index, [channel_share[c] for c in channel_share.columns],
             labels=channel_share.columns, colors=CATEGORICAL[:len(channel_share.columns)], alpha=0.9)
ax.set_title("Acquisition Channel Mix Over Time — Paid Social Share Is Rising as Organic Declines")
ax.set_ylabel("Share of Orders")
ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=9)
style_ax(ax)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "05_channel_mix_over_time.png"), dpi=150, bbox_inches="tight")
plt.close(fig)

# ===========================================================================
# 6. Channel efficiency — revenue per £1 of marketing spend
# ===========================================================================
chan_eff = pd.read_csv(os.path.join(CLEANED, "vw_channel_efficiency.csv"))
chan_eff_agg = (chan_eff.dropna(subset=["spend_gbp"])
                .groupby("channel")[["revenue", "spend_gbp"]].sum().reset_index())
chan_eff_agg["revenue_per_pound"] = chan_eff_agg["revenue"] / chan_eff_agg["spend_gbp"]
chan_eff_agg = chan_eff_agg.sort_values("revenue_per_pound", ascending=True)

fig, ax = plt.subplots(figsize=(9, 5))
colors = [CATEGORICAL[channel_order.index(c) % len(CATEGORICAL)] if c in channel_order else INK_MUTED
          for c in chan_eff_agg["channel"]]
bars = ax.barh(chan_eff_agg["channel"], chan_eff_agg["revenue_per_pound"], color=colors)
for b, v in zip(bars, chan_eff_agg["revenue_per_pound"]):
    ax.annotate(f"£{v:.1f}", (v, b.get_y() + b.get_height() / 2), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=9.5, color=INK_PRIMARY)
ax.set_title("Revenue Generated per £1 of Marketing Spend, by Paid Channel\n(2023–2024, Organic/Direct excluded — no media spend)")
ax.set_xlabel("£ Revenue per £1 Spend")
style_ax(ax)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "06_channel_efficiency.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 7. Cohort retention heatmap (sequential blue ramp)
# ===========================================================================
cohort = pd.read_csv(os.path.join(CLEANED, "vw_cohort_retention.csv"))
cohort_sizes = cohort[cohort["months_since_first_purchase"] == 0].set_index("cohort_month")["active_customers"]
pivot = cohort.pivot(index="cohort_month", columns="months_since_first_purchase", values="active_customers")
retention_pct = pivot.div(cohort_sizes, axis=0) * 100
# keep a readable window: first 12 months since first purchase, cohorts with enough follow-up history
retention_pct = retention_pct.loc[:, [c for c in retention_pct.columns if 0 <= c <= 11]]
retention_pct = retention_pct[retention_pct.index <= "2024-06"]  # need >=6mo of follow-up to be meaningful

fig, ax = plt.subplots(figsize=(11, 7))
im = ax.imshow(retention_pct.values, cmap="Blues", vmin=0, vmax=60, aspect="auto")
ax.set_xticks(range(retention_pct.shape[1]))
ax.set_xticklabels(retention_pct.columns.astype(int))
ax.set_yticks(range(retention_pct.shape[0]))
ax.set_yticklabels(retention_pct.index)
ax.set_xlabel("Months Since First Purchase")
ax.set_ylabel("Acquisition Cohort (first purchase month)")
ax.set_title("Monthly Cohort Retention (% of Cohort Still Active)")
for i in range(retention_pct.shape[0]):
    for j in range(retention_pct.shape[1]):
        val = retention_pct.values[i, j]
        if not np.isnan(val):
            txt_color = "white" if val > 32 else INK_PRIMARY
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=7.5, color=txt_color)
cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("% Retained", color=INK_SECONDARY)
ax.grid(False)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "07_cohort_retention_heatmap.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 8. Return rate by category (sorted bar)
# ===========================================================================
returns_2024 = cat_perf[cat_perf["year"] == 2024].sort_values("return_rate_pct", ascending=True)

fig, ax = plt.subplots(figsize=(9, 5.5))
colors = [CATEGORICAL[categories.index(c) % len(CATEGORICAL)] for c in returns_2024["category"]]
bars = ax.barh(returns_2024["category"], returns_2024["return_rate_pct"], color=colors)
for b, v in zip(bars, returns_2024["return_rate_pct"]):
    ax.annotate(f"{v:.1f}%", (v, b.get_y() + b.get_height() / 2), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=9.5, color=INK_PRIMARY)
ax.set_title("Return Rate by Category (2024)\nFashion Returns Nearly 4x the Store Average")
ax.set_xlabel("Return Rate (%)")
style_ax(ax)
fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "08_return_rate_by_category.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# 9. Customer value distribution (RFM monetary) — histogram + segment split
# ===========================================================================
rfm = pd.read_csv(os.path.join(CLEANED, "vw_customer_rfm.csv"))
q1, q2, q3 = rfm["monetary"].quantile([0.5, 0.8, 0.95])

def segment(m):
    if m >= q3:
        return "Top spenders (top 5%)"
    if m >= q2:
        return "High value (next 15%)"
    if m >= q1:
        return "Core (next 30%)"
    return "Occasional (bottom 50%)"

rfm["segment"] = rfm["monetary"].apply(segment)
seg_order = ["Occasional (bottom 50%)", "Core (next 30%)", "High value (next 15%)", "Top spenders (top 5%)"]
seg_summary = (rfm.groupby("segment")
               .agg(customers=("customer_id", "count"), total_revenue=("monetary", "sum"))
               .reindex(seg_order))
seg_summary["revenue_share"] = seg_summary["total_revenue"] / seg_summary["total_revenue"].sum() * 100

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
axes[0].hist(rfm["monetary"], bins=50, color=CATEGORICAL[0], alpha=0.85)
axes[0].set_title("Distribution of Customer Lifetime Spend")
axes[0].set_xlabel("Total Spend (£)")
axes[0].set_ylabel("Number of Customers")
axes[0].xaxis.set_major_formatter(mticker.FuncFormatter(gbp))
style_ax(axes[0])

colors9 = [CATEGORICAL[0], CATEGORICAL[2], CATEGORICAL[3], CATEGORICAL[1]]
axes[1].bar(seg_summary.index, seg_summary["revenue_share"], color=colors9)
for i, (idx, row) in enumerate(seg_summary.iterrows()):
    axes[1].annotate(f"{row['revenue_share']:.0f}% of revenue\n({row['customers']:.0f} customers)",
                      (i, row["revenue_share"]), xytext=(0, 6), textcoords="offset points",
                      ha="center", fontsize=8.5, color=INK_PRIMARY)
axes[1].set_title("Revenue Concentration by Customer Segment")
axes[1].set_ylabel("Share of Total Revenue (%)")
axes[1].set_xticks(range(len(seg_summary.index)))
axes[1].set_xticklabels(seg_summary.index, rotation=18, ha="right", fontsize=8.5)
axes[1].set_ylim(0, seg_summary["revenue_share"].max() * 1.25)
style_ax(axes[1])

fig.tight_layout()
fig.savefig(os.path.join(CHARTS, "09_customer_value_segments.png"), dpi=150)
plt.close(fig)

# ===========================================================================
# Headline numbers for the README
# ===========================================================================
total_revenue = facts["net_revenue"].sum()
total_orders = facts["order_id"].nunique()
total_customers = facts["customer_id"].nunique()
aov = total_revenue / total_orders
rev_2023 = trend[trend["order_month"].dt.year == 2023]["revenue"].sum()
rev_2024 = trend[trend["order_month"].dt.year == 2024]["revenue"].sum()
yoy_growth = (rev_2024 / rev_2023 - 1) * 100
top_seg_share = seg_summary.loc["Top spenders (top 5%)", "revenue_share"]
fashion_return = cat_perf[(cat_perf.category == "Fashion") & (cat_perf.year == 2024)]["return_rate_pct"].values[0]
avg_return = facts["returned"].mean() * 100
best_channel = chan_eff_agg.sort_values("revenue_per_pound", ascending=False).iloc[0]

print("=" * 70)
print("HEADLINE NUMBERS (for README)")
print("=" * 70)
print(f"Total net revenue (2023-2024):     £{total_revenue:,.0f}")
print(f"Total completed orders:             {total_orders:,}")
print(f"Unique purchasing customers:        {total_customers:,}")
print(f"Average order value:                £{aov:,.2f}")
print(f"2023 revenue:                       £{rev_2023:,.0f}")
print(f"2024 revenue:                       £{rev_2024:,.0f}")
print(f"YoY revenue growth:                 {yoy_growth:,.0f}%")
print(f"Top 5% of customers drive:          {top_seg_share:.0f}% of revenue")
print(f"Fashion return rate (2024):         {fashion_return:.1f}%")
print(f"Store-wide average return rate:     {avg_return:.1f}%")
print(f"Best paid channel (£ rev / £1 spend): {best_channel['channel']} (£{best_channel['revenue_per_pound']:.1f})")
print("=" * 70)
print(f"\nCharts written to: {os.path.abspath(CHARTS)}")
