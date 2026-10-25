"""Expiry and wastage risk analysis service for PharmaTrack.

Provides batch-level expiry classification, days-to-expiry tracking, configurable
warning thresholds, potential value-at-risk exposure computations, FEFO (First-Expiry-First-Out)
dispensing recommendations, recorded wastage analysis, and report exports.
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
)

# Standard analytical disclosure regarding value-at-risk vs actual financial loss
EXPOSURE_RISK_DISCLOSURE: str = (
    "Estimated value-at-risk represents the acquisition purchase value of remaining "
    "near-expiry inventory at risk of expiring if not dispensed prior to the batch expiry date. "
    "This is an operational risk exposure estimate, not an actual realized financial loss. "
    "Actual loss occurs only upon physical expiry and verified disposal."
)


def _parse_reference_date(dt: Optional[Union[str, datetime, pd.Timestamp]]) -> pd.Timestamp:
    """Normalize input date to pd.Timestamp."""
    if dt is None:
        return pd.to_datetime(REFERENCE_DATE)
    if isinstance(dt, (datetime, pd.Timestamp)):
        return pd.to_datetime(dt).normalize()
    return pd.to_datetime(str(dt).strip())


def classify_batch_expiry(
    inventory_df: pd.DataFrame,
    medicines_df: Optional[pd.DataFrame] = None,
    near_expiry_days: int = ExpiryThresholds.CRITICAL_DAYS,
    high_value_threshold: float = 300.0,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Classify all inventory batches against an evaluation reference date.

    Invariant Rules:
    1. An expired batch (days_remaining < 0) is NEVER classified as Near Expiry.
    2. A batch expiring today (days_remaining == 0) is classified consistently as 'Expiring Today'.
    3. Near-expiry batches satisfy: 0 <= days_remaining <= near_expiry_days.
    4. Safe batches have days_remaining > near_expiry_days.
    5. Value-at-risk = remaining_quantity * purchase_price.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Optional medicine catalog DataFrame to attach names and categories.
        near_expiry_days: Configurable threshold in days (default 30 days).
        high_value_threshold: Dollar threshold for flagging high-value exposure.
        as_of_date: Reference evaluation date (defaults to config.REFERENCE_DATE).

    Returns:
        DataFrame with batch-level expiry metrics, classification, and value-at-risk.
    """
    as_of_dt = _parse_reference_date(as_of_date)

    if inventory_df.empty:
        return pd.DataFrame(
            columns=[
                "batch_id",
                "medicine_id",
                "medicine_name",
                "category",
                "supplier",
                "quantity",
                "purchase_price",
                "selling_price",
                "expiry_date",
                "days_remaining",
                "expiry_classification",
                "value_at_risk",
                "potential_selling_value",
                "is_expired",
                "is_near_expiry",
                "is_high_value_risk",
            ]
        )

    df = inventory_df.copy()

    # Clean data types
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["purchase_price"] = pd.to_numeric(df["purchase_price"], errors="coerce").fillna(0.0).astype(float)
    df["selling_price"] = pd.to_numeric(df["selling_price"], errors="coerce").fillna(0.0).astype(float)
    df["expiry_dt"] = pd.to_datetime(df["expiry_date"], errors="coerce")

    # Merge medicine details if available
    if medicines_df is not None and not medicines_df.empty and "medicine_id" in medicines_df.columns:
        med_cols = [c for c in ["medicine_id", "medicine_name", "category"] if c in medicines_df.columns]
        df = pd.merge(df, medicines_df[med_cols], on="medicine_id", how="left")
    else:
        if "medicine_name" not in df.columns:
            df["medicine_name"] = df["medicine_id"]
        if "category" not in df.columns:
            df["category"] = "General"

    # Calculate days remaining until expiry
    df["days_remaining"] = (df["expiry_dt"] - as_of_dt).dt.days

    # Vectorized valuation
    qty = df["quantity"].to_numpy()
    purchase_p = df["purchase_price"].to_numpy()
    selling_p = df["selling_price"].to_numpy()

    # Value at risk represents purchase cost of the remaining stock
    val_at_risk = np.round(qty * purchase_p, 2)
    potential_selling_val = np.round(qty * selling_p, 2)

    df["value_at_risk"] = val_at_risk
    df["potential_selling_value"] = potential_selling_val

    # Strict invariant classification
    days = df["days_remaining"].to_numpy()

    is_expired = days < 0
    is_today = days == 0
    is_near = (days >= 0) & (days <= near_expiry_days)
    is_safe = days > near_expiry_days

    df["is_expired"] = is_expired
    # An expired batch must NEVER be classified as near expiry
    df["is_near_expiry"] = is_near & (~is_expired)

    # Human-readable classification label
    conditions = [
        is_expired,
        is_today,
        is_near,
        is_safe,
    ]
    choices = [
        "Expired",
        "Expiring Today",
        f"Near Expiry (≤{near_expiry_days}d)",
        "Safe / Healthy",
    ]
    df["expiry_classification"] = np.select(conditions, choices, default="Unknown")

    # High-value risk: remaining quantity > 0, expiring soon or today, and value >= threshold
    df["is_high_value_risk"] = (
        (df["quantity"] > 0)
        & (df["is_near_expiry"] | is_today)
        & (df["value_at_risk"] >= high_value_threshold)
    )

    # Usable stock flag
    df["is_usable"] = (df["quantity"] > 0) & (~is_expired)

    # Format expiry_date as string
    df["expiry_date"] = df["expiry_dt"].dt.strftime(DATE_FORMAT)
    df.drop(columns=["expiry_dt"], inplace=True)

    # Order by urgency: Expiring today, near expiry, expired, safe
    sort_order = np.select(
        [is_today, is_near, is_expired, is_safe],
        [1, 2, 3, 4],
        default=5,
    )
    df["_sort_key"] = sort_order
    df = df.sort_values(by=["_sort_key", "days_remaining", "value_at_risk"], ascending=[True, True, False])
    df.drop(columns=["_sort_key"], inplace=True)

    return df.reset_index(drop=True)


def calculate_expiry_exposure_metrics(
    inventory_df: pd.DataFrame,
    near_expiry_days: int = ExpiryThresholds.CRITICAL_DAYS,
    high_value_threshold: float = 300.0,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> Dict[str, Any]:
    """Calculate aggregate inventory expiry risk metrics and financial exposure.

    Args:
        inventory_df: Batch inventory DataFrame.
        near_expiry_days: Warning threshold in days.
        high_value_threshold: Dollar threshold for high-value batches.
        as_of_date: Reference evaluation date.

    Returns:
        Dictionary of summary risk metrics and value-at-risk exposure.
    """
    as_of_dt = _parse_reference_date(as_of_date)
    classified = classify_batch_expiry(
        inventory_df=inventory_df,
        near_expiry_days=near_expiry_days,
        high_value_threshold=high_value_threshold,
        as_of_date=as_of_dt,
    )

    if classified.empty:
        return {
            "as_of_date": as_of_dt.strftime(DATE_FORMAT),
            "near_expiry_threshold_days": near_expiry_days,
            "total_batches_evaluated": 0,
            "expired_batches_count": 0,
            "near_expiry_batches_count": 0,
            "safe_batches_count": 0,
            "expired_stock_units": 0,
            "near_expiry_stock_units": 0,
            "expired_stock_holding_cost": 0.0,
            "near_expiry_purchase_value_at_risk": 0.0,
            "near_expiry_potential_revenue_at_risk": 0.0,
            "high_value_near_expiry_batches_count": 0,
            "disclosure": EXPOSURE_RISK_DISCLOSURE,
        }

    expired_df = classified[classified["is_expired"]]
    near_df = classified[classified["is_near_expiry"]]
    safe_df = classified[~classified["is_expired"] & ~classified["is_near_expiry"]]
    high_val_df = classified[classified["is_high_value_risk"]]

    expired_cost = float(np.sum(expired_df["value_at_risk"].to_numpy()))
    near_risk_cost = float(np.sum(near_df["value_at_risk"].to_numpy()))
    near_risk_rev = float(np.sum(near_df["potential_selling_value"].to_numpy()))

    return {
        "as_of_date": as_of_dt.strftime(DATE_FORMAT),
        "near_expiry_threshold_days": near_expiry_days,
        "total_batches_evaluated": len(classified),
        "expired_batches_count": len(expired_df),
        "near_expiry_batches_count": len(near_df),
        "safe_batches_count": len(safe_df),
        "expired_stock_units": int(expired_df["quantity"].sum()),
        "near_expiry_stock_units": int(near_df["quantity"].sum()),
        "expired_stock_holding_cost": round(expired_cost, 2),
        "near_expiry_purchase_value_at_risk": round(near_risk_cost, 2),
        "near_expiry_potential_revenue_at_risk": round(near_risk_rev, 2),
        "high_value_near_expiry_batches_count": len(high_val_df),
        "disclosure": EXPOSURE_RISK_DISCLOSURE,
    }


def get_high_value_near_expiry_batches(
    inventory_df: pd.DataFrame,
    medicines_df: Optional[pd.DataFrame] = None,
    near_expiry_days: int = ExpiryThresholds.CRITICAL_DAYS,
    min_value_threshold: float = 300.0,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Filter high-value batches that are approaching expiry.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Optional medicine catalog DataFrame.
        near_expiry_days: Warning threshold in days.
        min_value_threshold: Minimum value-at-risk to include in priority list.
        as_of_date: Reference evaluation date.

    Returns:
        Filtered DataFrame sorted descending by financial exposure.
    """
    classified = classify_batch_expiry(
        inventory_df=inventory_df,
        medicines_df=medicines_df,
        near_expiry_days=near_expiry_days,
        high_value_threshold=min_value_threshold,
        as_of_date=as_of_date,
    )

    high_value = classified[
        classified["is_near_expiry"] & (classified["value_at_risk"] >= min_value_threshold)
    ].copy()

    return high_value.sort_values(by="value_at_risk", ascending=False).reset_index(drop=True)


def get_fefo_stock_rotation_queue(
    inventory_df: pd.DataFrame,
    medicines_df: Optional[pd.DataFrame] = None,
    as_of_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
) -> pd.DataFrame:
    """Generate FEFO (First-Expiry-First-Out) dispensing sequence recommendations.

    Important:
    - Expired stock is strictly excluded from dispensing priorities and quarantined.
    - Active batches are ordered per medicine by earliest expiry date first.
    - Zero stock batches are flagged as depleted.

    Args:
        inventory_df: Batch inventory DataFrame.
        medicines_df: Optional medicine catalog DataFrame.
        as_of_date: Reference evaluation date.

    Returns:
        DataFrame with FEFO priority rankings and clinical dispensing recommendations.
    """
    classified = classify_batch_expiry(
        inventory_df=inventory_df,
        medicines_df=medicines_df,
        as_of_date=as_of_date,
    )

    if classified.empty:
        return pd.DataFrame()

    df = classified.copy()

    # Separate saleable batches from expired batches
    saleable = df[df["is_usable"]].copy()
    expired = df[df["is_expired"] & (df["quantity"] > 0)].copy()

    # Sort saleable batches: medicine_id, then expiry_date ascending, then batch_id
    saleable = saleable.sort_values(
        by=["medicine_id", "days_remaining", "batch_id"],
        ascending=[True, True, True],
    ).reset_index(drop=True)

    # Assign FEFO dispense priority (1 = dispense first, 2 = dispense next)
    saleable["fefo_dispense_priority"] = saleable.groupby("medicine_id").cumcount() + 1

    # Formulate actionable FEFO guidance
    def _fefo_action(row):
        days = row["days_remaining"]
        priority = row["fefo_dispense_priority"]
        if days == 0:
            return "Urgent: Dispense immediately today or return to supplier"
        elif days <= 30:
            return f"Priority #{priority}: Dispense first; consider promotional clearance"
        elif days <= 90:
            return f"Priority #{priority}: Rotate to front shelf"
        return f"Priority #{priority}: Standard FEFO rotation"

    saleable["fefo_recommendation"] = saleable.apply(_fefo_action, axis=1)

    # Process expired batches with quarantine notice
    if not expired.empty:
        expired["fefo_dispense_priority"] = -1
        expired["fefo_recommendation"] = "DO NOT DISPENSE - Quarantine for safe disposal or supplier return"

    combined = pd.concat([saleable, expired], ignore_index=True)
    return combined.sort_values(
        by=["medicine_id", "fefo_dispense_priority"],
        ascending=[True, True],
    ).reset_index(drop=True)


def analyze_recorded_wastage(
    wastage_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Analyze actual historical recorded wastage transactions if present in dataset.

    Important: Does not claim wastage occurred unless the dataset contains
    a verified recorded wastage record.

    Args:
        wastage_df: Optional recorded wastage transactions DataFrame.

    Returns:
        Dictionary containing verified wastage metrics or explicit absence disclosure.
    """
    if wastage_df is None or wastage_df.empty:
        return {
            "has_recorded_wastage": False,
            "message": "No recorded wastage transactions present in dataset. Realized wastage is not claimed without explicit transaction records.",
            "total_units_wasted": 0,
            "total_wastage_loss": 0.0,
            "wastage_records_count": 0,
            "wastage_by_reason": pd.DataFrame(),
        }

    df = wastage_df.copy()
    qty_col = "quantity_wasted" if "quantity_wasted" in df.columns else "quantity"
    cost_col = "cost_per_unit" if "cost_per_unit" in df.columns else "purchase_price"

    df["units"] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0).astype(int)
    df["unit_cost"] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0.0).astype(float)
    df["total_loss"] = np.round(df["units"] * df["unit_cost"], 2)

    total_units = int(df["units"].sum())
    total_loss = float(np.sum(df["total_loss"].to_numpy()))

    reason_col = "reason" if "reason" in df.columns else "waste_reason"
    if reason_col in df.columns:
        by_reason = df.groupby(reason_col).agg(
            wasted_units=("units", "sum"),
            financial_loss=("total_loss", "sum"),
            incident_count=("units", "count"),
        ).reset_index().sort_values(by="financial_loss", ascending=False)
    else:
        by_reason = pd.DataFrame()

    return {
        "has_recorded_wastage": True,
        "message": f"Verified {len(df)} historical wastage transaction(s).",
        "total_units_wasted": total_units,
        "total_wastage_loss": round(total_loss, 2),
        "wastage_records_count": len(df),
        "wastage_by_reason": by_reason,
    }


def export_expiry_report(
    df: pd.DataFrame,
    filename: str,
    export_dir: Path = EXPORTS_DIR,
) -> Path:
    """Export expiry risk or FEFO rotation report to CSV in reports export directory.

    Args:
        df: DataFrame to export.
        filename: Destination filename.
        export_dir: Target directory path.

    Returns:
        Path to the saved CSV file.
    """
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".csv"):
        filename = f"{filename}.csv"

    dest_path = export_dir / filename
    df.to_csv(dest_path, index=False)
    return dest_path
