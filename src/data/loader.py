"""Data ingestion, cleaning, normalization, and relational merging for PharmaTrack."""

from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd

from config import (
    DATE_FORMAT,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    SCHEMA_INVENTORY,
    SCHEMA_MEDICINES,
    SCHEMA_SALES,
)
from src.data.validator import ValidationReport, validate_all_datasets


def load_raw_csv_files(data_dir: Path = RAW_DATA_DIR) -> Dict[str, pd.DataFrame]:
    """Load raw CSV files into Pandas DataFrames.

    Args:
        data_dir: Directory containing medicines.csv, inventory.csv, and sales.csv.

    Returns:
        Dictionary of raw DataFrames.

    Raises:
        FileNotFoundError: If any of the required CSV files are missing.
    """
    data_dir = Path(data_dir)
    files = {
        "medicines": data_dir / "medicines.csv",
        "inventory": data_dir / "inventory.csv",
        "sales": data_dir / "sales.csv",
    }

    loaded: Dict[str, pd.DataFrame] = {}
    for name, path in files.items():
        if not path.exists():
            raise FileNotFoundError(f"Required dataset '{name}.csv' not found at {path}")
        loaded[name] = pd.read_csv(path, dtype=str)

    return loaded


def clean_and_type_coerce(
    medicines_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    sales_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Strip whitespace and enforce proper data types across all datasets safely.

    Args:
        medicines_df: Raw medicines DataFrame.
        inventory_df: Raw inventory DataFrame.
        sales_df: Raw sales DataFrame.

    Returns:
        Tuple of cleaned (medicines_df, inventory_df, sales_df).
    """
    med = medicines_df.copy()
    inv = inventory_df.copy()
    sal = sales_df.copy()

    # Clean object & string columns
    for df in (med, inv, sal):
        for col in df.select_dtypes(include=["object", "string"]).columns:
            df[col] = df[col].astype(str).str.strip()

    # medicines types
    if "reorder_level" in med.columns:
        med["reorder_level"] = pd.to_numeric(med["reorder_level"], errors="coerce").fillna(0).astype(int)

    # inventory types
    if "quantity" in inv.columns:
        inv["quantity"] = pd.to_numeric(inv["quantity"], errors="coerce").fillna(0).astype(int)
    if "purchase_price" in inv.columns:
        inv["purchase_price"] = pd.to_numeric(inv["purchase_price"], errors="coerce").fillna(0.0).astype(float)
    if "selling_price" in inv.columns:
        inv["selling_price"] = pd.to_numeric(inv["selling_price"], errors="coerce").fillna(0.0).astype(float)
    if "expiry_date" in inv.columns:
        inv["expiry_date"] = pd.to_datetime(inv["expiry_date"], format=DATE_FORMAT, errors="coerce")

    # sales types
    if "quantity_sold" in sal.columns:
        sal["quantity_sold"] = pd.to_numeric(sal["quantity_sold"], errors="coerce").fillna(0).astype(int)
    if "unit_price" in sal.columns:
        sal["unit_price"] = pd.to_numeric(sal["unit_price"], errors="coerce").fillna(0.0).astype(float)
    if "date" in sal.columns:
        sal["date"] = pd.to_datetime(sal["date"], format=DATE_FORMAT, errors="coerce")

    return med, inv, sal


def ingest_and_validate_data(
    data_dir: Path = RAW_DATA_DIR,
    export_processed: bool = True,
) -> Tuple[Dict[str, pd.DataFrame], ValidationReport]:
    """Load, validate, type-coerce, and optionally export clean datasets to processed/.

    Args:
        data_dir: Directory containing input CSV files.
        export_processed: If True, writes validated datasets to data/processed/.

    Returns:
        Tuple of (dict_of_cleaned_dfs, validation_report).
    """
    raw_dfs = load_raw_csv_files(data_dir=data_dir)

    # Perform formal schema & relational validation
    is_valid, report = validate_all_datasets(
        medicines_df=raw_dfs["medicines"].copy(),
        inventory_df=raw_dfs["inventory"].copy(),
        sales_df=raw_dfs["sales"].copy(),
    )

    # Type-coerce and clean
    clean_med, clean_inv, clean_sal = clean_and_type_coerce(
        medicines_df=raw_dfs["medicines"],
        inventory_df=raw_dfs["inventory"],
        sales_df=raw_dfs["sales"],
    )

    cleaned_dict = {
        "medicines": clean_med,
        "inventory": clean_inv,
        "sales": clean_sal,
    }

    if is_valid and export_processed:
        PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Format dates back to string for standard CSV storage
        inv_export = clean_inv.copy()
        if "expiry_date" in inv_export.columns and pd.api.types.is_datetime64_any_dtype(inv_export["expiry_date"]):
            inv_export["expiry_date"] = inv_export["expiry_date"].dt.strftime(DATE_FORMAT)
        sal_export = clean_sal.copy()
        if "date" in sal_export.columns and pd.api.types.is_datetime64_any_dtype(sal_export["date"]):
            sal_export["date"] = sal_export["date"].dt.strftime(DATE_FORMAT)

        clean_med.to_csv(PROCESSED_DATA_DIR / "medicines.csv", index=False)
        inv_export.to_csv(PROCESSED_DATA_DIR / "inventory.csv", index=False)
        sal_export.to_csv(PROCESSED_DATA_DIR / "sales.csv", index=False)

    return cleaned_dict, report


def get_unified_sales_data(
    medicines_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    sales_df: pd.DataFrame,
) -> pd.DataFrame:
    """Merge sales transactions with batch inventory and medicine metadata.

    Calculates transaction-level total revenue, batch COGS, and gross margin.

    Returns:
        Unified analytical DataFrame.
    """
    # 1. Join sales with batch inventory
    sales_batch = pd.merge(
        sales_df,
        inventory_df[["batch_id", "medicine_id", "purchase_price", "expiry_date", "supplier"]],
        on="batch_id",
        how="inner",
    )

    # 2. Join with medicine catalog
    unified = pd.merge(
        sales_batch,
        medicines_df[["medicine_id", "medicine_name", "category", "reorder_level"]],
        on="medicine_id",
        how="inner",
    )

    # 3. Compute financial transaction metrics
    unified["total_revenue"] = unified["quantity_sold"] * unified["unit_price"]
    unified["total_cogs"] = unified["quantity_sold"] * unified["purchase_price"]
    unified["total_cost"] = unified["total_cogs"]
    unified["gross_margin"] = unified["total_revenue"] - unified["total_cogs"]
    unified["gross_profit"] = unified["gross_margin"]
    unified["margin_pct"] = (
        (unified["gross_margin"] / unified["total_revenue"]) * 100.0
    ).fillna(0.0)

    # 4. Standardize output schema
    ordered_cols = [
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
        "total_cost",
        "gross_margin",
        "gross_profit",
        "margin_pct",
        "expiry_date",
        "reorder_level",
    ]
    return unified[ordered_cols]
