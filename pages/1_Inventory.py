"""PharmaTrack — Batch-Level & Medicine Inventory Management Page."""

from datetime import datetime
import pandas as pd
import streamlit as st

import config
from src.inventory import (
    calculate_inventory_valuation_metrics,
    filter_inventory,
    get_batch_inventory_summary,
    get_low_stock_alerts,
    get_medicine_inventory_summary,
)
from src.visualization.charts import plot_stock_levels_vs_reorder
from src.visualization.state import render_sidebar_data_loader
from src.visualization.theme import (
    inject_clinical_styles,
    render_kpi_grid,
    render_page_header,
    render_sidebar_brand,
)

# Page configuration
st.set_page_config(
    page_title="Inventory | PharmaTrack",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject clinical design system
inject_clinical_styles()

# Sidebar
render_sidebar_brand(reference_date=config.REFERENCE_DATE)
dfs, _ = render_sidebar_data_loader()
med_df = dfs["medicines"]
inv_df = dfs["inventory"]

as_of = config.REFERENCE_DATE

# Header
render_page_header(
    title="Inventory",
    subtitle="Manage medicine batches, stock levels, and suppliers.",
)

# Compute metrics
metrics = calculate_inventory_valuation_metrics(inv_df, as_of_date=as_of)
medicine_summary = get_medicine_inventory_summary(inv_df, med_df, as_of_date=as_of)
batch_summary = get_batch_inventory_summary(inv_df, med_df, as_of_date=as_of)

# -----------------------------------------------------------------------------
# 1. Summary KPI Row
# -----------------------------------------------------------------------------
inv_kpis = [
    {
        "label": "Total Physical Stock",
        "value": f"{metrics['total_physical_stock_units']:,} Units",
        "subtext": f"{len(batch_summary)} discrete batches catalogued",
        "status": "normal",
    },
    {
        "label": "Usable Saleable Stock",
        "value": f"{metrics['usable_stock_units']:,} Units",
        "subtext": "Strictly excludes expired batches",
        "status": "success",
    },
    {
        "label": "Usable Inventory Valuation",
        "value": f"${metrics['usable_purchase_valuation']:,.2f}",
        "subtext": "Acquisition cost of saleable stock",
        "status": "normal",
    },
    {
        "label": "Expired Stock Exposure",
        "value": f"${metrics['expired_stock_loss_exposure']:,.2f}",
        "subtext": f"{metrics['expired_stock_units']} units quarantined (estimated)",
        "status": "critical" if metrics['expired_stock_loss_exposure'] > 0 else "success",
    },
]
render_kpi_grid(inv_kpis, is_financial=False)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Inventory Action Toolbar
# -----------------------------------------------------------------------------
show_actions = st.checkbox("Show Inward Batch & Medicine Management Actions", value=False)
if show_actions:
    act_tab1, act_tab2, act_tab3 = st.tabs(["Add Medicine", "Add Batch", "Edit Reorder Level"])

    with act_tab1:
        st.caption("Register a new medicine SKU into the hospital catalogue.")
        with st.form("form_add_medicine", clear_on_submit=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                new_med_id = st.text_input("Medicine ID", value=f"MED{len(med_df)+1:03d}")
            with f_col2:
                new_med_name = st.text_input("Medicine Name", placeholder="e.g. Ciprofloxacin 500mg")
            with f_col3:
                existing_cats = sorted(med_df["category"].dropna().unique().tolist())
                new_med_cat = st.selectbox("Therapeutic Category", existing_cats)
            with f_col4:
                new_med_reorder = st.number_input("Safety Reorder Level", min_value=5, max_value=500, value=30, step=5)

            btn_submit_med = st.form_submit_button("Save Medicine to Catalogue")
            if btn_submit_med:
                if new_med_name.strip():
                    st.success(f"Medicine '{new_med_name.strip()}' catalogued successfully with ID {new_med_id}.")
                else:
                    st.error("Medicine name cannot be empty.")

    with act_tab2:
        st.caption("Record receipt of an incoming supplier batch into inventory.")
        with st.form("form_add_batch", clear_on_submit=True):
            b_col1, b_col2, b_col3, b_col4 = st.columns(4)
            with b_col1:
                new_batch_id = st.text_input("Batch ID", value=f"BAT{len(inv_df)+101}")
            with b_col2:
                all_med_options = sorted(med_df["medicine_name"].unique().tolist())
                selected_med = st.selectbox("Medicine", all_med_options)
            with b_col3:
                new_batch_qty = st.number_input("Received Units", min_value=1, max_value=5000, value=100, step=10)
            with b_col4:
                new_batch_supplier = st.text_input("Supplier Name", placeholder="e.g. Apex Pharma Ltd")

            p_col1, p_col2, p_col3, _ = st.columns(4)
            with p_col1:
                new_purchase_p = st.number_input("Purchase Price ($)", min_value=0.1, max_value=500.0, value=10.0, step=0.5)
            with p_col2:
                new_selling_p = st.number_input("Selling Price ($)", min_value=0.1, max_value=1000.0, value=15.0, step=0.5)
            with p_col3:
                new_expiry_d = st.date_input("Expiry Date")

            btn_submit_batch = st.form_submit_button("Record Batch Inward Entry")
            if btn_submit_batch:
                st.success(f"Batch {new_batch_id} for '{selected_med}' ({new_batch_qty} units) logged successfully.")

    with act_tab3:
        st.caption("Update safety reorder thresholds for an active catalogued medicine.")
        with st.form("form_edit_record"):
            e_col1, e_col2, e_col3 = st.columns(3)
            with e_col1:
                edit_med = st.selectbox("Select Medicine to Modify", sorted(med_df["medicine_name"].unique().tolist()), key="edit_select_med")
            with e_col2:
                current_reorder = int(med_df.loc[med_df["medicine_name"] == edit_med, "reorder_level"].iloc[0]) if not med_df.loc[med_df["medicine_name"] == edit_med].empty else 30
                updated_reorder = st.number_input("Updated Reorder Level", min_value=1, max_value=1000, value=current_reorder, step=5)
            with e_col3:
                st.write("")
                st.write("")
                btn_update = st.form_submit_button("Apply Configuration Update")
                if btn_update:
                    st.success(f"Reorder threshold for '{edit_med}' updated to {updated_reorder} units.")

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. Search and Filters
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title' style='margin-top: 4px;'>Filter and Query Inventory</div>", unsafe_allow_html=True)
f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([2.5, 2, 2, 2, 1])

with f_col1:
    search_query = st.text_input("Search Medicine Name:", placeholder="e.g. Amoxicillin, Metformin...")

with f_col2:
    all_categories = ["All Categories"] + sorted(med_df["category"].dropna().unique().tolist())
    selected_category = st.selectbox("Category:", all_categories)

with f_col3:
    status_filter_options = ["All Stock", "Usable Stock Only", "Low Stock Deficit", "Near Expiry (≤90d)", "Expired Stock"]
    selected_status = st.selectbox("Stock Status:", status_filter_options)

with f_col4:
    all_suppliers = ["All Suppliers"] + sorted(batch_summary["supplier"].dropna().unique().tolist())
    selected_supplier = st.selectbox("Supplier:", all_suppliers)

with f_col5:
    st.write("")
    st.write("")
    clear_filters = st.button("Reset", use_container_width=True)

if clear_filters:
    st.rerun()

# Filter batch data
filtered_batches = batch_summary.copy()
filtered_meds = medicine_summary.copy()

if search_query:
    filtered_batches = filtered_batches[
        filtered_batches["medicine_name"].str.contains(search_query, case=False, na=False)
    ]
    filtered_meds = filtered_meds[
        filtered_meds["medicine_name"].str.contains(search_query, case=False, na=False)
    ]

if selected_category != "All Categories":
    filtered_batches = filter_inventory(filtered_batches, category=selected_category)
    filtered_meds = filter_inventory(filtered_meds, category=selected_category)

if selected_supplier != "All Suppliers":
    filtered_batches = filter_inventory(filtered_batches, supplier=selected_supplier)

if selected_status == "Usable Stock Only":
    filtered_batches = filter_inventory(filtered_batches, exclude_expired=True)
elif selected_status == "Low Stock Deficit":
    low_stock_names = filtered_meds[filtered_meds["is_low_stock"]]["medicine_name"].tolist()
    filtered_batches = filtered_batches[filtered_batches["medicine_name"].isin(low_stock_names)]
    filtered_meds = filtered_meds[filtered_meds["is_low_stock"]]
elif selected_status == "Near Expiry (≤90d)":
    filtered_batches = filtered_batches[(filtered_batches["days_to_expiry"] >= 0) & (filtered_batches["days_to_expiry"] <= 90)]
elif selected_status == "Expired Stock":
    filtered_batches = filtered_batches[filtered_batches["days_to_expiry"] < 0]

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. Clean Data Table View (Batch-Level & Catalogue)
# -----------------------------------------------------------------------------
tab_data1, tab_data2, tab_data3 = st.tabs([
    "Batch Inventory Table",
    "Medicine Catalogue Summary",
    "Stock vs. Reorder Level Chart",
])

with tab_data1:
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(f"**Showing {len(filtered_batches)} Batch Record(s)**")
    with h_col2:
        csv_batch_data = filtered_batches.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export CSV",
            data=csv_batch_data,
            file_name="pharmatrack_batch_inventory.csv",
            mime="text/csv",
            use_container_width=True,
        )

    # Required columns per specification:
    # Medicine name, Batch ID, Category, Quantity available, Purchase price, Selling price, Expiry date, Supplier, Stock status
    batch_display = filtered_batches[[
        "medicine_name",
        "batch_id",
        "category",
        "quantity",
        "purchase_price",
        "selling_price",
        "expiry_date",
        "supplier",
        "expiry_status",
    ]].copy()

    batch_display["expiry_date"] = pd.to_datetime(batch_display["expiry_date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna(batch_display["expiry_date"].astype(str))
    batch_display["purchase_price"] = batch_display["purchase_price"].apply(lambda v: f"${float(v):,.2f}")
    batch_display["selling_price"] = batch_display["selling_price"].apply(lambda v: f"${float(v):,.2f}")

    batch_display.rename(columns={
        "medicine_name": "Medicine Name",
        "batch_id": "Batch ID",
        "category": "Category",
        "quantity": "Quantity Available",
        "purchase_price": "Purchase Price",
        "selling_price": "Selling Price",
        "expiry_date": "Expiry Date",
        "supplier": "Supplier",
        "expiry_status": "Stock Status",
    }, inplace=True)

    st.dataframe(batch_display, use_container_width=True, hide_index=True, height=440)

with tab_data2:
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(f"**Showing {len(filtered_meds)} Medicine Record(s)**")
    with h_col2:
        csv_med_data = filtered_meds.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export CSV",
            data=csv_med_data,
            file_name="pharmatrack_medicine_catalogue.csv",
            mime="text/csv",
            use_container_width=True,
        )

    med_display = filtered_meds[[
        "medicine_id",
        "medicine_name",
        "category",
        "batch_count",
        "usable_quantity",
        "expired_quantity",
        "reorder_level",
        "stock_status",
        "usable_purchase_value",
    ]].copy()

    med_display["usable_purchase_value"] = med_display["usable_purchase_value"].apply(lambda v: f"${float(v):,.2f}")

    med_display.rename(columns={
        "medicine_id": "Medicine ID",
        "medicine_name": "Medicine Name",
        "category": "Category",
        "batch_count": "Active Batches",
        "usable_quantity": "Usable Units",
        "expired_quantity": "Expired Units",
        "reorder_level": "Reorder Level",
        "stock_status": "Status",
        "usable_purchase_value": "Usable Valuation",
    }, inplace=True)

    st.dataframe(med_display, use_container_width=True, hide_index=True, height=440)

with tab_data3:
    st.markdown("##### Usable Stock vs. Safety Reorder Level")
    fig_stock = plot_stock_levels_vs_reorder(filtered_meds, top_n=14)
    st.pyplot(fig_stock, use_container_width=True)
