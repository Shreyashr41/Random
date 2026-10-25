"""PharmaTrack — Analytical Reports & Data Exports Page."""

import pandas as pd
import streamlit as st

import config
from src.analytics import (
    get_periodic_sales_summary,
    prepare_enriched_sales,
)
from src.expiry import (
    classify_batch_expiry,
    get_fefo_stock_rotation_queue,
)
from src.inventory import (
    calculate_replenishment_suggestions,
    get_batch_inventory_summary,
    get_low_stock_alerts,
    get_medicine_inventory_summary,
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
    page_title="Reports | PharmaTrack",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject clinical styles
inject_clinical_styles()

# Sidebar
render_sidebar_brand(reference_date=config.REFERENCE_DATE)
dfs, _ = render_sidebar_data_loader()
med_df = dfs["medicines"]
inv_df = dfs["inventory"]
sal_df = dfs["sales"]

as_of = config.REFERENCE_DATE

# Header
render_page_header(
    title="Reports",
    subtitle="Generate and export standardized inventory, sales, expiry risk, and replenishment datasets.",
)

# Precompute analytical datasets
enriched_sales = prepare_enriched_sales(sal_df, inv_df, med_df)
sales_with_med = pd.merge(sal_df, inv_df[["batch_id", "medicine_id"]], on="batch_id", how="left")

medicine_summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date=as_of)
batch_summary = get_batch_inventory_summary(inv_df, med_df, as_of_date=as_of)
low_stock_alerts = get_low_stock_alerts(medicine_summary, threshold_factor=1.0)
classified_expiry = classify_batch_expiry(inv_df, medicines_df=med_df, as_of_date=as_of)
fefo_queue = get_fefo_stock_rotation_queue(inv_df, medicines_df=med_df, as_of_date=as_of)
replenish_df = calculate_replenishment_suggestions(medicine_summary, sales_df=sales_with_med)
daily_sales = get_periodic_sales_summary(enriched_sales, freq="D")
monthly_sales = get_periodic_sales_summary(enriched_sales, freq="M")

# Overview KPIs
rep_kpis = [
    {
        "label": "Available Reports",
        "value": "4 Core Modules",
        "subtext": "RFC 4180 standard CSV exports",
        "status": "normal",
    },
    {
        "label": "Inventory Batches Audited",
        "value": f"{len(batch_summary)} Batches",
        "subtext": f"{len(medicine_summary)} active medicine SKUs",
        "status": "normal",
    },
    {
        "label": "Expiry Risk Batches",
        "value": f"{len(classified_expiry[classified_expiry['is_near_expiry']])} Batches",
        "subtext": "Expiring within warning window",
        "status": "warning" if len(classified_expiry[classified_expiry['is_near_expiry']]) > 0 else "success",
    },
    {
        "label": "Replenishment Alerts",
        "value": f"{len(low_stock_alerts)} SKUs",
        "subtext": "Require stock replenishment",
        "status": "warning" if len(low_stock_alerts) > 0 else "success",
    },
]
render_kpi_grid(rep_kpis)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Report Selection & Configuration
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title'>Standardized Report Selector</div>", unsafe_allow_html=True)

report_categories = [
    "Inventory Report — Medicine Inventory & Valuation",
    "Inventory Report — Batch-Level Audit Log",
    "Sales Report — Detailed Transaction Ledger",
    "Sales Report — Monthly Financial Performance",
    "Expiry-Risk Report — Batch Shelf-Life Classification",
    "Expiry-Risk Report — FEFO Stock Rotation Queue",
    "Replenishment Report — Demand & Safety Stock Plan",
    "Replenishment Report — Low Stock Action Items",
]

col_sel, col_cat = st.columns([2.5, 1.5])
with col_sel:
    selected_report_name = st.selectbox("Select Report to Export:", report_categories)

# Determine underlying base DataFrame and export metadata
if "Medicine Inventory & Valuation" in selected_report_name:
    base_df = medicine_summary.copy()
    default_filename = "pharmatrack_inventory_valuation_report.csv"
    report_desc = "Catalogue-level inventory metrics, usable physical units vs expired quarantine stock, and total purchase valuations."
elif "Batch-Level Audit Log" in selected_report_name:
    base_df = batch_summary.copy()
    default_filename = "pharmatrack_batch_inventory_audit.csv"
    report_desc = "Discrete batch records with lot numbers, purchase prices, selling prices, expiry dates, and supplier designations."
elif "Detailed Transaction Ledger" in selected_report_name:
    base_df = enriched_sales.copy()
    default_filename = "pharmatrack_sales_transaction_ledger.csv"
    report_desc = "Individual sales transactions with medicine name, category, batch COGS, sale revenue, and gross profit."
elif "Monthly Financial Performance" in selected_report_name:
    base_df = monthly_sales.copy()
    default_filename = "pharmatrack_monthly_sales_summary.csv"
    report_desc = "Monthly financial aggregates, revenue, cost of goods sold, gross profit margins, and transaction volumes."
elif "Batch Shelf-Life Classification" in selected_report_name:
    base_df = classified_expiry.copy()
    default_filename = "pharmatrack_expiry_risk_report.csv"
    report_desc = "Batch classification by remaining shelf-life, near-expiry flags, and financial acquisition value at risk."
elif "FEFO Stock Rotation Queue" in selected_report_name:
    base_df = fefo_queue.copy()
    default_filename = "pharmatrack_fefo_dispensing_queue.csv"
    report_desc = "Strict First-Expiry-First-Out dispensing priorities ensuring earliest-expiring stock is dispensed first."
elif "Demand & Safety Stock Plan" in selected_report_name:
    base_df = replenish_df.copy()
    default_filename = "pharmatrack_replenishment_report.csv"
    report_desc = "Statistical consumption velocity (ADC), lead-time buffer requirements, and suggested reorder quantities."
else:  # Low Stock Action Items
    base_df = low_stock_alerts.copy()
    default_filename = "pharmatrack_low_stock_report.csv"
    report_desc = "Catalogued medicines where usable inventory has reached or breached the safety reorder threshold."

# Category filter if category column exists
with col_cat:
    if "category" in base_df.columns:
        cat_options = ["All Categories"] + sorted(base_df["category"].dropna().unique().tolist())
        selected_category = st.selectbox("Filter Category:", cat_options)
        if selected_category != "All Categories":
            current_df = base_df[base_df["category"] == selected_category].copy()
        else:
            current_df = base_df.copy()
    else:
        st.write("")
        st.caption("No category filtering applicable for this dataset.")
        current_df = base_df.copy()

st.caption(f"**Report Scope:** {report_desc}")

# -----------------------------------------------------------------------------
# Export Action Toolbar
# -----------------------------------------------------------------------------
exp_col1, exp_col2, exp_col3 = st.columns([2, 1.5, 1])

with exp_col1:
    st.markdown(
        f"<div style='font-size: 13px; color: #667085; padding-top: 6px;'>"
        f"Records: <strong>{len(current_df):,}</strong> rows &nbsp;|&nbsp; "
        f"Columns: <strong>{len(current_df.columns)}</strong> attributes"
        f"</div>",
        unsafe_allow_html=True,
    )

with exp_col2:
    if not current_df.empty:
        csv_bytes = current_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV Report",
            data=csv_bytes,
            file_name=default_filename,
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.button("Download CSV Report", disabled=True, use_container_width=True)

with exp_col3:
    st.markdown(
        "<div style='font-size: 12px; color: #667085; padding-top: 8px;'>Format: RFC 4180 CSV</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Data Preview
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-table-header'>Data Preview</div>", unsafe_allow_html=True)
if not current_df.empty:
    display_df = current_df.copy()
    # Format date columns cleanly if present
    for col in display_df.columns:
        if "date" in col.lower():
            display_df[col] = pd.to_datetime(display_df[col], errors="coerce").dt.strftime("%Y-%m-%d").fillna(display_df[col].astype(str))

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=440)
    st.caption(f"Showing dataset with {len(display_df)} total records.")
else:
    st.info("The selected report currently contains no records based on active filter criteria.")
