"""
Comprehensive End-to-End Integration Tests for PharmaTrack.

Tests the full lifecycle:
1. Ingestion, Validation & Cleaning
2. Inventory Aggregation & Valuation
3. Sales Enrichment, COGS & Margin Analytics
4. Expiry Classification, FEFO Sequencing & Exposure Risk
5. Visualization Generation (Matplotlib & Seaborn figures)
6. Export of all audit reports with schema verification
7. Error robustness on malformed CSVs, missing files, broken keys, empty datasets
"""

import os
import shutil
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
import matplotlib.figure

from src.data.generator import generate_synthetic_datasets
from src.data.validator import validate_all_datasets
from src.data.loader import ingest_and_validate_data, load_raw_csv_files, get_unified_sales_data
from src.inventory.service import (
    get_batch_inventory_summary,
    get_medicine_inventory_summary,
    get_low_stock_alerts,
    calculate_replenishment_suggestions,
    calculate_inventory_valuation_metrics,
    export_inventory_report,
)
from src.analytics.service import (
    prepare_enriched_sales,
    get_periodic_sales_summary,
    get_sales_by_dimension,
    get_top_selling_medicines,
    get_slow_moving_medicines,
    calculate_sales_statistics,
    estimate_demand_trends,
    export_analytics_summary,
)
from src.expiry.service import (
    classify_batch_expiry,
    calculate_expiry_exposure_metrics,
    get_high_value_near_expiry_batches,
    get_fefo_stock_rotation_queue,
    analyze_recorded_wastage,
    export_expiry_report,
)
from src.visualization.charts import (
    plot_revenue_time_series,
    plot_top_selling_medicines,
    plot_category_revenue_profit_comparison,
    plot_expiry_risk_distribution,
    plot_transaction_basket_distribution,
    plot_sales_correlation_heatmap,
    plot_stock_levels_vs_reorder,
)


@pytest.fixture
def temp_workspace():
    """Creates a temporary workspace with reproducible datasets."""
    temp_dir = tempfile.mkdtemp()
    raw_dir = Path(temp_dir) / "raw"
    reports_dir = Path(temp_dir) / "reports"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    data_dict = generate_synthetic_datasets(seed=42, output_dir=raw_dir, save_to_disk=True)
    yield {
        "root": temp_dir,
        "raw_dir": raw_dir,
        "reports_dir": reports_dir,
        "med_df": data_dict["medicines"],
        "inv_df": data_dict["inventory"],
        "sales_df": data_dict["sales"],
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_complete_end_to_end_workflow(temp_workspace):
    """
    Validates complete data flow across ingestion, inventory, sales,
    expiry, charts, and report exports.
    """
    raw_dir = temp_workspace["raw_dir"]
    reports_dir = temp_workspace["reports_dir"]

    # 1. Ingestion & Validation
    datasets, report = ingest_and_validate_data(data_dir=raw_dir, export_processed=False)
    assert report.is_valid is True
    assert len(report.errors) == 0

    med_df = datasets["medicines"]
    inv_df = datasets["inventory"]
    sales_df = datasets["sales"]

    # 2. Inventory Management
    ref_date = pd.to_datetime("2026-10-25")
    batch_inv = get_batch_inventory_summary(inv_df, med_df)
    med_inv = get_medicine_inventory_summary(inv_df, med_df, as_of_date=ref_date)
    low_stock = get_low_stock_alerts(med_inv)
    replenish = calculate_replenishment_suggestions(med_inv, sales_df)
    inv_val = calculate_inventory_valuation_metrics(inv_df, as_of_date=ref_date)

    assert "usable_quantity" in med_inv.columns
    assert "reorder_level" in med_inv.columns
    assert "suggested_reorder_qty" in replenish.columns
    assert inv_val["total_batches_tracked"] > 0
    assert inv_val["usable_purchase_valuation"] <= inv_val["total_purchase_valuation"]

    # 3. Sales Analytics
    enriched_sales = prepare_enriched_sales(sales_df, inv_df, med_df)
    daily_sales = get_periodic_sales_summary(enriched_sales, freq="D")
    cat_sales = get_sales_by_dimension(enriched_sales, dimension="category")
    top_sellers = get_top_selling_medicines(enriched_sales, top_n=5)
    slow_movers = get_slow_moving_medicines(enriched_sales, med_df, inv_df)
    stats = calculate_sales_statistics(enriched_sales)
    trends = estimate_demand_trends(enriched_sales, forecast_days=30)

    assert "gross_profit" in enriched_sales.columns
    assert "margin_pct" in enriched_sales.columns
    assert stats["total_transactions"] == len(enriched_sales)
    assert "disclaimer" in trends

    # 4. Expiry & FEFO Risk
    classified_expiry = classify_batch_expiry(inv_df, med_df, as_of_date=ref_date, near_expiry_days=30)
    exposure = calculate_expiry_exposure_metrics(inv_df, near_expiry_days=30, as_of_date=ref_date)
    high_value_risk = get_high_value_near_expiry_batches(inv_df, med_df, min_value_threshold=100.0, as_of_date=ref_date)
    fefo_queue = get_fefo_stock_rotation_queue(inv_df, med_df, as_of_date=ref_date)
    wastage_res = analyze_recorded_wastage(inv_df)

    assert "expiry_classification" in classified_expiry.columns
    assert "fefo_dispense_priority" in fefo_queue.columns
    assert exposure["near_expiry_purchase_value_at_risk"] >= 0.0

    # 5. Visualizations
    fig1 = plot_revenue_time_series(daily_sales)
    fig2 = plot_top_selling_medicines(top_sellers, metric="revenue")
    fig3 = plot_category_revenue_profit_comparison(cat_sales)
    fig4 = plot_expiry_risk_distribution(classified_expiry)
    fig5 = plot_transaction_basket_distribution(enriched_sales)
    fig6 = plot_sales_correlation_heatmap(enriched_sales)
    fig7 = plot_stock_levels_vs_reorder(med_inv)

    for fig in [fig1, fig2, fig3, fig4, fig5, fig6, fig7]:
        assert isinstance(fig, matplotlib.figure.Figure)
        matplotlib.pyplot.close(fig)

    # 6. Report Exports
    inv_path = export_inventory_report(med_inv, "test_inv.csv", export_dir=reports_dir)
    sales_path = export_analytics_summary(daily_sales, "test_sales.csv", export_dir=reports_dir)
    expiry_path = export_expiry_report(classified_expiry, "test_expiry.csv", export_dir=reports_dir)

    assert os.path.exists(inv_path)
    assert os.path.exists(sales_path)
    assert os.path.exists(expiry_path)

    # Verify CSV content
    exported_inv = pd.read_csv(inv_path)
    assert "medicine_id" in exported_inv.columns
    assert "usable_quantity" in exported_inv.columns

    exported_sales = pd.read_csv(sales_path)
    assert "period" in exported_sales.columns
    assert "total_revenue" in exported_sales.columns

    exported_expiry = pd.read_csv(expiry_path)
    assert "batch_id" in exported_expiry.columns
    assert "expiry_classification" in exported_expiry.columns


def test_error_handling_malformed_and_missing_data(temp_workspace):
    """
    Verifies that missing files, malformed schemas, and invalid values
    produce actionable, understandable errors rather than unhandled crashes.
    """
    root = temp_workspace["root"]
    bad_dir = Path(root) / "bad_data"
    bad_dir.mkdir(parents=True, exist_ok=True)

    # 1. Missing files
    with pytest.raises(FileNotFoundError, match="Required dataset"):
        load_raw_csv_files(data_dir=bad_dir)

    # 2. Malformed CSV missing mandatory column
    bad_med = pd.DataFrame({
        "medicine_id": ["MED-01"],
        # Missing medicine_name, category, reorder_level
    })
    bad_med.to_csv(bad_dir / "medicines.csv", index=False)
    pd.DataFrame({"batch_id": [], "medicine_id": [], "quantity": [], "purchase_price": [], "selling_price": [], "expiry_date": [], "supplier": []}).to_csv(bad_dir / "inventory.csv", index=False)
    pd.DataFrame({"sale_id": [], "date": [], "batch_id": [], "quantity_sold": [], "unit_price": []}).to_csv(bad_dir / "sales.csv", index=False)

    datasets, report = ingest_and_validate_data(data_dir=bad_dir, export_processed=False)
    assert report.is_valid is False
    assert any("Missing required column" in err for err in report.errors)

    # 3. Inconsistent IDs / Broken Foreign Keys
    bad_dir2 = Path(root) / "broken_fk"
    bad_dir2.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "medicine_id": ["MED-01"],
        "medicine_name": ["Paracetamol"],
        "category": ["Analgesics"],
        "reorder_level": [50]
    }).to_csv(bad_dir2 / "medicines.csv", index=False)

    pd.DataFrame({
        "batch_id": ["BAT-01"],
        "medicine_id": ["MED-999"],  # Nonexistent
        "quantity": [100],
        "purchase_price": [10.0],
        "selling_price": [15.0],
        "expiry_date": ["2027-01-01"],
        "supplier": ["PharmaCorp"]
    }).to_csv(bad_dir2 / "inventory.csv", index=False)

    pd.DataFrame({
        "sale_id": ["SAL-01"],
        "date": ["2026-10-01"],
        "batch_id": ["BAT-999"],  # Nonexistent
        "quantity_sold": [10],
        "unit_price": [15.0]
    }).to_csv(bad_dir2 / "sales.csv", index=False)

    datasets2, report2 = ingest_and_validate_data(data_dir=bad_dir2, export_processed=False)
    assert report2.is_valid is False
    assert any("med-999" in err.lower() for err in report2.errors)
    assert any("bat-999" in err.lower() for err in report2.errors)


def test_empty_datasets_visualization_and_analytics_safety():
    """
    Verifies that completely empty datasets do not crash analytics or visualization routines.
    """
    empty_sales = pd.DataFrame(columns=["sale_id", "date", "batch_id", "quantity_sold", "unit_price", "purchase_price", "total_revenue", "total_cogs", "gross_profit", "profit_margin_pct", "medicine_name", "category"])
    empty_med = pd.DataFrame(columns=["medicine_id", "medicine_name", "category", "reorder_level", "usable_stock"])

    stats = calculate_sales_statistics(empty_sales)
    assert stats["total_transactions"] == 0
    assert stats["total_revenue"] == 0.0

    fig_rev = plot_revenue_time_series(empty_sales)
    assert isinstance(fig_rev, matplotlib.figure.Figure)
    matplotlib.pyplot.close(fig_rev)

    fig_corr = plot_sales_correlation_heatmap(empty_sales)
    assert isinstance(fig_corr, matplotlib.figure.Figure)
    matplotlib.pyplot.close(fig_corr)

    fig_stock = plot_stock_levels_vs_reorder(empty_med)
    assert isinstance(fig_stock, matplotlib.figure.Figure)
    matplotlib.pyplot.close(fig_stock)
