"""Automated test suite for Phase 5: Statistical charts, visualizations, and dashboard pages."""

import ast
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from config import BASE_DIR
from src.data import clean_and_type_coerce, generate_synthetic_datasets
from src.analytics import get_periodic_sales_summary, get_sales_by_dimension, get_top_selling_medicines, prepare_enriched_sales
from src.expiry import classify_batch_expiry
from src.inventory import get_medicine_inventory_summary
from src.visualization import (
    plot_category_revenue_profit_comparison,
    plot_expiry_risk_distribution,
    plot_revenue_time_series,
    plot_sales_correlation_heatmap,
    plot_stock_levels_vs_reorder,
    plot_top_selling_medicines,
    plot_transaction_basket_distribution,
)


@pytest.fixture
def chart_data():
    """Load sample data frames for visualization testing."""
    datasets = generate_synthetic_datasets(seed=42, save_to_disk=False)
    med, inv, sal = clean_and_type_coerce(
        datasets["medicines"],
        datasets["inventory"],
        datasets["sales"],
    )
    enriched = prepare_enriched_sales(sal, inv, med)
    med_summary = get_medicine_inventory_summary(inv, med, as_of_date="2026-10-25")
    classified_expiry = classify_batch_expiry(inv, medicines_df=med, as_of_date="2026-10-25")
    daily_sales = get_periodic_sales_summary(enriched, freq="D")
    cat_sales = get_sales_by_dimension(enriched, dimension="category")
    top_meds = get_top_selling_medicines(enriched, top_n=10)

    return {
        "enriched": enriched,
        "med_summary": med_summary,
        "classified_expiry": classified_expiry,
        "daily_sales": daily_sales,
        "cat_sales": cat_sales,
        "top_meds": top_meds,
    }


def test_plot_revenue_time_series(chart_data):
    """Verify time series chart generation and empty dataframe handling."""
    fig = plot_revenue_time_series(chart_data["daily_sales"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    # Empty dataframe should return placeholder without raising errors
    empty_fig = plot_revenue_time_series(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_plot_top_selling_medicines(chart_data):
    """Verify top selling medicines bar chart."""
    fig = plot_top_selling_medicines(chart_data["top_meds"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    empty_fig = plot_top_selling_medicines(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_plot_category_comparison(chart_data):
    """Verify category revenue and profit comparison chart."""
    fig = plot_category_revenue_profit_comparison(chart_data["cat_sales"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    empty_fig = plot_category_revenue_profit_comparison(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_plot_expiry_risk_distribution(chart_data):
    """Verify expiry risk bar chart."""
    fig = plot_expiry_risk_distribution(chart_data["classified_expiry"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    empty_fig = plot_expiry_risk_distribution(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_plot_transaction_basket_distribution(chart_data):
    """Verify Seaborn box plot generation."""
    fig = plot_transaction_basket_distribution(chart_data["enriched"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    empty_fig = plot_transaction_basket_distribution(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_plot_sales_correlation_heatmap(chart_data):
    """Verify Seaborn correlation heatmap and safety when columns are insufficient."""
    fig = plot_sales_correlation_heatmap(chart_data["enriched"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    # Insufficient rows or columns should return a clean placeholder
    sparse_df = pd.DataFrame({"colA": [1, 2]})
    sparse_fig = plot_sales_correlation_heatmap(sparse_df)
    assert isinstance(sparse_fig, plt.Figure)
    plt.close(sparse_fig)


def test_plot_stock_levels_vs_reorder(chart_data):
    """Verify stock vs reorder level comparison chart."""
    fig = plot_stock_levels_vs_reorder(chart_data["med_summary"])
    assert isinstance(fig, plt.Figure)
    assert len(fig.axes) > 0
    plt.close(fig)

    empty_fig = plot_stock_levels_vs_reorder(pd.DataFrame())
    assert isinstance(empty_fig, plt.Figure)
    plt.close(empty_fig)


def test_all_pages_valid_python_syntax():
    """Verify all dashboard pages compile and contain valid Python syntax."""
    pages_dir = BASE_DIR / "pages"
    assert pages_dir.exists()
    page_files = list(pages_dir.glob("*.py"))
    assert len(page_files) >= 5, "Expected at least 5 page modules in pages/"

    for page_path in page_files:
        with open(page_path, "r", encoding="utf-8") as f:
            code = f.read()
            ast.parse(code, filename=page_path.name)
