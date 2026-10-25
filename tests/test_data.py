"""Automated test suite for Phase 1: Data ingestion, generation, validation, and merging."""

import copy
from datetime import datetime
import numpy as np
import pandas as pd
import pytest

from config import RAW_DATA_DIR
from src.data import (
    DataValidator,
    ValidationReport,
    clean_and_type_coerce,
    generate_synthetic_datasets,
    get_unified_sales_data,
    ingest_and_validate_data,
    validate_all_datasets,
)


@pytest.fixture
def sample_datasets():
    """Generate in-memory clean sample datasets with a fixed seed."""
    return generate_synthetic_datasets(seed=42, save_to_disk=False)


def test_reproducibility():
    """Verify that synthetic dataset generation is 100% deterministic given the same seed."""
    run1 = generate_synthetic_datasets(seed=999, save_to_disk=False)
    run2 = generate_synthetic_datasets(seed=999, save_to_disk=False)

    pd.testing.assert_frame_equal(run1["medicines"], run2["medicines"])
    pd.testing.assert_frame_equal(run1["inventory"], run2["inventory"])
    pd.testing.assert_frame_equal(run1["sales"], run2["sales"])


def test_valid_datasets_pass_validation(sample_datasets):
    """Verify that generated synthetic data passes all validation rules with zero errors."""
    med = sample_datasets["medicines"]
    inv = sample_datasets["inventory"]
    sal = sample_datasets["sales"]

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is True
    assert len(report.errors) == 0
    assert report.summary_stats["Total Unique Medicines in Stock"] > 0
    assert report.summary_stats["Total Batches Tracked"] > 0
    assert report.summary_stats["Total Current Stock (Units)"] > 0
    assert report.summary_stats["Total Transactions Recorded"] > 0
    assert report.summary_stats["Total Gross Revenue ($)"] > 0


def test_detect_missing_values(sample_datasets):
    """Verify validator catches null or missing mandatory fields and records the offending rows."""
    med = sample_datasets["medicines"].copy()
    inv = sample_datasets["inventory"].copy()
    sal = sample_datasets["sales"].copy()

    # Introduce nulls in key columns
    med.loc[0, "medicine_name"] = np.nan
    inv.loc[1, "purchase_price"] = np.nan
    sal.loc[2, "quantity_sold"] = np.nan

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is False
    assert any("missing values" in err.lower() for err in report.errors)
    assert "medicines" in report.invalid_records
    assert "inventory" in report.invalid_records
    assert "sales" in report.invalid_records


def test_detect_duplicate_primary_keys(sample_datasets):
    """Verify validator flags duplicate IDs in medicines, inventory, and sales."""
    med = sample_datasets["medicines"].copy()
    inv = sample_datasets["inventory"].copy()
    sal = sample_datasets["sales"].copy()

    # Duplicate first row of each dataset
    med = pd.concat([med, med.iloc[[0]]], ignore_index=True)
    inv = pd.concat([inv, inv.iloc[[0]]], ignore_index=True)
    sal = pd.concat([sal, sal.iloc[[0]]], ignore_index=True)

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is False
    assert any("duplicate medicine_id" in err.lower() for err in report.errors)
    assert any("duplicate batch_id" in err.lower() for err in report.errors)
    assert any("duplicate sale_id" in err.lower() for err in report.errors)


def test_detect_broken_foreign_keys(sample_datasets):
    """Verify validator detects foreign key violations when child records reference non-existent parents."""
    med = sample_datasets["medicines"].copy()
    inv = sample_datasets["inventory"].copy()
    sal = sample_datasets["sales"].copy()

    # Broken FK in inventory pointing to ghost medicine
    inv.loc[0, "medicine_id"] = "MED-NONEXISTENT-999"

    # Broken FK in sales pointing to ghost batch
    sal.loc[0, "batch_id"] = "BAT-NONEXISTENT-999"

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is False
    assert any("med-nonexistent-999" in err.lower() for err in report.errors)
    assert any("bat-nonexistent-999" in err.lower() for err in report.errors)


def test_detect_invalid_dates(sample_datasets):
    """Verify validator catches corrupt or invalid date formats."""
    med = sample_datasets["medicines"].copy()
    inv = sample_datasets["inventory"].copy()
    sal = sample_datasets["sales"].copy()

    # Non-standard or nonsensical dates
    inv.loc[0, "expiry_date"] = "2026/12/31"  # Slash format instead of dash
    inv.loc[1, "expiry_date"] = "invalid-date-string"
    sal.loc[0, "date"] = "31-10-2026"  # DD-MM-YYYY instead of YYYY-MM-DD

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is False
    assert any("expiry_date format" in err.lower() for err in report.errors)
    assert any("date format" in err.lower() for err in report.errors)


def test_detect_negative_and_zero_values(sample_datasets):
    """Verify validator catches negative stock, negative prices, and non-positive sales."""
    med = sample_datasets["medicines"].copy()
    inv = sample_datasets["inventory"].copy()
    sal = sample_datasets["sales"].copy()

    med.loc[0, "reorder_level"] = -10
    inv.loc[0, "quantity"] = -5
    inv.loc[1, "purchase_price"] = -2.50
    sal.loc[0, "quantity_sold"] = 0
    sal.loc[1, "unit_price"] = -15.00

    is_valid, report = validate_all_datasets(med, inv, sal)
    assert is_valid is False
    assert any("negative reorder_level" in err.lower() for err in report.errors)
    assert any("negative or invalid quantity" in err.lower() for err in report.errors)
    assert any("non-positive purchase_price" in err.lower() for err in report.errors)
    assert any("non-positive quantity_sold" in err.lower() for err in report.errors)
    assert any("non-positive unit_price" in err.lower() for err in report.errors)


def test_unified_sales_data_calculations(sample_datasets):
    """Verify that get_unified_sales_data properly joins datasets and computes COGS & margins."""
    med, inv, sal = clean_and_type_coerce(
        sample_datasets["medicines"],
        sample_datasets["inventory"],
        sample_datasets["sales"],
    )

    unified = get_unified_sales_data(med, inv, sal)
    assert len(unified) == len(sal)

    # Check that computed columns exist
    expected_cols = [
        "sale_id",
        "date",
        "batch_id",
        "quantity_sold",
        "unit_price",
        "purchase_price",
        "total_revenue",
        "total_cost",
        "gross_profit",
        "margin_pct",
        "medicine_name",
        "category",
    ]
    for col in expected_cols:
        assert col in unified.columns

    # Verify mathematical accuracy of vectorized calculations
    first_row = unified.iloc[0]
    expected_rev = round(first_row["quantity_sold"] * first_row["unit_price"], 2)
    expected_cost = round(first_row["quantity_sold"] * first_row["purchase_price"], 2)
    expected_profit = round(expected_rev - expected_cost, 2)

    assert round(first_row["total_revenue"], 2) == expected_rev
    assert round(first_row["total_cost"], 2) == expected_cost
    assert round(first_row["gross_profit"], 2) == expected_profit


def test_ingest_and_validate_from_disk():
    """Verify end-to-end ingestion and export to processed/ directory."""
    cleaned_dict, report = ingest_and_validate_data(data_dir=RAW_DATA_DIR, export_processed=True)
    assert report.is_valid is True
    assert len(cleaned_dict["medicines"]) > 0
    assert len(cleaned_dict["inventory"]) > 0
    assert len(cleaned_dict["sales"]) > 0
