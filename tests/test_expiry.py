"""Automated test suite for Phase 4: Expiry and wastage risk analysis."""

from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from config import EXPORTS_DIR, REFERENCE_DATE
from src.data import generate_synthetic_datasets, clean_and_type_coerce
from src.expiry import (
    EXPOSURE_RISK_DISCLOSURE,
    analyze_recorded_wastage,
    calculate_expiry_exposure_metrics,
    classify_batch_expiry,
    export_expiry_report,
    get_fefo_stock_rotation_queue,
    get_high_value_near_expiry_batches,
)


@pytest.fixture
def sample_data():
    """Load clean in-memory synthetic datasets."""
    datasets = generate_synthetic_datasets(seed=42, save_to_disk=False)
    med, inv, sal = clean_and_type_coerce(
        datasets["medicines"],
        datasets["inventory"],
        datasets["sales"],
    )
    return {"medicines": med, "inventory": inv, "sales": sal}


def test_expired_batches_classification_and_invariant():
    """Verify expired batches are correctly identified and NEVER classified as near expiry."""
    as_of = "2026-10-25"
    inv_df = pd.DataFrame([
        {
            "batch_id": "B_EXP1",
            "medicine_id": "M1",
            "quantity": 50,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-10-20",  # Expired 5 days ago
            "supplier": "Distributor A",
        },
        {
            "batch_id": "B_EXP2",
            "medicine_id": "M1",
            "quantity": 20,
            "purchase_price": 12.0,
            "selling_price": 18.0,
            "expiry_date": "2026-06-01",  # Expired months ago
            "supplier": "Distributor B",
        },
    ])

    classified = classify_batch_expiry(inv_df, near_expiry_days=30, as_of_date=as_of)

    for _, row in classified.iterrows():
        assert row["days_remaining"] < 0
        assert bool(row["is_expired"]) is True
        # Critical Invariant: An expired batch must NEVER be classified as near expiry
        assert bool(row["is_near_expiry"]) is False
        assert row["expiry_classification"] == "Expired"
        assert bool(row["is_usable"]) is False


def test_dates_at_warning_threshold_and_expiring_today():
    """Verify precise classification at warning boundary and for batches expiring today."""
    as_of = "2026-10-25"
    inv_df = pd.DataFrame([
        {
            "batch_id": "B_TODAY",
            "medicine_id": "M1",
            "quantity": 10,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-10-25",  # Expiring TODAY (days_remaining == 0)
            "supplier": "Supplier A",
        },
        {
            "batch_id": "B_DAY30",
            "medicine_id": "M1",
            "quantity": 15,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-11-24",  # Exactly 30 days remaining
            "supplier": "Supplier A",
        },
        {
            "batch_id": "B_DAY31",
            "medicine_id": "M1",
            "quantity": 25,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-11-25",  # Exactly 31 days remaining (outside 30-day window)
            "supplier": "Supplier A",
        },
    ])

    classified = classify_batch_expiry(inv_df, near_expiry_days=30, as_of_date=as_of)

    # 1. Expiring Today
    b_today = classified[classified["batch_id"] == "B_TODAY"].iloc[0]
    assert b_today["days_remaining"] == 0
    assert bool(b_today["is_expired"]) is False
    assert bool(b_today["is_near_expiry"]) is True
    assert b_today["expiry_classification"] == "Expiring Today"

    # 2. Exactly at 30-day boundary
    b_30 = classified[classified["batch_id"] == "B_DAY30"].iloc[0]
    assert b_30["days_remaining"] == 30
    assert bool(b_30["is_near_expiry"]) is True
    assert b_30["expiry_classification"] == "Near Expiry (≤30d)"

    # 3. Exactly at 31 days (outside threshold)
    b_31 = classified[classified["batch_id"] == "B_DAY31"].iloc[0]
    assert b_31["days_remaining"] == 31
    assert bool(b_31["is_near_expiry"]) is False
    assert b_31["expiry_classification"] == "Safe / Healthy"


def test_configurable_near_expiry_threshold():
    """Verify near-expiry classification updates when threshold is changed (e.g. to 60 days)."""
    as_of = "2026-10-25"
    inv_df = pd.DataFrame([
        {
            "batch_id": "B_45D",
            "medicine_id": "M1",
            "quantity": 40,
            "purchase_price": 10.0,
            "selling_price": 15.0,
            "expiry_date": "2026-12-09",  # 45 days remaining
            "supplier": "Supplier A",
        }
    ])

    # With 30-day threshold -> Safe
    res_30 = classify_batch_expiry(inv_df, near_expiry_days=30, as_of_date=as_of)
    assert bool(res_30.iloc[0]["is_near_expiry"]) is False

    # With 60-day threshold -> Near Expiry
    res_60 = classify_batch_expiry(inv_df, near_expiry_days=60, as_of_date=as_of)
    assert bool(res_60.iloc[0]["is_near_expiry"]) is True
    assert res_60.iloc[0]["expiry_classification"] == "Near Expiry (≤60d)"


def test_zero_stock_batches():
    """Verify batches with zero stock have zero value at risk and are handled safely."""
    as_of = "2026-10-25"
    inv_df = pd.DataFrame([
        {
            "batch_id": "B_ZERO",
            "medicine_id": "M1",
            "quantity": 0,
            "purchase_price": 50.0,
            "selling_price": 75.0,
            "expiry_date": "2026-11-10",  # Near expiry but empty
            "supplier": "Supplier A",
        }
    ])

    classified = classify_batch_expiry(inv_df, near_expiry_days=30, as_of_date=as_of)
    row = classified.iloc[0]

    assert row["quantity"] == 0
    assert row["value_at_risk"] == 0.0
    assert row["potential_selling_value"] == 0.0
    assert bool(row["is_high_value_risk"]) is False
    assert bool(row["is_usable"]) is False


def test_value_at_risk_calculation_and_disclosure(sample_data):
    """Verify purchase value of remaining near-expiry stock at risk and required disclosure."""
    inv = sample_data["inventory"]
    metrics = calculate_expiry_exposure_metrics(inv, near_expiry_days=30, as_of_date="2026-10-25")

    assert metrics["total_batches_evaluated"] == len(inv)
    assert metrics["expired_batches_count"] > 0
    assert metrics["near_expiry_batches_count"] > 0
    assert metrics["expired_stock_holding_cost"] > 0
    assert metrics["near_expiry_purchase_value_at_risk"] >= 0
    assert metrics["near_expiry_potential_revenue_at_risk"] >= metrics["near_expiry_purchase_value_at_risk"]

    # Verify disclosure notice that exposure is not actual loss
    assert "disclosure" in metrics
    assert EXPOSURE_RISK_DISCLOSURE in metrics["disclosure"]
    assert "operational risk exposure" in metrics["disclosure"].lower()


def test_high_value_near_expiry_batches_filtering(sample_data):
    """Verify high-value near-expiry batches are properly isolated and sorted by risk value."""
    inv = sample_data["inventory"]
    med = sample_data["medicines"]

    high_val = get_high_value_near_expiry_batches(
        inv,
        medicines_df=med,
        near_expiry_days=90,
        min_value_threshold=200.0,
        as_of_date="2026-10-25",
    )

    if not high_val.empty:
        assert (high_val["value_at_risk"] >= 200.0).all()
        assert (high_val["is_near_expiry"]).all()
        # Verify descending order
        if len(high_val) > 1:
            assert high_val.iloc[0]["value_at_risk"] >= high_val.iloc[1]["value_at_risk"]


def test_fefo_stock_rotation_queue_multiple_batches():
    """Verify FEFO stock rotation prioritizes earliest expiring batches and quarantines expired stock."""
    as_of = "2026-10-25"
    med = pd.DataFrame([
        {"medicine_id": "M_AMOX", "medicine_name": "Amoxicillin 500mg", "category": "Antibiotics"}
    ])
    # 3 batches: 1 expired, 1 expiring in 20 days, 1 expiring in 200 days
    inv = pd.DataFrame([
        {
            "batch_id": "BAT_HEALTHY",
            "medicine_id": "M_AMOX",
            "quantity": 100,
            "purchase_price": 5.0,
            "selling_price": 8.0,
            "expiry_date": "2027-05-15",  # Healthy
            "supplier": "Dist A",
        },
        {
            "batch_id": "BAT_EXPIRED",
            "medicine_id": "M_AMOX",
            "quantity": 30,
            "purchase_price": 5.0,
            "selling_price": 8.0,
            "expiry_date": "2026-09-01",  # Expired
            "supplier": "Dist A",
        },
        {
            "batch_id": "BAT_NEAR",
            "medicine_id": "M_AMOX",
            "quantity": 40,
            "purchase_price": 5.0,
            "selling_price": 8.0,
            "expiry_date": "2026-11-14",  # Expiring in 20 days
            "supplier": "Dist B",
        },
    ])

    fefo_queue = get_fefo_stock_rotation_queue(inv, medicines_df=med, as_of_date=as_of)

    # 1. BAT_NEAR should be Dispense Priority #1
    p1 = fefo_queue[fefo_queue["batch_id"] == "BAT_NEAR"].iloc[0]
    assert p1["fefo_dispense_priority"] == 1
    assert "Priority #1" in p1["fefo_recommendation"]

    # 2. BAT_HEALTHY should be Dispense Priority #2
    p2 = fefo_queue[fefo_queue["batch_id"] == "BAT_HEALTHY"].iloc[0]
    assert p2["fefo_dispense_priority"] == 2
    assert "Priority #2" in p2["fefo_recommendation"]

    # 3. BAT_EXPIRED must be quarantined (DO NOT DISPENSE)
    p_exp = fefo_queue[fefo_queue["batch_id"] == "BAT_EXPIRED"].iloc[0]
    assert p_exp["fefo_dispense_priority"] == -1
    assert "DO NOT DISPENSE" in p_exp["fefo_recommendation"]


def test_analyze_recorded_wastage_without_and_with_records():
    """Verify wastage analyzer does not falsely claim wastage unless records exist."""
    # 1. Without wastage records
    no_wastage = analyze_recorded_wastage(wastage_df=None)
    assert no_wastage["has_recorded_wastage"] is False
    assert no_wastage["total_wastage_loss"] == 0.0
    assert "No recorded wastage" in no_wastage["message"]

    # 2. With explicit wastage records
    wastage_data = pd.DataFrame([
        {"wastage_id": "W1", "date": "2026-09-10", "batch_id": "B1", "quantity_wasted": 10, "cost_per_unit": 5.0, "reason": "Damaged Packaging"},
        {"wastage_id": "W2", "date": "2026-09-15", "batch_id": "B2", "quantity_wasted": 5, "cost_per_unit": 20.0, "reason": "Expired Stock"},
    ])
    with_wastage = analyze_recorded_wastage(wastage_df=wastage_data)
    assert with_wastage["has_recorded_wastage"] is True
    assert with_wastage["total_units_wasted"] == 15
    assert with_wastage["total_wastage_loss"] == 150.0  # 10*5 + 5*20 = 150
    assert len(with_wastage["wastage_by_reason"]) == 2


def test_export_expiry_report(sample_data, tmp_path):
    """Verify export of expiry risk reports to CSV."""
    inv = sample_data["inventory"]
    classified = classify_batch_expiry(inv, as_of_date="2026-10-25")

    export_path = export_expiry_report(classified, filename="test_expiry_report.csv", export_dir=tmp_path)
    assert export_path.exists()
    assert export_path.stat().st_size > 0

    read_back = pd.read_csv(export_path)
    assert len(read_back) == len(classified)
    assert "expiry_classification" in read_back.columns
    assert "value_at_risk" in read_back.columns
