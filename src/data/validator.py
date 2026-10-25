"""Data validation, anomaly detection, and schema verification module for PharmaTrack."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from config import (
    DATE_FORMAT,
    SCHEMA_INVENTORY,
    SCHEMA_MEDICINES,
    SCHEMA_SALES,
)


@dataclass
class ValidationReport:
    """Detailed report tracking validation outcomes, detected anomalies, and data health."""

    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    invalid_records: Dict[str, pd.DataFrame] = field(default_factory=dict)
    summary_stats: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, message: str) -> None:
        """Register an integrity error."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Register a validation warning."""
        self.warnings.append(message)

    def record_invalid_rows(self, dataset_name: str, rows: pd.DataFrame, reason: str) -> None:
        """Record anomalous rows with an explanatory tag without silently dropping them."""
        if rows.empty:
            return
        annotated = rows.copy()
        annotated["validation_issue"] = reason
        if dataset_name in self.invalid_records:
            self.invalid_records[dataset_name] = pd.concat(
                [self.invalid_records[dataset_name], annotated], ignore_index=True
            )
        else:
            self.invalid_records[dataset_name] = annotated

    def to_markdown(self) -> str:
        """Generate a formatted markdown summary of the validation report."""
        status_label = "[PASSED]" if self.is_valid else "[FAILED]"
        lines = [
            f"### Validation Report: {status_label}",
            f"- **Errors ({len(self.errors)}):**",
        ]
        if self.errors:
            for err in self.errors:
                lines.append(f"  - [ERROR] {err}")
        else:
            lines.append("  - None")

        lines.append(f"- **Warnings ({len(self.warnings)}):**")
        if self.warnings:
            for warn in self.warnings:
                lines.append(f"  - [WARNING] {warn}")
        else:
            lines.append("  - None")

        if self.summary_stats:
            lines.append("- **Summary Statistics:**")
            for k, v in self.summary_stats.items():
                lines.append(f"  - **{k}:** {v}")

        if self.invalid_records:
            lines.append("- **Recorded Anomalous Records:**")
            for name, df in self.invalid_records.items():
                lines.append(f"  - **{name}:** {len(df)} flagged record(s)")

        return "\n".join(lines)


class DataValidator:
    """Validates pharmacy datasets against structural, relational, and business rules."""

    def __init__(self):
        self.report = ValidationReport()

    def validate_schema(self, df: pd.DataFrame, expected_columns: List[str], dataset_name: str) -> bool:
        """Verify that all mandatory columns are present in the dataset."""
        missing_cols = [col for col in expected_columns if col not in df.columns]
        if missing_cols:
            self.report.add_error(f"[{dataset_name}] Missing required columns: {', '.join(missing_cols)}")
            return False
        return True

    def validate_medicines(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate medicines master dataset."""
        dataset = "medicines"
        if not self.validate_schema(df, SCHEMA_MEDICINES, dataset):
            return df

        # 1. Null / Missing field check
        null_mask = df[SCHEMA_MEDICINES].isnull().any(axis=1)
        if null_mask.any():
            bad_rows = df[null_mask]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} row(s) with missing values.")
            self.report.record_invalid_rows(dataset, bad_rows, "Missing mandatory medicine fields")

        # 2. Primary key uniqueness
        dup_mask = df.duplicated(subset=["medicine_id"], keep=False)
        if dup_mask.any():
            bad_rows = df[dup_mask]
            dup_ids = df.loc[dup_mask, "medicine_id"].unique().tolist()
            self.report.add_error(f"[{dataset}] Duplicate medicine_id(s) detected: {dup_ids}")
            self.report.record_invalid_rows(dataset, bad_rows, "Duplicate medicine_id")

        # 3. Numeric range check for reorder_level
        invalid_reorder = pd.to_numeric(df["reorder_level"], errors="coerce") < 0
        if invalid_reorder.any():
            bad_rows = df[invalid_reorder]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} medicine(s) with negative reorder_level.")
            self.report.record_invalid_rows(dataset, bad_rows, "Negative reorder level")

        return df

    def validate_inventory(self, df: pd.DataFrame, medicines_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Validate inventory batch dataset."""
        dataset = "inventory"
        if not self.validate_schema(df, SCHEMA_INVENTORY, dataset):
            return df

        # 1. Null / Missing field check
        null_mask = df[SCHEMA_INVENTORY].isnull().any(axis=1)
        if null_mask.any():
            bad_rows = df[null_mask]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} batch(es) with missing values.")
            self.report.record_invalid_rows(dataset, bad_rows, "Missing mandatory batch fields")

        # 2. Batch ID uniqueness
        dup_mask = df.duplicated(subset=["batch_id"], keep=False)
        if dup_mask.any():
            bad_rows = df[dup_mask]
            dup_ids = df.loc[dup_mask, "batch_id"].unique().tolist()
            self.report.add_error(f"[{dataset}] Duplicate batch_id(s) detected: {dup_ids}")
            self.report.record_invalid_rows(dataset, bad_rows, "Duplicate batch_id")

        # 3. Numeric ranges: quantity >= 0, purchase_price > 0, selling_price > 0
        numeric_qty = pd.to_numeric(df["quantity"], errors="coerce")
        numeric_purchase = pd.to_numeric(df["purchase_price"], errors="coerce")
        numeric_selling = pd.to_numeric(df["selling_price"], errors="coerce")

        neg_qty = (numeric_qty < 0) | numeric_qty.isna()
        if neg_qty.any():
            bad_rows = df[neg_qty]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} batch(es) with negative or invalid quantity.")
            self.report.record_invalid_rows(dataset, bad_rows, "Negative or invalid quantity")

        neg_purchase = (numeric_purchase <= 0) | numeric_purchase.isna()
        if neg_purchase.any():
            bad_rows = df[neg_purchase]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} batch(es) with non-positive purchase_price.")
            self.report.record_invalid_rows(dataset, bad_rows, "Non-positive purchase price")

        neg_selling = (numeric_selling <= 0) | numeric_selling.isna()
        if neg_selling.any():
            bad_rows = df[neg_selling]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} batch(es) with non-positive selling_price.")
            self.report.record_invalid_rows(dataset, bad_rows, "Non-positive selling price")

        # Price sanity warning: selling_price should generally be >= purchase_price
        loss_making = numeric_selling < numeric_purchase
        if loss_making.any():
            bad_rows = df[loss_making]
            self.report.add_warning(
                f"[{dataset}] Found {len(bad_rows)} batch(es) where selling_price is less than purchase_price."
            )
            self.report.record_invalid_rows(dataset, bad_rows, "Selling price below purchase price")

        # 4. Expiry Date validation
        parsed_dates = pd.to_datetime(df["expiry_date"], format=DATE_FORMAT, errors="coerce")
        invalid_dates = parsed_dates.isna() & df["expiry_date"].notna()
        if invalid_dates.any():
            bad_rows = df[invalid_dates]
            self.report.add_error(
                f"[{dataset}] Found {len(bad_rows)} batch(es) with invalid expiry_date format (expected YYYY-MM-DD)."
            )
            self.report.record_invalid_rows(dataset, bad_rows, "Invalid expiry date format")

        # 5. Foreign Key check against medicines
        if medicines_df is not None and "medicine_id" in medicines_df.columns:
            valid_med_ids = set(medicines_df["medicine_id"].dropna().unique())
            broken_fks = ~df["medicine_id"].isin(valid_med_ids)
            if broken_fks.any():
                bad_rows = df[broken_fks]
                unmatched = df.loc[broken_fks, "medicine_id"].unique().tolist()
                self.report.add_error(
                    f"[{dataset}] Foreign key violation: medicine_id(s) {unmatched} not found in medicines table."
                )
                self.report.record_invalid_rows(dataset, bad_rows, "Broken foreign key to medicines")

        return df

    def validate_sales(
        self,
        df: pd.DataFrame,
        inventory_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Validate sales transaction dataset and cross-reference against inventory."""
        dataset = "sales"
        if not self.validate_schema(df, SCHEMA_SALES, dataset):
            return df

        # 1. Null / Missing fields
        null_mask = df[SCHEMA_SALES].isnull().any(axis=1)
        if null_mask.any():
            bad_rows = df[null_mask]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} sale(s) with missing values.")
            self.report.record_invalid_rows(dataset, bad_rows, "Missing mandatory sale fields")

        # 2. Sale ID uniqueness
        dup_mask = df.duplicated(subset=["sale_id"], keep=False)
        if dup_mask.any():
            bad_rows = df[dup_mask]
            dup_ids = df.loc[dup_mask, "sale_id"].unique().tolist()
            self.report.add_error(f"[{dataset}] Duplicate sale_id(s) detected: {dup_ids}")
            self.report.record_invalid_rows(dataset, bad_rows, "Duplicate sale_id")

        # 3. Numeric ranges: quantity_sold > 0, unit_price > 0
        numeric_qty = pd.to_numeric(df["quantity_sold"], errors="coerce")
        numeric_price = pd.to_numeric(df["unit_price"], errors="coerce")

        bad_qty = (numeric_qty <= 0) | numeric_qty.isna()
        if bad_qty.any():
            bad_rows = df[bad_qty]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} sale(s) with non-positive quantity_sold.")
            self.report.record_invalid_rows(dataset, bad_rows, "Non-positive quantity sold")

        bad_price = (numeric_price <= 0) | numeric_price.isna()
        if bad_price.any():
            bad_rows = df[bad_price]
            self.report.add_error(f"[{dataset}] Found {len(bad_rows)} sale(s) with non-positive unit_price.")
            self.report.record_invalid_rows(dataset, bad_rows, "Non-positive unit price")

        # 4. Date validation
        parsed_dates = pd.to_datetime(df["date"], format=DATE_FORMAT, errors="coerce")
        invalid_dates = parsed_dates.isna() & df["date"].notna()
        if invalid_dates.any():
            bad_rows = df[invalid_dates]
            self.report.add_error(
                f"[{dataset}] Found {len(bad_rows)} sale(s) with invalid date format (expected YYYY-MM-DD)."
            )
            self.report.record_invalid_rows(dataset, bad_rows, "Invalid transaction date format")

        # 5. Foreign Key check against inventory batches
        if inventory_df is not None and "batch_id" in inventory_df.columns:
            valid_batch_ids = set(inventory_df["batch_id"].dropna().unique())
            broken_batches = ~df["batch_id"].isin(valid_batch_ids)
            if broken_batches.any():
                bad_rows = df[broken_batches]
                unmatched = df.loc[broken_batches, "batch_id"].unique().tolist()
                self.report.add_error(
                    f"[{dataset}] Foreign key violation: batch_id(s) {unmatched} not found in inventory table."
                )
                self.report.record_invalid_rows(dataset, bad_rows, "Broken foreign key to inventory")

        return df

    def validate_stock_consistency(
        self,
        inventory_df: pd.DataFrame,
        sales_df: pd.DataFrame,
    ) -> None:
        """Verify stock consistency and calculate analytical summary metrics using NumPy and Pandas."""
        if "batch_id" not in inventory_df.columns or "batch_id" not in sales_df.columns:
            return

        # Calculate total units sold per batch using Pandas grouping
        sold_per_batch = sales_df.groupby("batch_id")["quantity_sold"].sum().reset_index()
        sold_per_batch.rename(columns={"quantity_sold": "total_sold"}, inplace=True)

        # Merge with inventory
        merged = pd.merge(inventory_df, sold_per_batch, on="batch_id", how="left")
        merged["total_sold"] = merged["total_sold"].fillna(0)

        # Summary calculations using NumPy
        total_medicines = len(inventory_df["medicine_id"].unique()) if "medicine_id" in inventory_df.columns else 0
        total_batches = len(inventory_df)
        total_current_units = np.sum(pd.to_numeric(inventory_df["quantity"], errors="coerce").fillna(0).to_numpy())
        total_sales_units = np.sum(pd.to_numeric(sales_df["quantity_sold"], errors="coerce").fillna(0).to_numpy())

        # Calculate revenue with NumPy vectorized multiplication
        unit_prices = pd.to_numeric(sales_df["unit_price"], errors="coerce").fillna(0).to_numpy()
        quantities = pd.to_numeric(sales_df["quantity_sold"], errors="coerce").fillna(0).to_numpy()
        total_revenue = float(np.sum(unit_prices * quantities))

        self.report.summary_stats = {
            "Total Unique Medicines in Stock": int(total_medicines),
            "Total Batches Tracked": int(total_batches),
            "Total Current Stock (Units)": int(total_current_units),
            "Total Transactions Recorded": len(sales_df),
            "Total Units Sold": int(total_sales_units),
            "Total Gross Revenue ($)": round(total_revenue, 2),
            "Average Transaction Value ($)": round(total_revenue / max(1, len(sales_df)), 2),
        }


def validate_all_datasets(
    medicines_df: pd.DataFrame,
    inventory_df: pd.DataFrame,
    sales_df: pd.DataFrame,
) -> Tuple[bool, ValidationReport]:
    """Execute end-to-end relational and schema validation across all 3 datasets."""
    validator = DataValidator()

    # Clean leading/trailing string whitespaces
    for df in (medicines_df, inventory_df, sales_df):
        str_cols = df.select_dtypes(include=["object", "string"]).columns
        df[str_cols] = df[str_cols].apply(lambda s: s.str.strip() if hasattr(s, "str") else s)

    # Validate individual tables and relational constraints
    validator.validate_medicines(medicines_df)
    validator.validate_inventory(inventory_df, medicines_df=medicines_df)
    validator.validate_sales(sales_df, inventory_df=inventory_df)
    validator.validate_stock_consistency(inventory_df, sales_df)

    return validator.report.is_valid, validator.report
