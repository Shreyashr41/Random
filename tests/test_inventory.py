"""Automated test suite for Phase 2: Medicine and batch-level inventory management."""

from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from config import EXPORTS_DIR, REFERENCE_DATE
from src.data import generate_synthetic_datasets, clean_and_type_coerce
from src.inventory import (
    calculate_inventory_valuation_metrics,
    calculate_replenishment_suggestions,
    export_inventory_report,
    filter_inventory,
    get_batch_inventory_summary,
    get_low_stock_alerts,
    get_medicine_inventory_summary,
)


@pytest.fixture
def test_data():
    """Load clean in-memory synthetic datasets."""
    datasets = generate_synthetic_datasets(seed=42, save_to_disk=False)
    med, inv, sal = clean_and_type_coerce(
        datasets["medicines"],
        datasets["inventory"],
        datasets["sales"],
    )
    return {"medicines": med, "inventory": inv, "sales": sal}


def test_batch_inventory_summary_valuation_and_expiry(test_data):
    """Verify batch summary computes correct purchase valuation and identifies expired batches."""
    med = test_data["medicines"]
    inv = test_data["inventory"]

    as_of = "2026-10-25"
    batches = get_batch_inventory_summary(inv, med, as_of_date=as_of)

    assert len(batches) == len(inv)
    assert "purchase_value" in batches.columns
    assert "potential_selling_value" in batches.columns
    assert "is_expired" in batches.columns
    assert "is_usable" in batches.columns
    assert "expiry_status" in batches.columns

    # Check mathematical correctness on the first row
    r0 = batches.iloc[0]
    expected_purchase_val = round(r0["quantity"] * r0["purchase_price"], 2)
    assert round(r0["purchase_value"], 2) == expected_purchase_val

    # Check that expired batches are flagged correctly
    for _, row in batches.iterrows():
        if pd.to_datetime(row["expiry_date"]) < pd.to_datetime(as_of):
            assert bool(row["is_expired"]) is True
            assert bool(row["is_usable"]) is False
            assert row["expiry_status"] == "Expired"
        elif row["quantity"] > 0:
            assert bool(row["is_usable"]) is True


def test_expired_stock_exclusion_from_usable_quantity():
    """Verify expired batches are strictly excluded from usable inventory quantity."""
    med_df = pd.DataFrame([
        {"medicine_id": "M1", "medicine_name": "Test Med 1", "category": "General", "reorder_level": 50}
    ])
    # Batch 1 expired (expiry 2026-09-01), Batch 2 valid (expiry 2027-05-01)
    inv_df = pd.DataFrame([
        {
            "batch_id": "B1",
            "medicine_id": "M1",
            "quantity": 100,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-09-01",
            "supplier": "Supplier A",
        },
        {
            "batch_id": "B2",
            "medicine_id": "M1",
            "quantity": 30,
            "purchase_price": 12.0,
            "selling_price": 18.0,
            "expiry_date": "2027-05-01",
            "supplier": "Supplier B",
        },
    ])

    summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date="2026-10-25")
    assert len(summary) == 1
    row = summary.iloc[0]

    # Total physical stock is 130, but usable stock must be ONLY 30
    assert row["total_physical_stock"] == 130
    assert row["usable_quantity"] == 30
    assert row["expired_quantity"] == 100

    # Usable stock is 30 <= reorder_level 50 -> low stock
    assert bool(row["is_low_stock"]) is True
    assert bool(row["is_out_of_stock"]) is False
    assert row["stock_deficit"] == 20


def test_out_of_stock_when_all_batches_expired():
    """Verify a medicine is marked Out of Stock if all its stock is expired."""
    med_df = pd.DataFrame([
        {"medicine_id": "M2", "medicine_name": "Test Med 2", "category": "General", "reorder_level": 20}
    ])
    inv_df = pd.DataFrame([
        {
            "batch_id": "B3",
            "medicine_id": "M2",
            "quantity": 80,
            "purchase_price": 5.0,
            "selling_price": 8.0,
            "expiry_date": "2026-01-01",
            "supplier": "Supplier A",
        }
    ])

    summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date="2026-10-25")
    row = summary.iloc[0]

    assert row["total_physical_stock"] == 80
    assert row["usable_quantity"] == 0
    assert row["expired_quantity"] == 80
    assert bool(row["is_out_of_stock"]) is True
    assert row["stock_status"] == "Out of Stock"


def test_multiple_batches_per_medicine_aggregation(test_data):
    """Verify medicines with multiple batches aggregate cleanly without double-counting."""
    med = test_data["medicines"]
    inv = test_data["inventory"]

    summary = get_medicine_inventory_summary(inv, med, as_of_date="2026-10-25")
    assert len(summary) == len(med)

    # Check total physical stock across all medicines matches total quantity in batches
    total_physical_batches = inv["quantity"].sum()
    total_physical_summary = summary["total_physical_stock"].sum()
    assert total_physical_batches == total_physical_summary

    # Ensure batch counts are positive
    assert (summary["batch_count"] > 0).all()


def test_low_stock_alerts_filtering(test_data):
    """Verify low stock alerts filter correctly and order by urgency."""
    med = test_data["medicines"]
    inv = test_data["inventory"]

    summary = get_medicine_inventory_summary(inv, med, as_of_date="2026-10-25")
    alerts_standard = get_low_stock_alerts(summary, threshold_factor=1.0)
    alerts_buffered = get_low_stock_alerts(summary, threshold_factor=1.5)

    # Buffered alert threshold should catch equal or more medicines than standard
    assert len(alerts_buffered) >= len(alerts_standard)

    for _, row in alerts_standard.iterrows():
        assert row["usable_quantity"] <= row["reorder_level"]


def test_medicines_with_no_sales_history_fallback_replenishment():
    """Verify replenishment suggestion safely handles medicines without any sales history."""
    med_df = pd.DataFrame([
        {"medicine_id": "M_NEW", "medicine_name": "Newly Introduced Medicine", "category": "Vitamins", "reorder_level": 30}
    ])
    inv_df = pd.DataFrame([
        {
            "batch_id": "B_NEW",
            "medicine_id": "M_NEW",
            "quantity": 10,  # Below reorder level 30
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2027-10-25",
            "supplier": "Supplier X",
        }
    ])
    # Empty sales dataframe (no sales records)
    empty_sales = pd.DataFrame(columns=["sale_id", "date", "batch_id", "quantity_sold", "unit_price", "medicine_id"])

    summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date="2026-10-25")
    suggestions = calculate_replenishment_suggestions(summary, sales_df=empty_sales)

    assert len(suggestions) == 1
    sug = suggestions.iloc[0]
    assert sug["medicine_id"] == "M_NEW"
    assert sug["calculation_method"] == "rule_fallback"
    assert np.isnan(sug["estimated_runout_days"])
    assert sug["avg_daily_demand"] == 0.0
    # Rule fallback calculates reorder: 30 * 2.5 - 10 = 65 units
    assert sug["suggested_reorder_qty"] > 0
    assert "estimate" in sug["recommendation_notice"].lower()


def test_demand_based_replenishment_with_sales_history(test_data):
    """Verify demand-based replenishment suggestion when sales history is present."""
    med = test_data["medicines"]
    inv = test_data["inventory"]
    sal = test_data["sales"]

    # Add medicine_id to sales for direct mapping
    sales_merged = pd.merge(sal, inv[["batch_id", "medicine_id"]], on="batch_id", how="left")

    summary = get_medicine_inventory_summary(inv, med, as_of_date="2026-10-25")
    suggestions = calculate_replenishment_suggestions(summary, sales_df=sales_merged, lead_time_days=7, safety_factor=1.5)

    assert len(suggestions) == len(med)
    demand_based = suggestions[suggestions["calculation_method"] == "demand_based"]
    assert len(demand_based) > 0

    for _, row in demand_based.iterrows():
        assert row["avg_daily_demand"] > 0
        assert not np.isnan(row["estimated_runout_days"])


def test_inventory_filtering(test_data):
    """Verify multi-criteria filtering by medicine_id, category, supplier, and expiry status."""
    med = test_data["medicines"]
    inv = test_data["inventory"]

    batches = get_batch_inventory_summary(inv, med, as_of_date="2026-10-25")

    # Filter by category
    antibiotics = filter_inventory(batches, category="Antibiotics")
    assert len(antibiotics) > 0
    assert (antibiotics["category"] == "Antibiotics").all()

    # Filter by specific medicine_id
    med_001 = filter_inventory(batches, medicine_id="MED-001")
    assert len(med_001) > 0
    assert (med_001["medicine_id"] == "MED-001").all()

    # Filter by supplier
    supplier_name = batches.iloc[0]["supplier"]
    by_supplier = filter_inventory(batches, supplier=supplier_name)
    assert len(by_supplier) > 0
    assert (by_supplier["supplier"] == supplier_name).all()

    # Exclude expired stock
    usable_only = filter_inventory(batches, exclude_expired=True)
    assert len(usable_only) > 0
    assert not usable_only["is_expired"].any()


def test_inventory_valuation_metrics_calculation(test_data):
    """Verify overall inventory metrics and financial KPIs."""
    inv = test_data["inventory"]
    metrics = calculate_inventory_valuation_metrics(inv, as_of_date="2026-10-25")

    assert metrics["total_batches_tracked"] == len(inv)
    assert metrics["total_physical_stock_units"] > 0
    assert metrics["usable_stock_units"] > 0
    assert metrics["expired_stock_units"] >= 0
    assert metrics["usable_stock_units"] + metrics["expired_stock_units"] == metrics["total_physical_stock_units"]
    assert metrics["total_purchase_valuation"] > 0
    assert metrics["usable_purchase_valuation"] > 0
    assert metrics["usable_purchase_valuation"] <= metrics["total_purchase_valuation"]


def test_export_inventory_report(test_data, tmp_path):
    """Verify inventory report export writes valid CSV file."""
    med = test_data["medicines"]
    inv = test_data["inventory"]
    summary = get_medicine_inventory_summary(inv, med, as_of_date="2026-10-25")

    export_path = export_inventory_report(summary, filename="test_summary_export.csv", export_dir=tmp_path)
    assert export_path.exists()
    assert export_path.stat().st_size > 0

    read_back = pd.read_csv(export_path)
    assert len(read_back) == len(summary)
    assert "usable_quantity" in read_back.columns
