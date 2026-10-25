"""PharmaTrack - Global configuration, directory paths, schemas, and threshold definitions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

# ==============================================================================
# Filesystem Paths
# ==============================================================================
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
REPORTS_DIR: Path = BASE_DIR / "reports"
EXPORTS_DIR: Path = REPORTS_DIR / "exports"

# Ensure all critical directories exist upon configuration import
for directory in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR, EXPORTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# Operational Thresholds
# ==============================================================================
@dataclass(frozen=True)
class ExpiryThresholds:
    """Threshold settings in days for categorizing batch expiry risk levels."""

    CRITICAL_DAYS: int = 30  # Expiring within 30 days (urgent action required)
    NEAR_EXPIRY_DAYS: int = 90  # Expiring within 90 days (standard near-expiry)
    MONITORING_DAYS: int = 180  # Expiring within 180 days (early monitoring alert)


@dataclass(frozen=True)
class ReplenishmentConfig:
    """Standard factors and defaults for demand analysis and replenishment planning."""

    DEFAULT_LEAD_TIME_DAYS: int = 7
    DEFAULT_SAFETY_STOCK_DAYS: int = 5
    SAFETY_STOCK_FACTOR: float = 1.5
    DEFAULT_REVIEW_PERIOD_DAYS: int = 30


# ==============================================================================
# Dataset Schemas
# ==============================================================================
# 1. medicines.csv: medicine_id, medicine_name, category, reorder_level
SCHEMA_MEDICINES: List[str] = [
    "medicine_id",
    "medicine_name",
    "category",
    "reorder_level",
]

# 2. inventory.csv: batch_id, medicine_id, quantity, purchase_price, selling_price, expiry_date, supplier
SCHEMA_INVENTORY: List[str] = [
    "batch_id",
    "medicine_id",
    "quantity",
    "purchase_price",
    "selling_price",
    "expiry_date",
    "supplier",
]

# Alias for backward compatibility with earlier batch schema references
SCHEMA_BATCHES: List[str] = SCHEMA_INVENTORY

# 3. sales.csv: sale_id, date, batch_id, quantity_sold, unit_price
SCHEMA_SALES: List[str] = [
    "sale_id",
    "date",
    "batch_id",
    "quantity_sold",
    "unit_price",
]

DATASET_SCHEMAS: Dict[str, List[str]] = {
    "medicines": SCHEMA_MEDICINES,
    "inventory": SCHEMA_INVENTORY,
    "batches": SCHEMA_BATCHES,
    "sales": SCHEMA_SALES,
}

# ==============================================================================
# Format Constants
# ==============================================================================
DATE_FORMAT: str = "%Y-%m-%d"
TIMESTAMP_FORMAT: str = "%Y-%m-%d %H:%M:%S"
CURRENCY_SYMBOL: str = "$"

# Default simulation reference date (matches current system year 2026)
REFERENCE_DATE: str = "2026-10-25"
