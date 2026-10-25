"""Synthetic pharmacy data generator for PharmaTrack.

Generates realistic, reproducible, and fully relational synthetic pharmacy datasets:
- medicines.csv (medicine catalog)
- inventory.csv (batch-level inventory with purchase costs & expiry dates)
- sales.csv (sales transactions tied to valid batches)
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from config import (
    DATE_FORMAT,
    RAW_DATA_DIR,
    REFERENCE_DATE,
    SCHEMA_INVENTORY,
    SCHEMA_MEDICINES,
    SCHEMA_SALES,
)

# Reference catalog of standard pharmaceutical medicines
MEDICINE_CATALOG: List[Dict[str, str]] = [
    {"name": "Amoxicillin 500mg", "category": "Antibiotics"},
    {"name": "Azithromycin 250mg", "category": "Antibiotics"},
    {"name": "Ciprofloxacin 500mg", "category": "Antibiotics"},
    {"name": "Cefixime 200mg", "category": "Antibiotics"},
    {"name": "Paracetamol 650mg", "category": "Analgesics"},
    {"name": "Ibuprofen 400mg", "category": "Analgesics"},
    {"name": "Diclofenac 50mg", "category": "Analgesics"},
    {"name": "Tramadol 50mg", "category": "Analgesics"},
    {"name": "Amlodipine 5mg", "category": "Cardiovascular"},
    {"name": "Losartan 50mg", "category": "Cardiovascular"},
    {"name": "Atorvastatin 20mg", "category": "Cardiovascular"},
    {"name": "Metoprolol 25mg", "category": "Cardiovascular"},
    {"name": "Metformin 500mg", "category": "Antidiabetic"},
    {"name": "Glimepiride 2mg", "category": "Antidiabetic"},
    {"name": "Sitagliptin 100mg", "category": "Antidiabetic"},
    {"name": "Omeprazole 20mg", "category": "Gastrointestinal"},
    {"name": "Pantoprazole 40mg", "category": "Gastrointestinal"},
    {"name": "Ranitidine 150mg", "category": "Gastrointestinal"},
    {"name": "Cetirizine 10mg", "category": "Antihistamine"},
    {"name": "Montelukast 10mg", "category": "Respiratory"},
    {"name": "Salbutamol Inhaler 100mcg", "category": "Respiratory"},
    {"name": "Vitamin D3 60K IU", "category": "Vitamins & Supplements"},
    {"name": "Ascorbic Acid (Vit C) 500mg", "category": "Vitamins & Supplements"},
    {"name": "Zinc Sulfate 50mg", "category": "Vitamins & Supplements"},
    {"name": "Multivitamin Complex", "category": "Vitamins & Supplements"},
]

SUPPLIERS: List[str] = [
    "Apex Pharma Distributors",
    "CarePoint Logistics",
    "MedLife Wholesale",
    "GlobalHealth Supplies",
    "BioPharm Direct",
]


def generate_synthetic_datasets(
    seed: int = 42,
    output_dir: Path = RAW_DATA_DIR,
    save_to_disk: bool = True,
) -> Dict[str, pd.DataFrame]:
    """Generate reproducible, relational synthetic datasets for PharmaTrack.

    Args:
        seed: Random seed for exact reproducibility.
        output_dir: Target directory to write raw CSV files.
        save_to_disk: If True, writes medicines.csv, inventory.csv, and sales.csv to disk.

    Returns:
        Dictionary containing DataFrames for medicines, inventory, and sales.
    """
    rng = np.random.default_rng(seed)
    ref_date = datetime.strptime(REFERENCE_DATE, DATE_FORMAT)

    # -------------------------------------------------------------------------
    # 1. Generate medicines.csv
    # -------------------------------------------------------------------------
    medicines_records = []
    for idx, item in enumerate(MEDICINE_CATALOG, start=1):
        med_id = f"MED-{idx:03d}"
        reorder_level = int(rng.choice([15, 20, 25, 30, 40, 50]))
        medicines_records.append({
            "medicine_id": med_id,
            "medicine_name": item["name"],
            "category": item["category"],
            "reorder_level": reorder_level,
        })

    medicines_df = pd.DataFrame(medicines_records)[SCHEMA_MEDICINES]

    # -------------------------------------------------------------------------
    # 2. Generate inventory.csv (batches)
    # -------------------------------------------------------------------------
    batch_records = []
    batch_counter = 1
    # Store initial batch capacity for transaction simulation
    batch_meta: Dict[str, Dict] = {}

    for _, med in medicines_df.iterrows():
        med_id = med["medicine_id"]
        # Generate 2 to 4 batches per medicine
        num_batches = int(rng.integers(2, 5))

        # Base purchase cost between $2.00 and $40.00
        base_cost = round(float(rng.uniform(2.5, 38.0)), 2)

        for _ in range(num_batches):
            batch_id = f"BAT-{batch_counter:04d}"
            batch_counter += 1

            # Slight cost variance between batches of same medicine
            cost_var = float(rng.uniform(-0.10, 0.15))
            purchase_price = round(max(1.0, base_cost * (1.0 + cost_var)), 2)
            # Selling price with 25% to 55% margin
            margin_pct = float(rng.uniform(0.25, 0.55))
            selling_price = round(purchase_price * (1.0 + margin_pct), 2)

            supplier = str(rng.choice(SUPPLIERS))

            # Expiry date distribution:
            # 10% expired, 15% critical (<= 30 days), 20% near expiry (<= 90 days), 55% safe (> 90 days)
            expiry_category = rng.choice(["expired", "critical", "near_expiry", "safe"], p=[0.10, 0.15, 0.20, 0.55])
            if expiry_category == "expired":
                offset_days = int(rng.integers(-120, -5))
            elif expiry_category == "critical":
                offset_days = int(rng.integers(5, 29))
            elif expiry_category == "near_expiry":
                offset_days = int(rng.integers(31, 89))
            else:
                offset_days = int(rng.integers(120, 720))

            expiry_dt = ref_date + timedelta(days=offset_days)
            expiry_str = expiry_dt.strftime(DATE_FORMAT)

            # Initial stock received
            initial_stock = int(rng.integers(50, 400))

            batch_meta[batch_id] = {
                "batch_id": batch_id,
                "medicine_id": med_id,
                "initial_stock": initial_stock,
                "purchase_price": purchase_price,
                "selling_price": selling_price,
                "expiry_date": expiry_str,
                "expiry_dt": expiry_dt,
                "supplier": supplier,
                "sold_quantity": 0,
            }

    # -------------------------------------------------------------------------
    # 3. Generate sales.csv (consistent with available batch stock)
    # -------------------------------------------------------------------------
    sales_records = []
    sale_counter = 1
    total_target_sales = 450

    batch_ids = list(batch_meta.keys())

    # We simulate sales over the past 90 days leading to ref_date
    start_sales_dt = ref_date - timedelta(days=90)

    for _ in range(total_target_sales):
        # Pick candidate batch
        b_id = str(rng.choice(batch_ids))
        b_data = batch_meta[b_id]

        # Check remaining capacity
        remaining_capacity = b_data["initial_stock"] - b_data["sold_quantity"]
        if remaining_capacity <= 5:
            continue

        # Transaction quantity between 1 and min(15, remaining_capacity - 1)
        max_allowed_qty = max(1, min(15, remaining_capacity - 5))
        qty_sold = int(rng.integers(1, max_allowed_qty + 1))

        # Pick transaction date within the active window (before or at ref_date, before expiry)
        max_sale_dt = min(ref_date, b_data["expiry_dt"])
        if max_sale_dt <= start_sales_dt:
            continue

        days_window = (max_sale_dt - start_sales_dt).days
        if days_window <= 0:
            sale_dt = start_sales_dt
        else:
            sale_dt = start_sales_dt + timedelta(days=int(rng.integers(0, days_window + 1)))

        sale_id = f"SAL-{sale_counter:05d}"
        sale_counter += 1

        unit_price = b_data["selling_price"]
        b_data["sold_quantity"] += qty_sold

        sales_records.append({
            "sale_id": sale_id,
            "date": sale_dt.strftime(DATE_FORMAT),
            "batch_id": b_id,
            "quantity_sold": qty_sold,
            "unit_price": unit_price,
        })

    sales_df = pd.DataFrame(sales_records)[SCHEMA_SALES]

    # Calculate final inventory current quantity: initial_stock - sold_quantity
    for b_id, b_data in batch_meta.items():
        current_quantity = max(0, b_data["initial_stock"] - b_data["sold_quantity"])
        batch_records.append({
            "batch_id": b_id,
            "medicine_id": b_data["medicine_id"],
            "quantity": current_quantity,
            "purchase_price": b_data["purchase_price"],
            "selling_price": b_data["selling_price"],
            "expiry_date": b_data["expiry_date"],
            "supplier": b_data["supplier"],
        })

    inventory_df = pd.DataFrame(batch_records)[SCHEMA_INVENTORY]

    # Sort sales chronologically
    sales_df["date_dt"] = pd.to_datetime(sales_df["date"])
    sales_df = sales_df.sort_values(by=["date_dt", "sale_id"]).drop(columns=["date_dt"]).reset_index(drop=True)

    # -------------------------------------------------------------------------
    # Save to disk
    # -------------------------------------------------------------------------
    if save_to_disk:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        medicines_df.to_csv(output_dir / "medicines.csv", index=False)
        inventory_df.to_csv(output_dir / "inventory.csv", index=False)
        sales_df.to_csv(output_dir / "sales.csv", index=False)

    return {
        "medicines": medicines_df,
        "inventory": inventory_df,
        "sales": sales_df,
    }


if __name__ == "__main__":
    print(f"Generating synthetic PharmaTrack datasets with seed 42 in {RAW_DATA_DIR}...")
    datasets = generate_synthetic_datasets(seed=42, output_dir=RAW_DATA_DIR, save_to_disk=True)
    print("Generation complete:")
    for name, df in datasets.items():
        print(f" - {name}.csv: {len(df)} records")
