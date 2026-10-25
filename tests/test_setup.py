"""Smoke and setup tests for PharmaTrack (Phase 0)."""

import ast
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
import matplotlib
import seaborn as sns
import streamlit as st

import config
import src
import src.data
import src.inventory
import src.analytics
import src.expiry
import src.visualization


def test_core_dependencies_importable():
    """Verify that all mandatory analytical and UI libraries are installed and operational."""
    assert pd.__version__ is not None
    assert np.__version__ is not None
    assert matplotlib.__version__ is not None
    assert sns.__version__ is not None
    assert st.__version__ is not None
    assert pytest.__version__ is not None


def test_configuration_directories_exist():
    """Verify that all standard directories configured in config.py exist on disk."""
    assert isinstance(config.BASE_DIR, Path)
    assert config.BASE_DIR.exists()
    assert config.DATA_DIR.exists()
    assert config.RAW_DATA_DIR.exists()
    assert config.PROCESSED_DATA_DIR.exists()
    assert config.REPORTS_DIR.exists()
    assert config.EXPORTS_DIR.exists()


def test_expiry_and_replenishment_thresholds():
    """Verify operational threshold settings."""
    expiry = config.ExpiryThresholds()
    assert expiry.CRITICAL_DAYS == 30
    assert expiry.NEAR_EXPIRY_DAYS == 90
    assert expiry.MONITORING_DAYS == 180

    replenish = config.ReplenishmentConfig()
    assert replenish.DEFAULT_LEAD_TIME_DAYS == 7
    assert replenish.DEFAULT_SAFETY_STOCK_DAYS == 5
    assert replenish.SAFETY_STOCK_FACTOR == 1.5
    assert replenish.DEFAULT_REVIEW_PERIOD_DAYS == 30


def test_dataset_schemas_definition():
    """Verify dataset schemas contain required core fields."""
    assert "medicine_id" in config.SCHEMA_MEDICINES
    assert "medicine_name" in config.SCHEMA_MEDICINES
    assert "reorder_level" in config.SCHEMA_MEDICINES

    assert "batch_id" in config.SCHEMA_INVENTORY
    assert "expiry_date" in config.SCHEMA_INVENTORY
    assert "purchase_price" in config.SCHEMA_INVENTORY

    assert "sale_id" in config.SCHEMA_SALES
    assert "date" in config.SCHEMA_SALES


def test_source_subpackages_importable():
    """Verify that all src subpackages are properly structured and importable."""
    assert hasattr(src, "__version__")
    assert src.data is not None
    assert src.inventory is not None
    assert src.analytics is not None
    assert src.expiry is not None
    assert src.visualization is not None


def test_app_entrypoint_validity():
    """Verify app.py exists, contains valid Python syntax, and defines main()."""
    app_file = config.BASE_DIR / "app.py"
    assert app_file.exists(), "app.py does not exist at project root"

    with open(app_file, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename="app.py")

    func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert "main" in func_names, "app.py must define a main() function"


def test_pages_directory_and_syntax():
    """Verify Streamlit pages exist and have valid Python syntax."""
    pages_dir = config.BASE_DIR / "pages"
    assert pages_dir.exists() and pages_dir.is_dir()

    page_files = list(pages_dir.glob("*.py"))
    assert len(page_files) >= 4, "Expected at least 4 page stubs in pages/"

    for page_path in page_files:
        with open(page_path, "r", encoding="utf-8") as f:
            ast.parse(f.read(), filename=page_path.name)
