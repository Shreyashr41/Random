"""PharmaTrack — Sales and Gross Profit Analytics Page."""

from datetime import datetime
import pandas as pd
import streamlit as st

import config
from src.analytics import (
    calculate_sales_statistics,
    get_periodic_sales_summary,
    get_sales_by_dimension,
    get_slow_moving_medicines,
    get_top_selling_medicines,
    prepare_enriched_sales,
)
from src.visualization.charts import (
    plot_category_revenue_profit_comparison,
    plot_revenue_time_series,
    plot_sales_correlation_heatmap,
    plot_top_selling_medicines,
    plot_transaction_basket_distribution,
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
    page_title="Sales Analytics | PharmaTrack",
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
    title="Sales Analytics",
    subtitle="Understand sales performance and medicine demand.",
)

# Prepare enriched transactions with actual batch purchase costs (COGS)
enriched = prepare_enriched_sales(sal_df, inv_df, med_df)

if enriched.empty:
    st.info("No transaction records available for analytical evaluation.")
    st.stop()

# -----------------------------------------------------------------------------
# 1. Date-Range & Category Filters
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title' style='margin-top: 2px;'>Filter Evaluation Window</div>", unsafe_allow_html=True)
f_col1, f_col2, f_col3 = st.columns(3)

min_date = enriched["date"].min().date()
max_date = enriched["date"].max().date()

with f_col1:
    date_range = st.date_input(
        "Date Range Filter:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

with f_col2:
    all_categories = ["All Categories"] + sorted(enriched["category"].dropna().unique().tolist())
    selected_category = st.selectbox("Therapeutic Category:", all_categories)

with f_col3:
    freq_choice = st.selectbox("Trend Aggregation Interval:", ["Daily", "Weekly", "Monthly"], index=0)
    freq_map = {"Daily": "D", "Weekly": "W", "Monthly": "M"}
    freq_code = freq_map[freq_choice]

# Apply filters
filtered_sales = enriched.copy()
start_d_str, end_d_str = str(min_date), str(max_date)

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_d, end_d = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    filtered_sales = filtered_sales[(filtered_sales["date"] >= start_d) & (filtered_sales["date"] <= end_d)]
    start_d_str, end_d_str = str(date_range[0]), str(date_range[1])

if selected_category != "All Categories":
    filtered_sales = filtered_sales[filtered_sales["category"] == selected_category]

# Calculate statistical metrics on filtered subset
stats = calculate_sales_statistics(filtered_sales)

st.caption(f"Active Filtering Window: {start_d_str} to {end_d_str} ({stats['total_transactions']:,} transactions recorded).")

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. Executive Sales KPI Cards (Per specification)
# -----------------------------------------------------------------------------
sales_kpis = [
    {
        "label": "Total Revenue",
        "value": f"${stats['total_revenue']:,.2f}",
        "subtext": "Gross recorded sales across window",
        "status": "normal",
    },
    {
        "label": "Units Sold",
        "value": f"{stats['total_units_sold']:,} Units",
        "subtext": f"Avg order: ${stats['avg_transaction_revenue']:,.2f}",
        "status": "normal",
    },
    {
        "label": "Gross Profit",
        "value": f"${stats['total_gross_profit']:,.2f}",
        "subtext": f"{stats['overall_gross_margin_pct']}% Gross margin (true batch COGS)",
        "status": "success",
    },
    {
        "label": "Number of Transactions",
        "value": f"{stats['total_transactions']:,} Txns",
        "subtext": f"COGS: ${stats['total_cogs']:,.2f}",
        "status": "normal",
    },
]
render_kpi_grid(sales_kpis, is_financial=False)

st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. Visual Charts (Revenue over time, Profit over time, Top sellers, Category)
# -----------------------------------------------------------------------------
chart_row1_col1, chart_row1_col2 = st.columns(2)

with chart_row1_col1:
    periodic_summary = get_periodic_sales_summary(filtered_sales, freq=freq_code)
    fig_trend = plot_revenue_time_series(periodic_summary, title=f"Revenue and 7-Day Moving Average Trend ($ USD)")
    st.pyplot(fig_trend, use_container_width=True)

with chart_row1_col2:
    cat_summary = get_sales_by_dimension(filtered_sales, dimension="category")
    fig_cat = plot_category_revenue_profit_comparison(cat_summary)
    st.pyplot(fig_cat, use_container_width=True)

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. Tables: Best-Selling Medicines & Slow-Moving Medicines
# -----------------------------------------------------------------------------
st.markdown("<div class='pt-section-title'>Medicine Performance & Velocity Tables</div>", unsafe_allow_html=True)
tbl_tab1, tbl_tab2, tbl_tab3 = st.tabs([
    "Best-Selling Medicines",
    "Slow-Moving Medicines",
    "Periodic Sales Ledger",
])

with tbl_tab1:
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        rank_metric = st.radio(
            "Rank Medicines By:",
            ["Revenue", "Units Sold", "Gross Profit"],
            horizontal=True,
        )
    with h_col2:
        st.write("")
        metric_key = "total_revenue" if rank_metric == "Revenue" else ("units_sold" if rank_metric == "Units Sold" else "gross_profit")
        top_meds = get_top_selling_medicines(filtered_sales, top_n=15, rank_by=metric_key)
        csv_top = top_meds.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export Best Sellers (CSV)",
            data=csv_top,
            file_name="pharmatrack_top_selling_medicines.csv",
            mime="text/csv",
            use_container_width=True,
        )

    top_display = top_meds[[
        "rank",
        "medicine_id",
        "medicine_name",
        "category",
        "units_sold",
        "total_revenue",
        "gross_profit",
        "gross_margin_pct",
        "revenue_share_pct",
    ]].copy()

    top_display["total_revenue"] = top_display["total_revenue"].apply(lambda v: f"${float(v):,.2f}")
    top_display["gross_profit"] = top_display["gross_profit"].apply(lambda v: f"${float(v):,.2f}")
    top_display["gross_margin_pct"] = top_display["gross_margin_pct"].apply(lambda v: f"{float(v):.1f}%")
    top_display["revenue_share_pct"] = top_display["revenue_share_pct"].apply(lambda v: f"{float(v):.1f}%")

    top_display.rename(columns={
        "rank": "Rank",
        "medicine_id": "Medicine ID",
        "medicine_name": "Medicine",
        "category": "Category",
        "units_sold": "Units Sold",
        "total_revenue": "Gross Revenue",
        "gross_profit": "Gross Profit",
        "gross_margin_pct": "Margin",
        "revenue_share_pct": "Revenue Share",
    }, inplace=True)

    st.dataframe(top_display, use_container_width=True, hide_index=True, height=400)

with tbl_tab2:
    st.caption("Identifies medicines with low unit dispensing velocity over the evaluation window while holding active physical stock.")

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1.5, 1.5, 1])
    with ctrl_col1:
        window_days = st.number_input("Velocity Lookback Window (Days):", min_value=30, max_value=365, value=90, step=15)
    with ctrl_col2:
        unit_threshold = st.number_input("Velocity Unit Threshold:", min_value=1, max_value=100, value=25, step=5)
    with ctrl_col3:
        st.write("")
        st.write("")

    slow_meds = get_slow_moving_medicines(
        enriched_sales_df=enriched,
        medicines_df=med_df,
        inventory_df=inv_df,
        days_window=int(window_days),
        sales_threshold_units=int(unit_threshold),
        as_of_date=as_of,
    )

    if not slow_meds.empty:
        st.warning(f"{len(slow_meds)} medicine(s) flagged as slow-moving (≤{unit_threshold} units dispensed in last {window_days} days).")
        csv_slow = slow_meds.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export Slow-Moving Medicines (CSV)",
            data=csv_slow,
            file_name="pharmatrack_slow_moving_medicines.csv",
            mime="text/csv",
        )
        st.dataframe(slow_meds, use_container_width=True, hide_index=True, height=380)
    else:
        st.success("No medicines are currently classified as slow-moving under the selected parameters.")

with tbl_tab3:
    st.markdown("##### Periodic Aggregated Financial Ledger")
    csv_periodic = periodic_summary.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export Periodic Summary (CSV)",
        data=csv_periodic,
        file_name="pharmatrack_periodic_sales.csv",
        mime="text/csv",
    )
    display_periodic = periodic_summary.rename(columns={
        "period": "Period",
        "transaction_count": "Transactions",
        "total_units_sold": "Units Sold",
        "total_revenue": "Revenue ($)",
        "total_cogs": "COGS ($)",
        "total_gross_profit": "Gross Profit ($)",
        "gross_margin_pct": "Margin (%)",
        "avg_order_value": "Avg Order ($)",
        "avg_units_per_order": "Units / Order",
    })
    st.dataframe(display_periodic, use_container_width=True, hide_index=True, height=380)
