"""PharmaTrack — Demand Analysis & Replenishment Planning Page."""

import pandas as pd
import streamlit as st

import config
from src.inventory import (
    calculate_replenishment_suggestions,
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
    page_title="Replenishment | PharmaTrack",
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
medicine_summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date=as_of)

# Map batch_id to medicine_id on sales for demand calculations
sales_with_med = pd.merge(sal_df, inv_df[["batch_id", "medicine_id"]], on="batch_id", how="left")

# Header
render_page_header(
    title="Replenishment",
    subtitle="Manage stock replenishment, lead-time buffers, and purchase heuristics.",
)

# -----------------------------------------------------------------------------
# 1. Configuration Controls
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title'>Replenishment Parameters</div>", unsafe_allow_html=True)
param_col1, param_col2, param_col3 = st.columns(3)

with param_col1:
    lead_time = st.number_input(
        "Supplier Lead Time (Days):",
        min_value=1,
        max_value=30,
        value=config.ReplenishmentConfig.DEFAULT_LEAD_TIME_DAYS,
        step=1,
        help="Average elapsed days between purchase order placement and receipt.",
    )

with param_col2:
    safety_stock_factor = st.slider(
        "Safety Stock Multiplier:",
        min_value=1.0,
        max_value=3.0,
        value=config.ReplenishmentConfig.SAFETY_STOCK_FACTOR,
        step=0.25,
        help="Multiplier applied to lead-time demand to buffer against unexpected demand surges.",
    )

with param_col3:
    review_window = st.number_input(
        "Sales Velocity Lookback (Days):",
        min_value=7,
        max_value=180,
        value=config.ReplenishmentConfig.DEFAULT_REVIEW_PERIOD_DAYS,
        step=7,
        help="Historical transaction window used to calculate Average Daily Consumption (ADC).",
    )

# Calculate Replenishment Suggestions
suggestions = calculate_replenishment_suggestions(
    medicine_summary_df=medicine_summary,
    sales_df=sales_with_med,
    lead_time_days=int(lead_time),
    safety_factor=float(safety_stock_factor),
    review_period_days=int(review_window),
)

# Map supplier from batch inventory if available
if not inv_df.empty and "supplier" in inv_df.columns:
    med_suppliers = inv_df.groupby("medicine_id")["supplier"].agg(
        lambda s: s.mode().iloc[0] if not s.empty and not s.mode().empty else (s.iloc[0] if not s.empty else "N/A")
    ).to_dict()
    suggestions["supplier"] = suggestions["medicine_id"].map(med_suppliers).fillna("N/A")
else:
    suggestions["supplier"] = "N/A"

reorder_needed = suggestions[suggestions["suggested_reorder_qty"] > 0]
total_reorder_units = int(suggestions["suggested_reorder_qty"].sum())

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Metric Summary
# -----------------------------------------------------------------------------
rep_kpis = [
    {
        "label": "Catalogued Medicines",
        "value": f"{len(suggestions):,} SKUs",
        "subtext": "Active catalogue under monitoring",
        "status": "normal",
    },
    {
        "label": "Medicines Needing Reorder",
        "value": f"{len(reorder_needed):,} Medicines",
        "subtext": "Usable stock below threshold" if len(reorder_needed) > 0 else "Fully stocked",
        "status": "warning" if len(reorder_needed) > 0 else "success",
    },
    {
        "label": "Suggested Reorder Volume",
        "value": f"{total_reorder_units:,} Units",
        "subtext": "Sum of recommended replenishment orders",
        "status": "normal",
    },
]
render_kpi_grid(rep_kpis)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
st.caption(
    "Advisory Notice: Suggested reorder quantities are statistical heuristics derived from historical consumption. "
    "All quantities should be verified against clinical dispensing schedules before generating supplier purchase orders. "
    "Expired batches are strictly excluded from usable inventory totals."
)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. Detailed Suggestions Table
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title'>Replenishment Recommendations</div>", unsafe_allow_html=True)
h_col1, h_col2, h_col3 = st.columns([2, 2, 1.2])

categories = ["All Categories"] + sorted(suggestions["category"].dropna().unique().tolist())
with h_col1:
    sel_cat = st.selectbox("Filter by Category:", categories)

with h_col2:
    status_filter = st.selectbox(
        "Stock Filter:",
        ["All Medicines", "Only Medicines Needing Reorder"],
        index=0,
    )

filtered_sug = suggestions.copy()
if sel_cat != "All Categories":
    filtered_sug = filtered_sug[filtered_sug["category"] == sel_cat]

if status_filter == "Only Medicines Needing Reorder":
    filtered_sug = filtered_sug[filtered_sug["suggested_reorder_qty"] > 0]

with h_col3:
    st.write("")
    st.write("")
    csv_sug = filtered_sug.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export CSV",
        data=csv_sug,
        file_name="pharmatrack_replenishment_suggestions.csv",
        mime="text/csv",
        use_container_width=True,
    )

display_sug_cols = [
    "medicine_id",
    "medicine_name",
    "category",
    "reorder_level",
    "usable_stock",
    "expired_stock",
    "avg_daily_demand",
    "estimated_runout_days",
    "suggested_reorder_qty",
    "supplier",
    "calculation_method",
    "reorder_urgency",
]

renamed_sug = {
    "medicine_id": "Medicine ID",
    "medicine_name": "Medicine",
    "category": "Category",
    "reorder_level": "Reorder Level",
    "usable_stock": "Usable Units",
    "expired_stock": "Expired Units",
    "avg_daily_demand": "Daily Demand (ADC)",
    "estimated_runout_days": "Runout Days",
    "suggested_reorder_qty": "Suggested Reorder",
    "supplier": "Supplier",
    "calculation_method": "Method",
    "reorder_urgency": "Urgency",
}

if not filtered_sug.empty:
    st.dataframe(
        filtered_sug[display_sug_cols].rename(columns=renamed_sug),
        use_container_width=True,
        hide_index=True,
        height=440,
    )
else:
    st.info("No medicines match the selected replenishment filter criteria.")
