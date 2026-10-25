"""Automated test suite for Phase 3: Sales, revenue, profit, and demand analytics."""

from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from config import EXPORTS_DIR, REFERENCE_DATE
from src.data import generate_synthetic_datasets, clean_and_type_coerce
from src.analytics import (
    DEMAND_ESTIMATE_DISCLAIMER,
    calculate_sales_statistics,
    estimate_demand_trends,
    export_analytics_summary,
    get_periodic_sales_summary,
    get_sales_by_dimension,
    get_slow_moving_medicines,
    get_top_selling_medicines,
    prepare_enriched_sales,
)


@pytest.fixture
def raw_data():
    """Load clean in-memory synthetic datasets."""
    datasets = generate_synthetic_datasets(seed=42, save_to_disk=False)
    med, inv, sal = clean_and_type_coerce(
        datasets["medicines"],
        datasets["inventory"],
        datasets["sales"],
    )
    return {"medicines": med, "inventory": inv, "sales": sal}


@pytest.fixture
def enriched_sales(raw_data):
    """Generate pre-enriched sales DataFrame."""
    return prepare_enriched_sales(
        raw_data["sales"],
        raw_data["inventory"],
        raw_data["medicines"],
    )


def test_prepare_enriched_sales_cogs_and_profit(raw_data):
    """Verify enriched sales calculates revenue, actual batch COGS, and gross profit."""
    med = raw_data["medicines"]
    inv = raw_data["inventory"]
    sal = raw_data["sales"]

    enriched = prepare_enriched_sales(sal, inv, med)

    assert len(enriched) == len(sal)
    assert "total_revenue" in enriched.columns
    assert "total_cogs" in enriched.columns
    assert "gross_profit" in enriched.columns
    assert "margin_pct" in enriched.columns

    # Verify mathematics on row 0
    r0 = enriched.iloc[0]
    expected_rev = round(r0["quantity_sold"] * r0["unit_price"], 2)
    expected_cogs = round(r0["quantity_sold"] * r0["purchase_price"], 2)
    expected_profit = round(expected_rev - expected_cogs, 2)

    assert round(r0["total_revenue"], 2) == expected_rev
    assert round(r0["total_cogs"], 2) == expected_cogs
    assert round(r0["gross_profit"], 2) == expected_profit

    # Confirm revenue is never treated as profit
    assert (enriched["total_revenue"] >= enriched["gross_profit"]).all()


def test_cogs_uses_actual_batch_cost():
    """Verify gross profit uses the specific purchase cost of the batch sold, not a generic price."""
    med = pd.DataFrame([
        {"medicine_id": "M1", "medicine_name": "Test Med", "category": "General", "reorder_level": 10}
    ])
    # Batch 1 cheap ($10), Batch 2 expensive ($25)
    inv = pd.DataFrame([
        {
            "batch_id": "B1",
            "medicine_id": "M1",
            "quantity": 50,
            "purchase_price": 10.0,
            "selling_price": 30.0,
            "expiry_date": "2027-01-01",
            "supplier": "S1",
        },
        {
            "batch_id": "B2",
            "medicine_id": "M1",
            "quantity": 50,
            "purchase_price": 25.0,
            "selling_price": 30.0,
            "expiry_date": "2027-01-01",
            "supplier": "S2",
        },
    ])
    sales = pd.DataFrame([
        {"sale_id": "S1", "date": "2026-09-01", "batch_id": "B1", "quantity_sold": 2, "unit_price": 30.0},
        {"sale_id": "S2", "date": "2026-09-02", "batch_id": "B2", "quantity_sold": 2, "unit_price": 30.0},
    ])

    enriched = prepare_enriched_sales(sales, inv, med)

    # Sale 1 (from B1): Rev $60, COGS $20, Profit $40
    s1 = enriched[enriched["sale_id"] == "S1"].iloc[0]
    assert s1["total_cogs"] == 20.0
    assert s1["gross_profit"] == 40.0

    # Sale 2 (from B2): Rev $60, COGS $50, Profit $10
    s2 = enriched[enriched["sale_id"] == "S2"].iloc[0]
    assert s2["total_cogs"] == 50.0
    assert s2["gross_profit"] == 10.0


def test_periodic_sales_summary(enriched_sales):
    """Verify daily, weekly, and monthly time-series aggregations."""
    daily = get_periodic_sales_summary(enriched_sales, freq="D")
    weekly = get_periodic_sales_summary(enriched_sales, freq="W")
    monthly = get_periodic_sales_summary(enriched_sales, freq="M")

    assert len(daily) > 0
    assert len(weekly) > 0
    assert len(monthly) > 0
    assert len(monthly) <= len(weekly) <= len(daily)

    # Verify overall revenue consistency across different time aggregations
    sum_daily_rev = round(daily["total_revenue"].sum(), 2)
    sum_monthly_rev = round(monthly["total_revenue"].sum(), 2)
    total_raw_rev = round(enriched_sales["total_revenue"].sum(), 2)

    assert sum_daily_rev == total_raw_rev
    assert sum_monthly_rev == total_raw_rev


def test_sales_by_dimension_and_date_filtering(enriched_sales):
    """Verify grouping by medicine and category, and date range filtering."""
    by_category = get_sales_by_dimension(enriched_sales, dimension="category")
    assert len(by_category) > 0
    assert "category" in by_category.columns
    assert "gross_margin_pct" in by_category.columns
    assert "avg_selling_price" in by_category.columns

    # Test date filtering
    filtered = get_sales_by_dimension(
        enriched_sales,
        dimension="medicine",
        start_date="2026-08-01",
        end_date="2026-08-31",
    )
    assert len(filtered) > 0
    # Revenue in August must be <= total revenue
    assert filtered["total_revenue"].sum() <= enriched_sales["total_revenue"].sum()


def test_top_selling_medicines(enriched_sales):
    """Verify top-selling medicines ranking by revenue, units, and margin shares."""
    top_rev = get_top_selling_medicines(enriched_sales, top_n=5, rank_by="revenue")
    top_qty = get_top_selling_medicines(enriched_sales, top_n=5, rank_by="quantity")

    assert len(top_rev) <= 5
    assert len(top_qty) <= 5
    assert list(top_rev["rank"]) == [1, 2, 3, 4, 5]

    # Revenue of rank 1 should be >= rank 2
    assert top_rev.iloc[0]["total_revenue"] >= top_rev.iloc[1]["total_revenue"]
    # Quantity of rank 1 in top_qty should be >= rank 2
    assert top_qty.iloc[0]["units_sold"] >= top_qty.iloc[1]["units_sold"]

    # Verify revenue share percentage is calculated and > 0
    assert (top_rev["revenue_share_pct"] > 0).all()


def test_slow_moving_medicines_identification(raw_data, enriched_sales):
    """Verify slow-moving medicine identification and inclusion of zero-sales medicines."""
    med = raw_data["medicines"]
    inv = raw_data["inventory"]

    # Add a medicine with zero sales
    med_with_stagnant = pd.concat([
        med,
        pd.DataFrame([{"medicine_id": "MED-ZERO", "medicine_name": "Zero Sales Medicine", "category": "Rare", "reorder_level": 10}]),
    ], ignore_index=True)

    inv_with_stagnant = pd.concat([
        inv,
        pd.DataFrame([{
            "batch_id": "BAT-ZERO",
            "medicine_id": "MED-ZERO",
            "quantity": 100,
            "purchase_price": 20.0,
            "selling_price": 30.0,
            "expiry_date": "2027-10-25",
            "supplier": "Distributor X",
        }]),
    ], ignore_index=True)

    slow_movers = get_slow_moving_medicines(
        enriched_sales,
        medicines_df=med_with_stagnant,
        inventory_df=inv_with_stagnant,
        days_window=90,
        sales_threshold_units=20,
        as_of_date=REFERENCE_DATE,
    )

    assert len(slow_movers) > 0
    assert "MED-ZERO" in slow_movers["medicine_id"].values

    # Check stagnant classification
    zero_row = slow_movers[slow_movers["medicine_id"] == "MED-ZERO"].iloc[0]
    assert zero_row["units_sold_in_window"] == 0
    assert zero_row["velocity_status"] == "Stagnant (Zero Sales)"
    assert zero_row["current_stock_on_hand"] == 100
    assert zero_row["stock_holding_cost"] == 2000.0


def test_sales_statistics_calculations(enriched_sales):
    """Verify sales distribution and descriptive statistical calculations."""
    stats = calculate_sales_statistics(enriched_sales)

    assert stats["total_transactions"] == len(enriched_sales)
    assert stats["total_revenue"] > 0
    assert stats["total_cogs"] > 0
    assert stats["total_gross_profit"] > 0
    assert stats["total_revenue"] > stats["total_gross_profit"]
    assert stats["avg_transaction_revenue"] > 0
    assert stats["median_transaction_revenue"] > 0
    assert stats["std_transaction_revenue"] >= 0
    assert stats["avg_units_per_sale"] > 0
    assert stats["overall_gross_margin_pct"] > 0


def test_estimate_demand_trends_and_disclaimer(enriched_sales):
    """Verify moving averages, trend direction, and mandatory analytical disclaimer."""
    trends = estimate_demand_trends(enriched_sales, forecast_days=30)

    assert "daily_history" in trends
    assert len(trends["daily_history"]) > 0
    assert "rolling_7d_revenue" in trends["daily_history"].columns
    assert trends["avg_daily_revenue"] > 0
    assert trends["projected_period_revenue"] > 0
    assert trends["trend_direction"] in ("Upward", "Downward", "Stable")

    # Verify explicit disclaimer is provided
    assert "disclaimer" in trends
    assert DEMAND_ESTIMATE_DISCLAIMER in trends["disclaimer"]
    assert "clinical forecasts" in trends["disclaimer"]


def test_empty_datasets_safety():
    """Verify functions handle empty datasets gracefully without raising exceptions."""
    empty_sal = pd.DataFrame(columns=["sale_id", "date", "batch_id", "quantity_sold", "unit_price"])
    empty_inv = pd.DataFrame(columns=["batch_id", "medicine_id", "quantity", "purchase_price", "selling_price", "expiry_date", "supplier"])
    empty_med = pd.DataFrame(columns=["medicine_id", "medicine_name", "category", "reorder_level"])

    enriched = prepare_enriched_sales(empty_sal, empty_inv, empty_med)
    assert enriched.empty

    periodic = get_periodic_sales_summary(enriched)
    assert periodic.empty

    dim = get_sales_by_dimension(enriched)
    assert dim.empty

    top = get_top_selling_medicines(enriched)
    assert top.empty

    stats = calculate_sales_statistics(enriched)
    assert stats["total_transactions"] == 0
    assert stats["total_revenue"] == 0.0

    trends = estimate_demand_trends(enriched)
    assert trends["avg_daily_revenue"] == 0.0
    assert "disclaimer" in trends


def test_export_analytics_summary(enriched_sales, tmp_path):
    """Verify exporting analytical summaries to CSV."""
    by_category = get_sales_by_dimension(enriched_sales, dimension="category")
    export_path = export_analytics_summary(by_category, "test_category_sales.csv", export_dir=tmp_path)

    assert export_path.exists()
    assert export_path.stat().st_size > 0

    read_back = pd.read_csv(export_path)
    assert len(read_back) == len(by_category)
    assert "gross_margin_pct" in read_back.columns
