"""Medicine and batch-level inventory management and analytics service for PharmaTrack.

Provides batch-level inventory summaries, stock valuation, usable stock calculations
(excluding expired stock), configurable low-stock alerts, multi-criteria filtering,
demand-based and rule-based replenishment suggestions, and report exports.
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
    ExpiryThresholds,
    ReplenishmentConfig,
)


def _parse_as_of_date(as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None) -> pd.Timestamp:
    """Normalize input date to pd.Timestamp."""
    if as_of_date is None:
        return pd.to_datetime(REFERENCE_DATE)
    if isinstance(as_of_date, (datetime, pd.Timestamp)):
        return pd.to_datetime(as_of_date).normalize()
    return pd.to_datetime(str(as_of_date).strip())


def get_batch_inventory_summary(
    inventory_df: pd.DataFrame,
    medicines_df: pd.DataFrame,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Generate a batch-level inventory table with valuation and expiry status.

    Preserves individual batch expiry dates, suppliers, and purchase costs.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Medicine catalog DataFrame.
        as_of_date: Reference evaluation date (defaults to config.REFERENCE_DATE).

    Returns:
        Enriched batch inventory DataFrame.
    """
    as_of_dt = _parse_as_of_date(as_of_date)

    inv = inventory_df.copy()
    med = medicines_df.copy()

    # Ensure clean data types
    inv["quantity"] = pd.to_numeric(inv["quantity"], errors="coerce").fillna(0).astype(int)
    inv["purchase_price"] = pd.to_numeric(inv["purchase_price"], errors="coerce").fillna(0.0).astype(float)
    inv["selling_price"] = pd.to_numeric(inv["selling_price"], errors="coerce").fillna(0.0).astype(float)
    inv["expiry_dt"] = pd.to_datetime(inv["expiry_date"], errors="coerce")

    # Merge with medicine metadata
    merged = pd.merge(
        inv,
        med[["medicine_id", "medicine_name", "category", "reorder_level"]],
        on="medicine_id",
        how="left",
    )

    # Vectorized valuation calculations using NumPy
    qty_arr = merged["quantity"].to_numpy()
    purchase_price_arr = merged["purchase_price"].to_numpy()
    selling_price_arr = merged["selling_price"].to_numpy()

    merged["purchase_value"] = np.round(qty_arr * purchase_price_arr, 2)
    merged["potential_selling_value"] = np.round(qty_arr * selling_price_arr, 2)

    # Days to expiry calculation
    days_to_expiry = (merged["expiry_dt"] - as_of_dt).dt.days
    merged["days_to_expiry"] = days_to_expiry

    # Expiry and usability flags
    # Expired if expiry_dt < as_of_dt (strictly before reference date)
    is_expired = merged["expiry_dt"] < as_of_dt
    merged["is_expired"] = is_expired
    # Usable stock: quantity > 0 and NOT expired
    merged["is_usable"] = (merged["quantity"] > 0) & (~is_expired)

    # Expiry category classification
    conditions = [
        merged["is_expired"],
        merged["days_to_expiry"] <= ExpiryThresholds.CRITICAL_DAYS,
        merged["days_to_expiry"] <= ExpiryThresholds.NEAR_EXPIRY_DAYS,
        merged["days_to_expiry"] <= ExpiryThresholds.MONITORING_DAYS,
    ]
    choices = ["Expired", "Critical (≤30d)", "Near Expiry (≤90d)", "Monitoring (≤180d)"]
    merged["expiry_status"] = np.select(conditions, choices, default="Healthy")

    return merged


def get_medicine_inventory_summary(
    inventory_df: pd.DataFrame,
    medicines_df: pd.DataFrame,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Aggregate batch-level stock into a comprehensive medicine catalogue summary.

    Computes total stock, usable stock (strictly excluding expired stock),
    expired stock, purchase valuation, and low-stock alerts.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Medicine catalog DataFrame.
        as_of_date: Reference evaluation date.

    Returns:
        Catalogue-level inventory summary DataFrame.
    """
    batches_enriched = get_batch_inventory_summary(
        inventory_df=inventory_df,
        medicines_df=medicines_df,
        as_of_date=as_of_date,
    )

    # Calculate usable quantity per batch
    batches_enriched["usable_quantity"] = np.where(
        batches_enriched["is_usable"], batches_enriched["quantity"], 0
    )
    batches_enriched["expired_quantity"] = np.where(
        batches_enriched["is_expired"], batches_enriched["quantity"], 0
    )
    batches_enriched["usable_purchase_value"] = np.where(
        batches_enriched["is_usable"], batches_enriched["purchase_value"], 0.0
    )
    batches_enriched["expired_purchase_value"] = np.where(
        batches_enriched["is_expired"], batches_enriched["purchase_value"], 0.0
    )

    # Aggregate by medicine_id
    agg_funcs = {
        "batch_id": "count",
        "quantity": "sum",
        "usable_quantity": "sum",
        "expired_quantity": "sum",
        "purchase_value": "sum",
        "usable_purchase_value": "sum",
        "expired_purchase_value": "sum",
    }
    grouped = batches_enriched.groupby("medicine_id").agg(agg_funcs).reset_index()
    grouped.rename(
        columns={
            "batch_id": "batch_count",
            "quantity": "total_physical_stock",
            "purchase_value": "total_purchase_value",
        },
        inplace=True,
    )

    # Merge with full medicine catalog so medicines with ZERO batches are preserved
    med = medicines_df.copy()
    med["reorder_level"] = pd.to_numeric(med["reorder_level"], errors="coerce").fillna(0).astype(int)

    summary = pd.merge(med, grouped, on="medicine_id", how="left")

    # Fill NaNs for medicines without batches in inventory
    summary["batch_count"] = summary["batch_count"].fillna(0).astype(int)
    summary["total_physical_stock"] = summary["total_physical_stock"].fillna(0).astype(int)
    summary["usable_quantity"] = summary["usable_quantity"].fillna(0).astype(int)
    summary["expired_quantity"] = summary["expired_quantity"].fillna(0).astype(int)
    summary["total_purchase_value"] = np.round(summary["total_purchase_value"].fillna(0.0), 2)
    summary["usable_purchase_value"] = np.round(summary["usable_purchase_value"].fillna(0.0), 2)
    summary["expired_purchase_value"] = np.round(summary["expired_purchase_value"].fillna(0.0), 2)

    # Stock status flags based strictly on USABLE quantity
    summary["is_out_of_stock"] = summary["usable_quantity"] == 0
    summary["is_low_stock"] = (summary["usable_quantity"] > 0) & (
        summary["usable_quantity"] <= summary["reorder_level"]
    )
    summary["stock_deficit"] = np.maximum(0, summary["reorder_level"] - summary["usable_quantity"])

    # Categorical stock health status
    status_conditions = [
        summary["is_out_of_stock"],
        summary["usable_quantity"] <= (summary["reorder_level"] * 0.5),
        summary["is_low_stock"],
    ]
    status_choices = ["Out of Stock", "Critical Low", "Low Stock"]
    summary["stock_status"] = np.select(status_conditions, status_choices, default="Healthy")

    return summary


def get_low_stock_alerts(
    medicine_summary_df: pd.DataFrame,
    threshold_factor: float = 1.0,
) -> pd.DataFrame:
    """Filter medicines that require replenishment based on usable stock and reorder levels.

    Args:
        medicine_summary_df: Medicine-level summary DataFrame.
        threshold_factor: Multiplier applied to reorder_level (e.g., 1.0 for standard, 1.2 for early buffer).

    Returns:
        Filtered DataFrame sorted by stock urgency (out of stock first, then highest deficit).
    """
    df = medicine_summary_df.copy()
    threshold = df["reorder_level"] * threshold_factor
    low_stock_mask = df["usable_quantity"] <= threshold

    alerts = df[low_stock_mask].copy()
    # Sort: Out of stock first, then by deficit descending
    alerts = alerts.sort_values(
        by=["is_out_of_stock", "stock_deficit", "usable_quantity"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    return alerts


def filter_inventory(
    df: pd.DataFrame,
    medicine_id: Optional[str] = None,
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    exclude_expired: bool = False,
) -> pd.DataFrame:
    """Multi-criteria filtering for batch or medicine inventory dataframes.

    Args:
        df: Enriched batch inventory or medicine inventory DataFrame.
        medicine_id: Specific medicine identifier to match.
        category: Therapeutic category to filter by.
        supplier: Supplier name to filter by (for batch tables).
        exclude_expired: If True, excludes expired stock from the view.

    Returns:
        Filtered DataFrame.
    """
    filtered = df.copy()

    if medicine_id:
        filtered = filtered[filtered["medicine_id"] == medicine_id.strip()]

    if category:
        filtered = filtered[filtered["category"].str.lower() == category.strip().lower()]

    if supplier and "supplier" in filtered.columns:
        filtered = filtered[filtered["supplier"].str.lower() == supplier.strip().lower()]

    if exclude_expired and "is_expired" in filtered.columns:
        filtered = filtered[~filtered["is_expired"]]

    return filtered.reset_index(drop=True)


def calculate_replenishment_suggestions(
    medicine_summary_df: pd.DataFrame,
    sales_df: Optional[pd.DataFrame] = None,
    lead_time_days: int = ReplenishmentConfig.DEFAULT_LEAD_TIME_DAYS,
    safety_factor: float = ReplenishmentConfig.SAFETY_STOCK_FACTOR,
    review_period_days: int = ReplenishmentConfig.DEFAULT_REVIEW_PERIOD_DAYS,
) -> pd.DataFrame:
    """Generate rule-based and demand-driven replenishment suggestions.

    Important: Suggestions are analytical estimates, not automated purchase orders.
    Safely handles medicines with no sales history using a fallback reorder rule.

    Args:
        medicine_summary_df: Medicine-level summary DataFrame.
        sales_df: Optional historical sales transactions DataFrame.
        lead_time_days: Supplier delivery lead time in days.
        safety_factor: Safety stock multiplier.
        review_period_days: Historical sales window in days to evaluate velocity.

    Returns:
        DataFrame with estimated reorder quantities and runout days.
    """
    df = medicine_summary_df.copy()

    # Step 1: Calculate historical demand velocity if sales_df is provided and non-empty
    demand_metrics: Dict[str, Dict[str, float]] = {}

    if sales_df is not None and not sales_df.empty and "quantity_sold" in sales_df.columns:
        sal = sales_df.copy()
        # Ensure quantity is numeric
        sal["quantity_sold"] = pd.to_numeric(sal["quantity_sold"], errors="coerce").fillna(0)

        # If sales_df has medicine_id or batch_id
        if "medicine_id" in sal.columns:
            grouped_sales = sal.groupby("medicine_id")["quantity_sold"].sum().to_dict()
            for med_id, total_sold in grouped_sales.items():
                daily_velocity = float(total_sold) / max(1, review_period_days)
                demand_metrics[med_id] = {
                    "total_sales_units": float(total_sold),
                    "avg_daily_demand": daily_velocity,
                }

    # Step 2: Compute suggestions per medicine
    records = []
    for _, row in df.iterrows():
        med_id = row["medicine_id"]
        usable_stock = int(row["usable_quantity"])
        reorder_level = int(row["reorder_level"])

        if med_id in demand_metrics and demand_metrics[med_id]["avg_daily_demand"] > 0:
            # Demand-driven method
            daily_demand = demand_metrics[med_id]["avg_daily_demand"]
            lead_time_demand = daily_demand * lead_time_days
            safety_stock = lead_time_demand * safety_factor
            target_stock = lead_time_demand + safety_stock

            runout_days = round(usable_stock / daily_demand, 1)

            if usable_stock <= reorder_level or usable_stock <= target_stock:
                suggested_reorder = int(np.ceil(max(0, target_stock - usable_stock)))
            else:
                suggested_reorder = 0

            method = "demand_based"
            demand_val = round(daily_demand, 2)
        else:
            # Simple rule-based fallback when historical demand is unavailable
            daily_demand = 0.0
            demand_val = 0.0
            runout_days = np.nan

            if usable_stock <= reorder_level:
                # Rule fallback: replenish up to 2.5x the safety reorder level
                target_stock = reorder_level * 2.5
                suggested_reorder = int(np.ceil(max(0, target_stock - usable_stock)))
            else:
                suggested_reorder = 0

            method = "rule_fallback"

        reorder_urgency = "High" if row["is_out_of_stock"] else ("Medium" if row["is_low_stock"] else "Low")

        records.append({
            "medicine_id": med_id,
            "medicine_name": row["medicine_name"],
            "category": row["category"],
            "reorder_level": reorder_level,
            "usable_stock": usable_stock,
            "expired_stock": row["expired_quantity"],
            "avg_daily_demand": demand_val,
            "estimated_runout_days": runout_days,
            "suggested_reorder_qty": suggested_reorder,
            "calculation_method": method,
            "reorder_urgency": reorder_urgency,
            "recommendation_notice": "Analytical estimate — verify before placing purchase orders",
        })

    return pd.DataFrame(records)


def calculate_inventory_valuation_metrics(
    inventory_df: pd.DataFrame,
    medicines_df: Optional[pd.DataFrame] = None,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> Dict[str, Any]:
    """Calculate aggregate inventory metrics and valuations using NumPy and Pandas.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Optional medicine catalog DataFrame.
        as_of_date: Reference evaluation date.

    Returns:
        Dictionary of high-level inventory KPIs.
    """
    as_of_dt = _parse_as_of_date(as_of_date)

    inv = inventory_df.copy()
    qty = pd.to_numeric(inv["quantity"], errors="coerce").fillna(0).to_numpy()
    purchase = pd.to_numeric(inv["purchase_price"], errors="coerce").fillna(0.0).to_numpy()
    selling = pd.to_numeric(inv["selling_price"], errors="coerce").fillna(0.0).to_numpy()
    expiry_dt = pd.to_datetime(inv["expiry_date"], errors="coerce")

    # Expiry mask
    is_expired = (expiry_dt < as_of_dt).to_numpy()
    is_usable = (~is_expired) & (qty > 0)

    # Vectorized valuation
    total_val_arr = qty * purchase
    usable_val_arr = np.where(is_usable, total_val_arr, 0.0)
    expired_val_arr = np.where(is_expired, total_val_arr, 0.0)
    potential_revenue_arr = np.where(is_usable, qty * selling, 0.0)

    total_physical_units = int(np.sum(qty))
    usable_units = int(np.sum(np.where(is_usable, qty, 0)))
    expired_units = int(np.sum(np.where(is_expired, qty, 0)))

    total_valuation = float(np.sum(total_val_arr))
    usable_valuation = float(np.sum(usable_val_arr))
    expired_valuation = float(np.sum(expired_val_arr))
    potential_revenue = float(np.sum(potential_revenue_arr))

    unique_medicines = len(inv["medicine_id"].unique()) if "medicine_id" in inv.columns else 0
    total_batches = len(inv)

    return {
        "as_of_date": as_of_dt.strftime(DATE_FORMAT),
        "total_unique_medicines": int(unique_medicines),
        "total_batches_tracked": int(total_batches),
        "total_physical_stock_units": total_physical_units,
        "usable_stock_units": usable_units,
        "expired_stock_units": expired_units,
        "total_purchase_valuation": round(total_valuation, 2),
        "usable_purchase_valuation": round(usable_valuation, 2),
        "expired_stock_loss_exposure": round(expired_valuation, 2),
        "potential_usable_revenue": round(potential_revenue, 2),
    }


def export_inventory_report(
    df: pd.DataFrame,
    filename: str,
    export_dir: Path = EXPORTS_DIR,
) -> Path:
    """Export an inventory dataframe to CSV in the reports export directory.

    Args:
        df: DataFrame to export.
        filename: Destination filename (e.g., 'low_stock_alerts.csv').
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
