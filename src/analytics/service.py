"""Medicine sales and revenue analytics service for PharmaTrack.

Provides periodic sales summaries (daily, weekly, monthly), revenue by medicine/category,
top-selling rankings, slow-moving medicine identification, true batch-level COGS and
gross profit analysis, statistical price/quantity distributions, trend forecasting,
and CSV summary exports.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from config import (
    DATE_FORMAT,
    EXPORTS_DIR,
    REFERENCE_DATE,
)

# Standard analytical disclaimer regarding historical demand forecasting limitations
DEMAND_ESTIMATE_DISCLAIMER: str = (
    "Historical demand estimates are descriptive and moving-average statistical projections "
    "based strictly on historical transaction frequency and volume. They do not account for "
    "external healthcare externalities such as clinical seasonality, disease outbreaks, "
    "formulary updates, patient demographic shifts, or supply-chain disruptions. These "
    "estimates should serve as planning heuristics, not definitive clinical forecasts."
)


def _parse_date(dt: Optional[Union[str, datetime, pd.Timestamp]]) -> Optional[pd.Timestamp]:
    """Normalize date input to pd.Timestamp."""
    if dt is None:
        return None
    if isinstance(dt, (datetime, pd.Timestamp)):
        return pd.to_datetime(dt).normalize()
    return pd.to_datetime(str(dt).strip())


def prepare_enriched_sales(
    sales_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    medicines_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join sales transactions with actual batch inventory and medicine catalog metadata.

    Calculates transaction-level revenue, batch-specific Cost of Goods Sold (COGS),
    gross profit, and profit margin.

    Important: Uses the actual batch purchase price associated with the batch sold,
    preserving historical margin fidelity rather than current inventory valuation.

    Args:
        sales_df: Sales transactions DataFrame.
        inventory_df: Batch inventory DataFrame containing batch purchase prices.
        medicines_df: Medicine catalog DataFrame.

    Returns:
        Enriched DataFrame with joined attributes and computed profit metrics.
    """
    expected_cols = [
        "sale_id",
        "date",
        "batch_id",
        "medicine_id",
        "medicine_name",
        "category",
        "supplier",
        "quantity_sold",
        "unit_price",
        "purchase_price",
        "total_revenue",
        "total_cogs",
        "gross_profit",
        "margin_pct",
        "year_month",
        "year_week",
    ]

    if sales_df.empty or inventory_df.empty or medicines_df.empty:
        return pd.DataFrame(columns=expected_cols)

    sal = sales_df.copy()
    inv = inventory_df.copy()
    med = medicines_df.copy()

    # Clean data types
    sal["quantity_sold"] = pd.to_numeric(sal["quantity_sold"], errors="coerce").fillna(0).astype(int)
    sal["unit_price"] = pd.to_numeric(sal["unit_price"], errors="coerce").fillna(0.0).astype(float)
    sal["date"] = pd.to_datetime(sal["date"], errors="coerce")

    inv["purchase_price"] = pd.to_numeric(inv["purchase_price"], errors="coerce").fillna(0.0).astype(float)

    # 1. Join sales with inventory batches (inner join to capture batch purchase cost)
    batch_cols = ["batch_id", "medicine_id", "purchase_price", "supplier"]
    sales_with_batch = pd.merge(sal, inv[batch_cols], on="batch_id", how="inner")

    # 2. Join with medicines master
    med_cols = ["medicine_id", "medicine_name", "category"]
    enriched = pd.merge(sales_with_batch, med[med_cols], on="medicine_id", how="inner")

    if enriched.empty:
        return pd.DataFrame(columns=expected_cols)

    # Vectorized numerical computations with NumPy
    qty = enriched["quantity_sold"].to_numpy()
    unit_p = enriched["unit_price"].to_numpy()
    purch_p = enriched["purchase_price"].to_numpy()

    revenue = np.round(qty * unit_p, 2)
    cogs = np.round(qty * purch_p, 2)
    profit = np.round(revenue - cogs, 2)

    # Profit margin safely avoiding division by zero
    margin_pct = np.where(revenue > 0, np.round((profit / revenue) * 100.0, 2), 0.0)

    enriched["total_revenue"] = revenue
    enriched["total_cogs"] = cogs
    enriched["gross_profit"] = profit
    enriched["margin_pct"] = margin_pct

    # Time period groupings
    enriched["year_month"] = enriched["date"].dt.strftime("%Y-%m")
    enriched["year_week"] = enriched["date"].dt.strftime("%Y-W%W")

    return enriched.sort_values(by=["date", "sale_id"]).reset_index(drop=True)


def get_periodic_sales_summary(
    enriched_sales_df: pd.DataFrame,
    freq: str = "D",
) -> pd.DataFrame:
    """Aggregate sales and profit metrics over daily, weekly, or monthly intervals.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.
        freq: Frequency string - 'D' (daily), 'W' (weekly), or 'M' (monthly).

    Returns:
        Aggregated time series DataFrame.
    """
    freq = freq.upper()
    if freq not in ("D", "W", "M"):
        raise ValueError("Frequency must be one of: 'D' (daily), 'W' (weekly), 'M' (monthly)")

    if enriched_sales_df.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "transaction_count",
                "total_units_sold",
                "total_revenue",
                "total_cogs",
                "total_gross_profit",
                "gross_margin_pct",
                "avg_order_value",
                "avg_units_per_order",
            ]
        )

    df = enriched_sales_df.copy()
    df["period_dt"] = pd.to_datetime(df["date"])

    # Define period label formatting based on frequency
    if freq == "D":
        grouper = pd.Grouper(key="period_dt", freq="D")
        period_format = "%Y-%m-%d"
    elif freq == "W":
        grouper = pd.Grouper(key="period_dt", freq="W-MON")
        period_format = "%Y-W%W"
    else:  # 'M'
        grouper = pd.Grouper(key="period_dt", freq="MS")
        period_format = "%Y-%m"

    grouped = df.groupby(grouper).agg(
        transaction_count=("sale_id", "count"),
        total_units_sold=("quantity_sold", "sum"),
        total_revenue=("total_revenue", "sum"),
        total_cogs=("total_cogs", "sum"),
        total_gross_profit=("gross_profit", "sum"),
    ).reset_index()

    # Drop intervals with zero transactions
    grouped = grouped[grouped["transaction_count"] > 0].copy()

    # Calculate ratios using NumPy
    rev = grouped["total_revenue"].to_numpy()
    profit = grouped["total_gross_profit"].to_numpy()
    tx_count = grouped["transaction_count"].to_numpy()
    units = grouped["total_units_sold"].to_numpy()

    grouped["gross_margin_pct"] = np.where(rev > 0, np.round((profit / rev) * 100.0, 2), 0.0)
    grouped["avg_order_value"] = np.where(tx_count > 0, np.round(rev / tx_count, 2), 0.0)
    grouped["avg_units_per_order"] = np.where(tx_count > 0, np.round(units / tx_count, 1), 0.0)

    # Format period label
    grouped["period"] = grouped["period_dt"].dt.strftime(period_format)
    grouped.drop(columns=["period_dt"], inplace=True)

    # Reorder columns
    cols = [
        "period",
        "transaction_count",
        "total_units_sold",
        "total_revenue",
        "total_cogs",
        "total_gross_profit",
        "gross_margin_pct",
        "avg_order_value",
        "avg_units_per_order",
    ]
    return grouped[cols].reset_index(drop=True)


def get_sales_by_dimension(
    enriched_sales_df: pd.DataFrame,
    dimension: str = "medicine",
    start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Aggregate sales metrics across medicines or therapeutic categories with date filtering.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.
        dimension: 'medicine' or 'category'.
        start_date: Optional filter start date (inclusive).
        end_date: Optional filter end date (inclusive).

    Returns:
        Aggregated dimensional DataFrame.
    """
    dim_key = "medicine_name" if dimension.lower() == "medicine" else "category"
    if dim_key not in enriched_sales_df.columns:
        dim_key = "category"

    if enriched_sales_df.empty:
        return pd.DataFrame(
            columns=[
                dim_key,
                "transaction_count",
                "units_sold",
                "total_revenue",
                "total_cogs",
                "gross_profit",
                "gross_margin_pct",
                "avg_selling_price",
            ]
        )

    df = enriched_sales_df.copy()

    # Apply date filters if provided
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)
    if start_dt is not None:
        df = df[df["date"] >= start_dt]
    if end_dt is not None:
        df = df[df["date"] <= end_dt]

    if df.empty:
        return pd.DataFrame(
            columns=[
                dim_key,
                "transaction_count",
                "units_sold",
                "total_revenue",
                "total_cogs",
                "gross_profit",
                "gross_margin_pct",
                "avg_selling_price",
            ]
        )

    grouped = df.groupby(dim_key).agg(
        transaction_count=("sale_id", "count"),
        units_sold=("quantity_sold", "sum"),
        total_revenue=("total_revenue", "sum"),
        total_cogs=("total_cogs", "sum"),
        gross_profit=("gross_profit", "sum"),
    ).reset_index()

    # Derived statistical metrics
    rev = grouped["total_revenue"].to_numpy()
    profit = grouped["gross_profit"].to_numpy()
    units = grouped["units_sold"].to_numpy()

    grouped["gross_margin_pct"] = np.where(rev > 0, np.round((profit / rev) * 100.0, 2), 0.0)
    grouped["avg_selling_price"] = np.where(units > 0, np.round(rev / units, 2), 0.0)

    # Sort descending by revenue
    grouped = grouped.sort_values(by="total_revenue", ascending=False).reset_index(drop=True)
    return grouped


def get_top_selling_medicines(
    enriched_sales_df: pd.DataFrame,
    top_n: int = 10,
    rank_by: str = "revenue",
) -> pd.DataFrame:
    """Rank top-selling medicines by revenue, units sold, or gross profit.

    Calculates percentage contribution to overall pharmacy performance.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.
        top_n: Number of top records to return.
        rank_by: Metric to rank by - 'revenue', 'quantity', or 'profit'.

    Returns:
        Ranked top-selling medicines DataFrame.
    """
    if enriched_sales_df.empty:
        return pd.DataFrame(
            columns=[
                "rank",
                "medicine_id",
                "medicine_name",
                "category",
                "units_sold",
                "total_revenue",
                "gross_profit",
                "gross_margin_pct",
                "revenue_share_pct",
                "volume_share_pct",
            ]
        )

    # Aggregate by medicine_id
    grouped = enriched_sales_df.groupby(["medicine_id", "medicine_name", "category"]).agg(
        units_sold=("quantity_sold", "sum"),
        total_revenue=("total_revenue", "sum"),
        total_cogs=("total_cogs", "sum"),
        gross_profit=("gross_profit", "sum"),
    ).reset_index()

    total_overall_revenue = grouped["total_revenue"].sum()
    total_overall_units = grouped["units_sold"].sum()

    grouped["gross_margin_pct"] = np.where(
        grouped["total_revenue"] > 0,
        np.round((grouped["gross_profit"] / grouped["total_revenue"]) * 100.0, 2),
        0.0,
    )
    grouped["revenue_share_pct"] = np.where(
        total_overall_revenue > 0,
        np.round((grouped["total_revenue"] / total_overall_revenue) * 100.0, 2),
        0.0,
    )
    grouped["volume_share_pct"] = np.where(
        total_overall_units > 0,
        np.round((grouped["units_sold"] / total_overall_units) * 100.0, 2),
        0.0,
    )

    rank_column = "total_revenue"
    if rank_by.lower() in ("quantity", "units", "volume"):
        rank_column = "units_sold"
    elif rank_by.lower() in ("profit", "gross_profit"):
        rank_column = "gross_profit"

    ranked = grouped.sort_values(by=rank_column, ascending=False).head(top_n).reset_index(drop=True)
    ranked["rank"] = np.arange(1, len(ranked) + 1)

    cols = [
        "rank",
        "medicine_id",
        "medicine_name",
        "category",
        "units_sold",
        "total_revenue",
        "gross_profit",
        "gross_margin_pct",
        "revenue_share_pct",
        "volume_share_pct",
    ]
    return ranked[cols]


def get_slow_moving_medicines(
    enriched_sales_df: pd.DataFrame,
    medicines_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    days_window: int = 90,
    sales_threshold_units: int = 25,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Identify slow-moving and stagnant medicines presenting inventory holding risks.

    Operational Definition:
    A medicine is classified as 'Slow-Moving' if its total quantity sold over the
    evaluated evaluation window (e.g. past 90 days) is below `sales_threshold_units`
    (or exactly zero), while holding active stock in inventory.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.
        medicines_df: Complete medicine catalog DataFrame.
        inventory_df: Current batch inventory DataFrame.
        days_window: Evaluation time window in days.
        sales_threshold_units: Upper unit threshold defining slow-moving velocity.
        as_of_date: Evaluation reference date.

    Returns:
        DataFrame detailing slow-moving medicines, stock levels, and velocity status.
    """
    as_of_dt = _parse_date(as_of_date) or pd.to_datetime(REFERENCE_DATE)
    start_window_dt = as_of_dt - pd.Timedelta(days=days_window)

    # 1. Calculate sales in window
    if not enriched_sales_df.empty:
        window_sales = enriched_sales_df[
            (enriched_sales_df["date"] >= start_window_dt) & (enriched_sales_df["date"] <= as_of_dt)
        ]
        sales_agg = window_sales.groupby("medicine_id").agg(
            units_sold_in_window=("quantity_sold", "sum"),
            revenue_in_window=("total_revenue", "sum"),
            last_sale_date=("date", "max"),
        ).reset_index()
    else:
        sales_agg = pd.DataFrame(
            columns=["medicine_id", "units_sold_in_window", "revenue_in_window", "last_sale_date"]
        )

    # 2. Current stock from inventory
    if not inventory_df.empty:
        inv_copy = inventory_df.copy()
        inv_copy["quantity"] = pd.to_numeric(inv_copy["quantity"], errors="coerce").fillna(0)
        inv_copy["purchase_price"] = pd.to_numeric(inv_copy["purchase_price"], errors="coerce").fillna(0.0)
        inv_copy["stock_value"] = inv_copy["quantity"] * inv_copy["purchase_price"]

        inv_agg = inv_copy.groupby("medicine_id").agg(
            current_stock_on_hand=("quantity", "sum"),
            stock_holding_cost=("stock_value", "sum"),
        ).reset_index()
    else:
        inv_agg = pd.DataFrame(columns=["medicine_id", "current_stock_on_hand", "stock_holding_cost"])

    # 3. Merge with medicines master to guarantee complete catalog inclusion
    merged = pd.merge(medicines_df, sales_agg, on="medicine_id", how="left")
    merged = pd.merge(merged, inv_agg, on="medicine_id", how="left")

    merged["units_sold_in_window"] = merged["units_sold_in_window"].fillna(0).astype(int)
    merged["revenue_in_window"] = np.round(merged["revenue_in_window"].fillna(0.0), 2)
    merged["current_stock_on_hand"] = merged["current_stock_on_hand"].fillna(0).astype(int)
    merged["stock_holding_cost"] = np.round(merged["stock_holding_cost"].fillna(0.0), 2)

    # Filter slow-moving records: units_sold <= threshold
    slow_moving = merged[merged["units_sold_in_window"] <= sales_threshold_units].copy()

    # Calculate days since last transaction
    def _calc_days_since_sale(dt_val):
        if pd.isna(dt_val):
            return np.nan
        return int((as_of_dt - pd.to_datetime(dt_val)).days)

    slow_moving["days_since_last_sale"] = slow_moving["last_sale_date"].apply(_calc_days_since_sale)

    # Calculate stock turnover ratio (sales / stock)
    stock = slow_moving["current_stock_on_hand"].to_numpy()
    sold = slow_moving["units_sold_in_window"].to_numpy()
    slow_moving["turnover_ratio"] = np.where(stock > 0, np.round(sold / stock, 3), 0.0)

    # Classify slow-moving severity
    conditions = [
        slow_moving["units_sold_in_window"] == 0,
        slow_moving["units_sold_in_window"] <= (sales_threshold_units * 0.4),
    ]
    choices = ["Stagnant (Zero Sales)", "Critical Slow"]
    slow_moving["velocity_status"] = np.select(conditions, choices, default="Slow-Moving")

    # Sort: Stagnant zero-sales first, then by holding cost descending
    slow_moving = slow_moving.sort_values(
        by=["units_sold_in_window", "stock_holding_cost"],
        ascending=[True, False],
    ).reset_index(drop=True)

    cols = [
        "medicine_id",
        "medicine_name",
        "category",
        "current_stock_on_hand",
        "stock_holding_cost",
        "units_sold_in_window",
        "revenue_in_window",
        "days_since_last_sale",
        "turnover_ratio",
        "velocity_status",
    ]
    return slow_moving[cols]


def calculate_sales_statistics(enriched_sales_df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate key summary statistics and distributions using NumPy and Pandas.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.

    Returns:
        Dictionary of sales statistical metrics.
    """
    if enriched_sales_df.empty:
        return {
            "total_transactions": 0,
            "total_units_sold": 0,
            "total_revenue": 0.0,
            "total_cogs": 0.0,
            "total_gross_profit": 0.0,
            "overall_gross_margin_pct": 0.0,
            "avg_transaction_revenue": 0.0,
            "median_transaction_revenue": 0.0,
            "std_transaction_revenue": 0.0,
            "avg_units_per_sale": 0.0,
            "median_units_per_sale": 0.0,
            "std_units_per_sale": 0.0,
            "avg_selling_price": 0.0,
            "min_unit_price": 0.0,
            "max_unit_price": 0.0,
        }

    rev = enriched_sales_df["total_revenue"].to_numpy()
    qty = enriched_sales_df["quantity_sold"].to_numpy()
    prices = enriched_sales_df["unit_price"].to_numpy()
    cogs = enriched_sales_df["total_cogs"].to_numpy()
    profit = enriched_sales_df["gross_profit"].to_numpy()

    total_rev = float(np.sum(rev))
    total_cost = float(np.sum(cogs))
    total_prof = float(np.sum(profit))
    overall_margin = round((total_prof / total_rev * 100.0), 2) if total_rev > 0 else 0.0

    return {
        "total_transactions": len(enriched_sales_df),
        "total_units_sold": int(np.sum(qty)),
        "total_revenue": round(total_rev, 2),
        "total_cogs": round(total_cost, 2),
        "total_gross_profit": round(total_prof, 2),
        "overall_gross_margin_pct": overall_margin,
        "avg_transaction_revenue": round(float(np.mean(rev)), 2),
        "median_transaction_revenue": round(float(np.median(rev)), 2),
        "std_transaction_revenue": round(float(np.std(rev)), 2),
        "avg_units_per_sale": round(float(np.mean(qty)), 2),
        "median_units_per_sale": round(float(np.median(qty)), 2),
        "std_units_per_sale": round(float(np.std(qty)), 2),
        "avg_selling_price": round(float(np.mean(prices)), 2),
        "min_unit_price": round(float(np.min(prices)), 2),
        "max_unit_price": round(float(np.max(prices)), 2),
    }


def estimate_demand_trends(
    enriched_sales_df: pd.DataFrame,
    forecast_days: int = 30,
) -> Dict[str, Any]:
    """Calculate moving averages, trend direction, and projected baseline demand.

    Discloses the analytical limitations of statistical moving-average projections.

    Args:
        enriched_sales_df: Enriched sales transactions DataFrame.
        forecast_days: Projected horizon in days.

    Returns:
        Dictionary containing historical moving averages, trend slope, and demand estimates.
    """
    if enriched_sales_df.empty:
        return {
            "daily_history": pd.DataFrame(),
            "avg_daily_revenue": 0.0,
            "avg_daily_volume": 0.0,
            "trend_slope": 0.0,
            "trend_direction": "Neutral",
            "projected_period_revenue": 0.0,
            "projected_period_volume": 0.0,
            "disclaimer": DEMAND_ESTIMATE_DISCLAIMER,
        }

    # Aggregate daily time series
    daily = enriched_sales_df.groupby("date").agg(
        daily_units=("quantity_sold", "sum"),
        daily_revenue=("total_revenue", "sum"),
        transactions=("sale_id", "count"),
    ).reset_index().sort_values("date")

    # Compute rolling 7-day and 14-day moving averages
    daily["rolling_7d_units"] = np.round(daily["daily_units"].rolling(window=7, min_periods=1).mean(), 1)
    daily["rolling_7d_revenue"] = np.round(daily["daily_revenue"].rolling(window=7, min_periods=1).mean(), 2)
    daily["rolling_14d_revenue"] = np.round(daily["daily_revenue"].rolling(window=14, min_periods=1).mean(), 2)

    # Linear trend slope calculation with NumPy polyfit
    y_revenue = daily["daily_revenue"].to_numpy()
    x_indices = np.arange(len(y_revenue))

    if len(y_revenue) > 1:
        slope, _ = np.polyfit(x_indices, y_revenue, 1)
        slope = round(float(slope), 2)
    else:
        slope = 0.0

    trend_direction = "Upward" if slope > 0.5 else ("Downward" if slope < -0.5 else "Stable")

    avg_daily_rev = float(np.mean(y_revenue))
    avg_daily_vol = float(np.mean(daily["daily_units"].to_numpy()))

    # Basic projection over forecast_days
    proj_rev = round(avg_daily_rev * forecast_days, 2)
    proj_vol = int(np.round(avg_daily_vol * forecast_days))

    return {
        "daily_history": daily,
        "avg_daily_revenue": round(avg_daily_rev, 2),
        "avg_daily_volume": round(avg_daily_vol, 1),
        "trend_slope": slope,
        "trend_direction": trend_direction,
        "projected_period_revenue": proj_rev,
        "projected_period_volume": proj_vol,
        "forecast_days": forecast_days,
        "disclaimer": DEMAND_ESTIMATE_DISCLAIMER,
    }


def export_analytics_summary(
    df: pd.DataFrame,
    filename: str,
    export_dir: Path = EXPORTS_DIR,
) -> Path:
    """Export analytical summary table to CSV in the reports export directory.

    Args:
        df: DataFrame to export.
        filename: Destination filename.
        export_dir: Directory path for exports.

    Returns:
        Path of the saved file.
    """
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".csv"):
        filename = f"{filename}.csv"

    dest_path = export_dir / filename
    df.to_csv(dest_path, index=False)
    return dest_path
