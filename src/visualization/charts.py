"""Statistical charts and visual analytics module for PharmaTrack.

Implements clinical, minimal Matplotlib and Seaborn plotting routines.
Strictly adheres to:
- Solid white backgrounds (#FFFFFF)
- Restrained clinical palette (#2457A7, #237A4B, #A15C00, #B42318, #667085)
- Thin 1px gridlines (#E4E7EC)
- No gradients, dropshadows, or decorative clutter
- Publication-grade typography and clear axis/legend labeling
"""

from typing import List, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for thread safety
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.visualization.theme import (
    COLOR_ACTIVE_NAV,
    COLOR_BORDER,
    COLOR_CRITICAL,
    COLOR_PAGE_BG,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_WARNING,
    apply_chart_theme,
)



def _create_empty_figure(message: str = "No Data Available to Display") -> plt.Figure:
    """Create a standardized placeholder figure when datasets are empty or insufficient."""
    apply_chart_theme()
    fig, ax = plt.subplots(figsize=(8, 3.8), dpi=100)
    ax.text(
        0.5,
        0.5,
        message,
        horizontalalignment="center",
        verticalalignment="center",
        fontsize=11,
        color=COLOR_TEXT_SECONDARY,
        transform=ax.transAxes,
        fontweight="normal",
    )
    ax.set_facecolor(COLOR_PAGE_BG)
    ax.set_axis_off()
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    fig.tight_layout()
    return fig


def plot_revenue_time_series(
    daily_sales_df: pd.DataFrame,
    title: str = "Daily Revenue & 7-Day Moving Average Trend",
) -> plt.Figure:
    """Generate clean clinical time-series line chart with moving average trend."""
    apply_chart_theme()
    if daily_sales_df.empty:
        return _create_empty_figure("No revenue transactions recorded for the selected period.")

    df = daily_sales_df.copy()
    date_col = "date" if "date" in df.columns else "period"
    df["dt"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["dt"]).sort_values("dt")

    if df.empty or "total_revenue" not in df.columns:
        return _create_empty_figure("Invalid time-series data structure.")

    df["rolling_7d"] = df["total_revenue"].rolling(window=7, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    # Daily revenue line (clinical blue)
    ax.plot(
        df["dt"],
        df["total_revenue"],
        color=COLOR_PRIMARY,
        marker="o",
        markersize=3.5,
        linewidth=1.5,
        label="Daily Revenue ($)",
        alpha=0.9,
    )

    # 7-day moving average trend line (clinical amber)
    ax.plot(
        df["dt"],
        df["rolling_7d"],
        color=COLOR_WARNING,
        linestyle="--",
        linewidth=1.8,
        label="7-Day Moving Avg ($)",
    )

    ax.set_title(title, fontsize=12, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_xlabel("Transaction Date", fontsize=9.5, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Gross Revenue ($ USD)", fontsize=9.5, labelpad=6, color=COLOR_TEXT_PRIMARY)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=0, ha="center")

    ax.yaxis.set_major_formatter("${x:,.0f}")
    ax.legend(loc="upper left", frameon=True, facecolor=COLOR_PAGE_BG, edgecolor=COLOR_BORDER)
    fig.tight_layout()

    return fig


def plot_monthly_revenue_line(
    monthly_sales_df: pd.DataFrame,
    title: str = "Monthly Revenue Trend",
) -> plt.Figure:
    """Generate monthly revenue line chart for executive overview."""
    apply_chart_theme()
    if monthly_sales_df.empty or "total_revenue" not in monthly_sales_df.columns:
        return _create_empty_figure("No monthly revenue records available.")

    df = monthly_sales_df.copy()
    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    periods = df["period"].astype(str).tolist()
    revenue = df["total_revenue"].tolist()

    ax.plot(
        periods,
        revenue,
        color=COLOR_PRIMARY,
        marker="s",
        markersize=5,
        linewidth=2.0,
        label="Monthly Revenue ($)",
    )

    if "total_gross_profit" in df.columns:
        ax.plot(
            periods,
            df["total_gross_profit"].tolist(),
            color=COLOR_SUCCESS,
            marker="o",
            markersize=4.5,
            linewidth=1.8,
            linestyle="--",
            label="Gross Profit ($)",
        )

    ax.set_title(title, fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_xlabel("Billing Period", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Amount ($ USD)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.yaxis.set_major_formatter("${x:,.0f}")
    ax.legend(loc="upper left", frameon=True, facecolor=COLOR_PAGE_BG, edgecolor=COLOR_BORDER)
    plt.xticks(rotation=0, ha="center")
    fig.tight_layout()
    return fig


def plot_top_selling_medicines(
    top_df: pd.DataFrame,
    metric: str = "total_revenue",
    top_n: int = 10,
) -> plt.Figure:
    """Generate clean clinical horizontal bar chart of top medicines."""
    apply_chart_theme()
    if top_df.empty:
        return _create_empty_figure("No sales records available to rank medicines.")

    df = top_df.head(top_n).copy()
    if metric not in df.columns:
        metric = "total_revenue" if "total_revenue" in df.columns else df.columns[1]

    df = df.sort_values(by=metric, ascending=True)

    fig, ax = plt.subplots(figsize=(8.5, max(3.8, len(df) * 0.4)), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)
    is_revenue = "revenue" in metric.lower() or "profit" in metric.lower()

    bars = ax.barh(
        df["medicine_name"],
        df[metric],
        color=COLOR_PRIMARY,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
        height=0.6,
    )

    for bar in bars:
        val = bar.get_width()
        label_text = f"${val:,.0f}" if is_revenue else f"{int(val):,} units"
        ax.text(
            val + (df[metric].max() * 0.015),
            bar.get_y() + bar.get_height() / 2,
            label_text,
            va="center",
            ha="left",
            fontsize=8.5,
            fontweight="medium",
            color=COLOR_TEXT_PRIMARY,
        )

    metric_label = "Gross Revenue ($)" if is_revenue else "Quantity Sold (Units)"
    ax.set_title(f"Top {len(df)} Medicines by {metric_label}", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_xlabel(metric_label, fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Medicine", fontsize=9, color=COLOR_TEXT_PRIMARY)
    ax.set_xlim(0, df[metric].max() * 1.20)

    if is_revenue:
        ax.xaxis.set_major_formatter("${x:,.0f}")
    else:
        ax.xaxis.set_major_formatter("{x:,.0f}")

    fig.tight_layout()
    return fig


def plot_category_revenue_profit_comparison(
    category_df: pd.DataFrame,
) -> plt.Figure:
    """Generate clean clinical grouped bar chart comparing Revenue and Gross Profit."""
    apply_chart_theme()
    if category_df.empty or "category" not in category_df.columns:
        return _create_empty_figure("No category sales records available.")

    df = category_df.sort_values(by="total_revenue", ascending=False).head(8).copy()

    fig, ax = plt.subplots(figsize=(9.5, 4.2), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    categories = df["category"].tolist()
    x = np.arange(len(categories))
    width = 0.35

    ax.bar(
        x - width / 2,
        df["total_revenue"],
        width,
        label="Gross Revenue ($)",
        color=COLOR_PRIMARY,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
    )
    ax.bar(
        x + width / 2,
        df["gross_profit"],
        width,
        label="Gross Profit ($)",
        color=COLOR_SUCCESS,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
    )

    ax.set_title("Sales Revenue vs. Gross Profit by Therapeutic Category", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Amount ($ USD)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_xticks(x)
    ax.set_xticklabels(categories, rotation=20, ha="right", fontsize=8.5, color=COLOR_TEXT_PRIMARY)
    ax.yaxis.set_major_formatter("${x:,.0f}")
    ax.legend(frameon=True, facecolor=COLOR_PAGE_BG, edgecolor=COLOR_BORDER, loc="upper right")

    fig.tight_layout()
    return fig


def plot_category_sales_bar(
    category_df: pd.DataFrame,
    title: str = "Sales Revenue by Therapeutic Category",
) -> plt.Figure:
    """Generate minimal clinical bar chart of category sales for Dashboard."""
    apply_chart_theme()
    if category_df.empty or "category" not in category_df.columns:
        return _create_empty_figure("No category sales records available.")

    df = category_df.sort_values(by="total_revenue", ascending=False).head(7).copy()

    fig, ax = plt.subplots(figsize=(7, 3.8), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    bars = ax.bar(
        df["category"],
        df["total_revenue"],
        color=COLOR_PRIMARY,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
        width=0.55,
    )

    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + (df["total_revenue"].max() * 0.02),
            f"${h:,.0f}",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="medium",
            color=COLOR_TEXT_PRIMARY,
        )

    ax.set_title(title, fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Revenue ($ USD)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.yaxis.set_major_formatter("${x:,.0f}")
    ax.set_ylim(0, df["total_revenue"].max() * 1.18)
    plt.xticks(rotation=20, ha="right", fontsize=8.5)

    fig.tight_layout()
    return fig


def plot_expiry_risk_distribution(
    classified_batches_df: pd.DataFrame,
) -> plt.Figure:
    """Generate clean clinical bar chart showing inventory value-at-risk by expiry tier."""
    apply_chart_theme()
    if classified_batches_df.empty or "expiry_classification" not in classified_batches_df.columns:
        return _create_empty_figure("No batch inventory records available for expiry analysis.")

    tier_summary = classified_batches_df.groupby("expiry_classification").agg(
        batch_count=("batch_id", "count"),
        total_units=("quantity", "sum"),
        total_value_at_risk=("value_at_risk", "sum"),
    ).reset_index()

    color_map = {
        "Expired": COLOR_CRITICAL,
        "Expiring Today": COLOR_CRITICAL,
        "Near Expiry (≤30d)": COLOR_WARNING,
        "Near Expiry (≤90d)": COLOR_WARNING,
        "Safe / Healthy": COLOR_SUCCESS,
    }
    palette = [color_map.get(tier, COLOR_PRIMARY) for tier in tier_summary["expiry_classification"]]

    fig, ax1 = plt.subplots(figsize=(8.5, 4.2), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax1.set_facecolor(COLOR_PAGE_BG)

    bars = ax1.bar(
        tier_summary["expiry_classification"],
        tier_summary["total_value_at_risk"],
        color=palette,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
        width=0.52,
    )

    for bar in bars:
        h = bar.get_height()
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + (tier_summary["total_value_at_risk"].max() * 0.02),
            f"${h:,.0f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="semibold",
            color=COLOR_TEXT_PRIMARY,
        )

    ax1.set_title("Inventory Acquisition Value-at-Risk by Expiry Classification", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax1.set_xlabel("Expiry Risk Category", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax1.set_ylabel("Value at Risk ($ USD at Cost)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax1.yaxis.set_major_formatter("${x:,.0f}")
    ax1.set_ylim(0, tier_summary["total_value_at_risk"].max() * 1.18)
    plt.xticks(rotation=15, ha="right", fontsize=8.5)

    fig.tight_layout()
    return fig


def plot_transaction_basket_distribution(
    enriched_sales_df: pd.DataFrame,
) -> plt.Figure:
    """Generate clean clinical boxplot of transaction revenue distribution."""
    apply_chart_theme()
    if enriched_sales_df.empty or "total_revenue" not in enriched_sales_df.columns or "category" not in enriched_sales_df.columns:
        return _create_empty_figure("No transaction data available for statistical distribution analysis.")

    top_categories = enriched_sales_df["category"].value_counts().head(6).index.tolist()
    sub_df = enriched_sales_df[enriched_sales_df["category"].isin(top_categories)].copy()

    fig, ax = plt.subplots(figsize=(9, 4.0), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    sns.boxplot(
        data=sub_df,
        x="category",
        y="total_revenue",
        color=COLOR_ACTIVE_NAV,
        boxprops=dict(edgecolor=COLOR_PRIMARY, linewidth=1.0),
        whiskerprops=dict(color=COLOR_PRIMARY, linewidth=1.0),
        capprops=dict(color=COLOR_PRIMARY, linewidth=1.0),
        medianprops=dict(color=COLOR_CRITICAL, linewidth=1.4),
        flierprops=dict(marker="o", markerfacecolor=COLOR_TEXT_SECONDARY, markersize=3, markeredgecolor="none"),
        ax=ax,
    )

    ax.set_title("Statistical Distribution of Transaction Basket Revenue by Category", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_xlabel("Therapeutic Category", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Transaction Revenue ($)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.yaxis.set_major_formatter("${x:,.0f}")
    plt.xticks(rotation=20, ha="right", fontsize=8.5)

    fig.tight_layout()
    return fig


def plot_sales_correlation_heatmap(
    enriched_sales_df: pd.DataFrame,
) -> plt.Figure:
    """Generate clean clinical correlation matrix across numerical sales features."""
    apply_chart_theme()
    if enriched_sales_df.empty or len(enriched_sales_df) < 5:
        return _create_empty_figure("Insufficient transactions to compute statistical correlation heatmap.")

    candidate_cols = ["quantity_sold", "unit_price", "purchase_price", "total_revenue", "total_cogs", "gross_profit"]
    valid_cols = [c for c in candidate_cols if c in enriched_sales_df.columns]

    if len(valid_cols) < 3:
        return _create_empty_figure("Insufficient numerical features for correlation matrix.")

    corr = enriched_sales_df[valid_cols].corr()

    labels = {
        "quantity_sold": "Units Sold",
        "unit_price": "Unit Price",
        "purchase_price": "Batch Cost",
        "total_revenue": "Revenue",
        "total_cogs": "COGS",
        "gross_profit": "Gross Profit",
    }
    corr_renamed = corr.rename(index=labels, columns=labels)

    fig, ax = plt.subplots(figsize=(7, 5.0), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    sns.heatmap(
        corr_renamed,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        vmin=-1,
        vmax=1,
        linewidths=0.6,
        linecolor=COLOR_BORDER,
        cbar_kws={"label": "Pearson Correlation (r)", "shrink": 0.8},
        ax=ax,
        square=True,
        annot_kws={"size": 8.5, "weight": "medium"},
    )

    ax.set_title("Correlation Matrix of Transactional Financial Metrics", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    plt.xticks(rotation=30, ha="right", fontsize=8.5)
    plt.yticks(rotation=0, fontsize=8.5)

    fig.tight_layout()
    return fig


def plot_stock_levels_vs_reorder(
    medicine_summary_df: pd.DataFrame,
    top_n: int = 14,
) -> plt.Figure:
    """Generate clean clinical comparison of Usable Stock vs. Safety Reorder Level."""
    apply_chart_theme()
    if medicine_summary_df.empty or "usable_quantity" not in medicine_summary_df.columns:
        return _create_empty_figure("No medicine inventory stock data available.")

    df = medicine_summary_df.sort_values(by=["is_low_stock", "usable_quantity"], ascending=[False, True]).head(top_n).copy()

    fig, ax = plt.subplots(figsize=(9.5, 4.2), dpi=100)
    fig.patch.set_facecolor(COLOR_PAGE_BG)
    ax.set_facecolor(COLOR_PAGE_BG)

    x = np.arange(len(df))
    width = 0.38

    ax.bar(
        x - width / 2,
        df["usable_quantity"],
        width,
        label="Usable Stock (Units)",
        color=COLOR_PRIMARY,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
    )
    ax.bar(
        x + width / 2,
        df["reorder_level"],
        width,
        label="Reorder Level (Units)",
        color=COLOR_CRITICAL,
        edgecolor=COLOR_BORDER,
        linewidth=0.8,
    )

    ax.set_title(f"Usable Stock vs. Safety Reorder Level (Top {len(df)} Focus Items)", fontsize=11.5, fontweight="semibold", pad=10, loc="left", color=COLOR_TEXT_PRIMARY)
    ax.set_ylabel("Quantity (Units)", fontsize=9, labelpad=6, color=COLOR_TEXT_PRIMARY)
    ax.set_xticks(x)
    ax.set_xticklabels(df["medicine_name"], rotation=30, ha="right", fontsize=8.5, color=COLOR_TEXT_PRIMARY)
    ax.legend(frameon=True, facecolor=COLOR_PAGE_BG, edgecolor=COLOR_BORDER, loc="upper right")

    fig.tight_layout()
    return fig
