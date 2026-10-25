"""PharmaTrack — Clinical Pharmacy Management & Analytics System.

Main Application Entry Point: Overview Dashboard.
"""

from datetime import datetime
import pandas as pd
import streamlit as st

import config
from src.analytics import (
    calculate_sales_statistics,
    get_periodic_sales_summary,
    get_sales_by_dimension,
    prepare_enriched_sales,
)
from src.expiry import (
    calculate_expiry_exposure_metrics,
    classify_batch_expiry,
)
from src.inventory import (
    calculate_inventory_valuation_metrics,
    get_low_stock_alerts,
    get_medicine_inventory_summary,
)
from src.visualization.charts import (
    plot_category_sales_bar,
    plot_monthly_revenue_line,
)
from src.visualization.state import render_sidebar_data_loader
from src.visualization.theme import (
    inject_clinical_styles,
    render_kpi_grid,
    render_page_header,
    render_sidebar_brand,
)

# Page configuration
st.set_page_config(
    page_title="Overview | PharmaTrack",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Render the primary clinical overview dashboard."""
    # Inject unified clinical CSS styles
    inject_clinical_styles()

    # Sidebar branding and unified data loader
    render_sidebar_brand(reference_date=config.REFERENCE_DATE)
    dfs, data_source_label = render_sidebar_data_loader()

    with st.sidebar:
        st.markdown("---")
        st.caption(f"System Reference: {config.REFERENCE_DATE}")
        st.caption("PharmaTrack Enterprise v1.1.0")

    # Shell Header with title, subtitle, and right-aligned reference date (No decorative badge)
    render_page_header(
        title="Overview",
        subtitle="Monitor inventory health, sales performance, and expiry risk.",
        right_label=f"Reference Date: {config.REFERENCE_DATE}",
    )

    # Ingest datasets
    med_df = dfs["medicines"]
    inv_df = dfs["inventory"]
    sal_df = dfs["sales"]

    # Compute operational metrics
    enriched_sales = prepare_enriched_sales(sal_df, inv_df, med_df)
    inv_metrics = calculate_inventory_valuation_metrics(inv_df, as_of_date=config.REFERENCE_DATE)
    sales_stats = calculate_sales_statistics(enriched_sales)
    med_summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date=config.REFERENCE_DATE)
    low_stock_alerts = get_low_stock_alerts(med_summary, threshold_factor=1.0)
    expiry_metrics = calculate_expiry_exposure_metrics(inv_df, near_expiry_days=30, as_of_date=config.REFERENCE_DATE)

    # Calculate today's sales (as of reference date)
    ref_dt = pd.to_datetime(config.REFERENCE_DATE)
    today_txns = enriched_sales[enriched_sales["date"] == ref_dt] if not enriched_sales.empty else pd.DataFrame()
    if not today_txns.empty:
        today_rev = today_txns["total_revenue"].sum()
        today_units = int(today_txns["quantity_sold"].sum())
        today_sub = f"{today_units} units dispensed ({len(today_txns)} transactions)"
        today_val = f"${today_rev:,.2f}"
    else:
        daily_summary = get_periodic_sales_summary(enriched_sales, freq="D")
        latest_day = daily_summary.iloc[-1] if not daily_summary.empty else None
        if latest_day is not None:
            today_val = f"${latest_day['total_revenue']:,.2f}"
            today_sub = f"Latest day: {latest_day['period']} ({int(latest_day['total_units_sold'])} units)"
        else:
            today_val = "$0.00"
            today_sub = "No transactions recorded"

    # -------------------------------------------------------------------------
    # 1. Primary Operational KPI Section (4 aligned cards)
    # -------------------------------------------------------------------------
    kpi_cards = [
        {
            "label": "Total Medicines",
            "value": f"{len(med_df):,}",
            "subtext": f"{inv_metrics['total_physical_stock_units']:,} total physical units",
            "status": "normal",
        },
        {
            "label": "Low Stock Items",
            "value": f"{len(low_stock_alerts)}",
            "subtext": "Requires replenishment" if len(low_stock_alerts) > 0 else "All stock levels optimal",
            "status": "warning" if len(low_stock_alerts) > 0 else "success",
        },
        {
            "label": "Expiring Soon",
            "value": f"{expiry_metrics['near_expiry_batches_count']} Batches",
            "subtext": f"${expiry_metrics['near_expiry_purchase_value_at_risk']:,.2f} cost exposure (≤30d)",
            "status": "critical" if expiry_metrics['near_expiry_batches_count'] > 0 else "success",
        },
        {
            "label": "Today's Sales",
            "value": today_val,
            "subtext": today_sub,
            "status": "normal",
        },
    ]
    render_kpi_grid(kpi_cards, is_financial=False)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 2. Financial Overview Section (4 compact cards)
    # -------------------------------------------------------------------------
    st.markdown("<div class='pt-section-title' style='margin-top: 6px;'>Financial Overview</div>", unsafe_allow_html=True)
    financial_cards = [
        {
            "label": "Gross Sales Revenue",
            "value": f"${sales_stats['total_revenue']:,.2f}",
            "subtext": f"{sales_stats['total_transactions']:,} total sales transactions",
            "status": "normal",
        },
        {
            "label": "Gross Profit",
            "value": f"${sales_stats['total_gross_profit']:,.2f}",
            "subtext": f"{sales_stats['overall_gross_margin_pct']}% Gross margin (COGS deducted)",
            "status": "success",
        },
        {
            "label": "Usable Inventory Value",
            "value": f"${inv_metrics['usable_purchase_valuation']:,.2f}",
            "subtext": "Saleable stock excluding expired units",
            "status": "normal",
        },
        {
            "label": "Expired Stock Exposure",
            "value": f"${inv_metrics['expired_stock_loss_exposure']:,.2f}",
            "subtext": f"{inv_metrics['expired_stock_units']} units quarantined (estimated)",
            "status": "critical" if inv_metrics['expired_stock_loss_exposure'] > 0 else "success",
        },
    ]
    render_kpi_grid(financial_cards, is_financial=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 3. Two-Column Balanced Charts: Monthly Revenue & Category Sales
    # -------------------------------------------------------------------------
    st.markdown("<div class='pt-section-title'>Revenue and Category Performance</div>", unsafe_allow_html=True)
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        monthly_sales = get_periodic_sales_summary(enriched_sales, freq="M")
        fig_revenue = plot_monthly_revenue_line(
            monthly_sales,
            title="Revenue and Gross Profit Trend ($ USD)",
        )
        st.pyplot(fig_revenue, use_container_width=True)

    with chart_col2:
        category_sales = get_sales_by_dimension(enriched_sales, dimension="category")
        fig_category = plot_category_sales_bar(
            category_sales,
            title="Sales by Therapeutic Category ($ USD)",
        )
        st.pyplot(fig_category, use_container_width=True)

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 4. Compact Aligned Operational Tables: Low Stock Alerts & Upcoming Expiries
    # -------------------------------------------------------------------------
    table_col1, table_col2 = st.columns(2)

    with table_col1:
        st.markdown("<div class='pt-table-header'>Low Stock Alerts</div>", unsafe_allow_html=True)
        if not low_stock_alerts.empty:
            display_low = low_stock_alerts[[
                "medicine_name",
                "category",
                "usable_quantity",
                "reorder_level",
                "stock_status",
            ]].copy()
            display_low.rename(columns={
                "medicine_name": "Medicine",
                "category": "Category",
                "usable_quantity": "Usable Units",
                "reorder_level": "Reorder Level",
                "stock_status": "Status",
            }, inplace=True)
            st.dataframe(display_low, use_container_width=True, hide_index=True, height=240)
        else:
            st.info("All catalogued medicines currently meet safety reorder levels.")

    with table_col2:
        st.markdown("<div class='pt-table-header'>Upcoming Expiries (≤30 Days)</div>", unsafe_allow_html=True)
        classified_batches = classify_batch_expiry(inv_df, near_expiry_days=30, as_of_date=config.REFERENCE_DATE)
        near_batches = classified_batches[classified_batches["is_near_expiry"]].copy()

        if not near_batches.empty:
            display_near = near_batches[[
                "batch_id",
                "medicine_name",
                "quantity",
                "expiry_date",
                "days_remaining",
                "value_at_risk",
            ]].sort_values("days_remaining").copy()

            display_near["expiry_date"] = pd.to_datetime(display_near["expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(display_near["expiry_date"].astype(str))
            display_near["value_at_risk"] = display_near["value_at_risk"].apply(lambda v: f"${float(v):,.2f}")

            display_near.rename(columns={
                "batch_id": "Batch ID",
                "medicine_name": "Medicine",
                "quantity": "Units",
                "expiry_date": "Expiry Date",
                "days_remaining": "Days Left",
                "value_at_risk": "Cost at Risk",
            }, inplace=True)
            st.dataframe(display_near, use_container_width=True, hide_index=True, height=240)
        else:
            st.info("No batches are expiring within the next 30 days.")


if __name__ == "__main__":
    main()
