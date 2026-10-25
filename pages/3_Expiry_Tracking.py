"""PharmaTrack — Expiry & Wastage Risk Analysis Page."""

import pandas as pd
import streamlit as st

import config
from src.expiry import (
    EXPOSURE_RISK_DISCLOSURE,
    analyze_recorded_wastage,
    calculate_expiry_exposure_metrics,
    classify_batch_expiry,
    get_fefo_stock_rotation_queue,
)
from src.visualization.charts import plot_expiry_risk_distribution
from src.visualization.state import render_sidebar_data_loader
from src.visualization.theme import (
    inject_clinical_styles,
    render_kpi_grid,
    render_page_header,
    render_sidebar_brand,
)

# Page configuration
st.set_page_config(
    page_title="Expiry Tracking | PharmaTrack",
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

as_of = config.REFERENCE_DATE

# Header
render_page_header(
    title="Expiry Tracking",
    subtitle="Identify at-risk batches and prioritize stock rotation.",
)

# Business logic calculations
classified_batches = classify_batch_expiry(
    inv_df,
    medicines_df=med_df,
    near_expiry_days=30,
    as_of_date=as_of,
)
fefo_queue = get_fefo_stock_rotation_queue(
    inv_df,
    medicines_df=med_df,
    as_of_date=as_of,
)

# Compute specific 7-day and 30-day exposure subsets
expired_subset = classified_batches[classified_batches["days_remaining"] < 0]
expiring_7d_subset = classified_batches[(classified_batches["days_remaining"] >= 0) & (classified_batches["days_remaining"] <= 7)]
expiring_30d_subset = classified_batches[(classified_batches["days_remaining"] >= 0) & (classified_batches["days_remaining"] <= 30)]

total_exposure_val = expiring_30d_subset["value_at_risk"].sum()

# -----------------------------------------------------------------------------
# 1. Summary Metrics (4 cards in one row per specification)
# -----------------------------------------------------------------------------
expiry_kpis = [
    {
        "label": "Expired Batches",
        "value": f"{len(expired_subset)} Batches",
        "subtext": f"{expired_subset['quantity'].sum():,} units quarantined (non-saleable)",
        "status": "critical" if len(expired_subset) > 0 else "success",
    },
    {
        "label": "Expiring Within 7 Days",
        "value": f"{len(expiring_7d_subset)} Batches",
        "subtext": f"{expiring_7d_subset['quantity'].sum():,} units requiring urgent dispensing",
        "status": "warning" if len(expiring_7d_subset) > 0 else "normal",
    },
    {
        "label": "Expiring Within 30 Days",
        "value": f"{len(expiring_30d_subset)} Batches",
        "subtext": f"{expiring_30d_subset['quantity'].sum():,} units in primary risk window",
        "status": "warning" if len(expiring_30d_subset) > 0 else "success",
    },
    {
        "label": "Estimated Purchase-Cost Exposure",
        "value": f"${total_exposure_val:,.2f}",
        "subtext": "Cost of batches expiring within ≤30 days",
        "status": "warning" if total_exposure_val > 0 else "normal",
    },
]
render_kpi_grid(expiry_kpis, is_financial=False)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
st.caption(f"Regulatory Disclosure: {EXPOSURE_RISK_DISCLOSURE}")

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Filters Bar
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title' style='margin-top: 2px;'>Filter At-Risk Batches</div>", unsafe_allow_html=True)
flt_col1, flt_col2, flt_col3, flt_col4 = st.columns(4)

with flt_col1:
    status_choices = ["All Inventory", "Expired Only", "Expiring Within 7 Days", "Expiring Within 30 Days", "Safe Stock"]
    selected_status = st.selectbox("Expiry Status Filter:", status_choices)

with flt_col2:
    all_cats = ["All Categories"] + sorted(classified_batches["category"].dropna().unique().tolist())
    selected_cat = st.selectbox("Medicine Category:", all_cats)

with flt_col3:
    all_supps = ["All Suppliers"] + sorted(classified_batches["supplier"].dropna().unique().tolist())
    selected_supp = st.selectbox("Supplier:", all_supps)

with flt_col4:
    st.write("")
    st.write("")
    st.caption(f"Evaluation Reference: {as_of}")

# Filter data
working_df = classified_batches.copy()

if selected_status == "Expired Only":
    working_df = working_df[working_df["days_remaining"] < 0]
elif selected_status == "Expiring Within 7 Days":
    working_df = working_df[(working_df["days_remaining"] >= 0) & (working_df["days_remaining"] <= 7)]
elif selected_status == "Expiring Within 30 Days":
    working_df = working_df[(working_df["days_remaining"] >= 0) & (working_df["days_remaining"] <= 30)]
elif selected_status == "Safe Stock":
    working_df = working_df[working_df["days_remaining"] > 30]

if selected_cat != "All Categories":
    working_df = working_df[working_df["category"] == selected_cat]

if selected_supp != "All Suppliers":
    working_df = working_df[working_df["supplier"] == selected_supp]

# Sort earliest expiry first
working_df = working_df.sort_values(by="days_remaining", ascending=True)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. Data Presentation Tabs: Batch Table, FEFO Queue, Risk Visuals, Wastage Audit
# -----------------------------------------------------------------------------
exp_tab1, exp_tab2, exp_tab3, exp_tab4 = st.tabs([
    "Batch Expiry Table",
    "FEFO Stock Rotation Queue",
    "Expiry Risk Distribution Chart",
    "Recorded Wastage Audit",
])

with exp_tab1:
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(f"**Showing {len(working_df)} Batch Records (Sorted Earliest Expiry First)**")
    with h_col2:
        csv_near = working_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export Expiry Table (CSV)",
            data=csv_near,
            file_name="pharmatrack_expiry_batches.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Required table columns:
    # Medicine, Batch ID, Available quantity, Expiry date, Days remaining, Estimated cost exposure, Status
    display_df = working_df[[
        "medicine_name",
        "batch_id",
        "quantity",
        "expiry_date",
        "days_remaining",
        "value_at_risk",
        "supplier",
        "expiry_classification",
    ]].copy()

    display_df["expiry_date"] = pd.to_datetime(display_df["expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(display_df["expiry_date"].astype(str))
    display_df["value_at_risk"] = display_df["value_at_risk"].apply(lambda v: f"${float(v):,.2f}")

    display_df.rename(columns={
        "medicine_name": "Medicine",
        "batch_id": "Batch ID",
        "quantity": "Available Quantity",
        "expiry_date": "Expiry Date",
        "days_remaining": "Days Remaining",
        "value_at_risk": "Estimated Cost Exposure",
        "supplier": "Supplier",
        "expiry_classification": "Status",
    }, inplace=True)

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=440)

with exp_tab2:
    st.markdown("##### First-Expiry-First-Out (FEFO) Dispensing Sequence")
    st.caption("Prioritizes batch dispensing sequence by earliest expiration date to minimize shelf-life loss. Expired units are excluded.")

    fefo_display = fefo_queue[[
        "medicine_name",
        "batch_id",
        "quantity",
        "days_remaining",
        "expiry_date",
        "fefo_dispense_priority",
        "fefo_recommendation",
        "supplier",
    ]].copy()

    fefo_display["expiry_date"] = pd.to_datetime(fefo_display["expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(fefo_display["expiry_date"].astype(str))

    fefo_display.rename(columns={
        "medicine_name": "Medicine",
        "batch_id": "Batch ID",
        "quantity": "Available Units",
        "days_remaining": "Days Remaining",
        "expiry_date": "Expiry Date",
        "fefo_dispense_priority": "Priority Order",
        "fefo_recommendation": "FEFO Recommendation",
        "supplier": "Supplier",
    }, inplace=True)

    st.dataframe(fefo_display, use_container_width=True, hide_index=True, height=420)

    csv_fefo = fefo_queue.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export FEFO Rotation Queue (CSV)",
        data=csv_fefo,
        file_name="pharmatrack_fefo_schedule.csv",
        mime="text/csv",
    )

with exp_tab3:
    st.markdown("##### Acquisition Value-at-Risk Across Expiry Tiers")
    fig_dist = plot_expiry_risk_distribution(classified_batches)
    st.pyplot(fig_dist, use_container_width=True)

with exp_tab4:
    st.markdown("##### Realized Historical Wastage Audit")
    wastage_info = analyze_recorded_wastage(wastage_df=None)
    st.info(f"{wastage_info['message']}")
    st.caption(
        "Data Integrity Standard: PharmaTrack distinguishes potential estimated expiry risk from actual realized wastage logs."
    )
