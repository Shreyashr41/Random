"""State management and data loading helper for the Streamlit dashboard."""

from typing import Dict, Optional, Tuple
import pandas as pd
import streamlit as st

from config import RAW_DATA_DIR
from src.data import (
    clean_and_type_coerce,
    generate_synthetic_datasets,
    ingest_and_validate_data,
    validate_all_datasets,
)


@st.cache_data(show_spinner=False)
def load_default_data() -> Tuple[Dict[str, pd.DataFrame], bool, Optional[str]]:
    """Load, validate, and return default synthetic datasets.

    Returns:
        Tuple of (dfs_dict, is_valid, validation_report_text).
    """
    try:
        dfs, report = ingest_and_validate_data(data_dir=RAW_DATA_DIR, export_processed=True)
        return dfs, report.is_valid, report.to_markdown()
    except Exception:
        # Fallback to generating in-memory synthetic data if files not yet written
        generated = generate_synthetic_datasets(seed=42, save_to_disk=True)
        clean_med, clean_inv, clean_sal = clean_and_type_coerce(
            generated["medicines"], generated["inventory"], generated["sales"]
        )
        dfs = {"medicines": clean_med, "inventory": clean_inv, "sales": clean_sal}
        _, report = validate_all_datasets(clean_med, clean_inv, clean_sal)
        return dfs, report.is_valid, report.to_markdown()


def render_sidebar_data_loader() -> Tuple[Dict[str, pd.DataFrame], str]:
    """Render consistent sidebar controls for data source selection and file uploading.

    Returns:
        Tuple of (loaded_dataframes_dict, data_source_label).
    """
    st.sidebar.markdown("##### Data Management")
    data_source = st.sidebar.radio(
        "Data Source:",
        ["Synthetic Demo Data", "Upload Custom CSVs"],
        index=0,
    )

    if data_source == "Synthetic Demo Data":
        with st.sidebar:
            if st.button("Regenerate Sample Data", help="Regenerate reproducible synthetic datasets"):
                generate_synthetic_datasets(seed=42, save_to_disk=True)
                st.cache_data.clear()
                st.success("Sample datasets refreshed successfully.")
                st.rerun()

        dfs, is_valid, report_text = load_default_data()
        st.sidebar.caption("Source: Validated Synthetic Dataset")
        with st.sidebar.expander("Validation Report"):
            st.markdown(report_text)
        return dfs, "Synthetic Demo Data"

    else:
        st.sidebar.info("Upload 3 required CSV files: medicines.csv, inventory.csv, sales.csv.")
        med_file = st.sidebar.file_uploader("Upload medicines.csv", type=["csv"], key="upload_med")
        inv_file = st.sidebar.file_uploader("Upload inventory.csv", type=["csv"], key="upload_inv")
        sal_file = st.sidebar.file_uploader("Upload sales.csv", type=["csv"], key="upload_sal")

        if med_file and inv_file and sal_file:
            try:
                med_df = pd.read_csv(med_file, dtype=str)
                inv_df = pd.read_csv(inv_file, dtype=str)
                sal_df = pd.read_csv(sal_file, dtype=str)

                is_valid, report = validate_all_datasets(med_df.copy(), inv_df.copy(), sal_df.copy())
                if not is_valid:
                    st.sidebar.error("Uploaded files contain validation errors.")
                    with st.sidebar.expander("Validation Issues"):
                        st.markdown(report.to_markdown())

                clean_med, clean_inv, clean_sal = clean_and_type_coerce(med_df, inv_df, sal_df)
                custom_dfs = {
                    "medicines": clean_med,
                    "inventory": clean_inv,
                    "sales": clean_sal,
                }
                st.sidebar.success("Custom CSVs validated and active.")
                return custom_dfs, "Custom Upload"
            except Exception as ex:
                st.sidebar.error(f"Error parsing uploaded files: {ex}")
                dfs, _, _ = load_default_data()
                return dfs, "Fallback Demo Data"
        else:
            st.sidebar.caption("Awaiting upload. Demo datasets currently loaded.")
            dfs, _, _ = load_default_data()
            return dfs, "Fallback Demo Data"
