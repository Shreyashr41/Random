"""Sales, revenue, profit, and demand analytics package for PharmaTrack."""

from src.analytics.service import (
    DEMAND_ESTIMATE_DISCLAIMER,
    prepare_enriched_sales,
    get_periodic_sales_summary,
    get_sales_by_dimension,
    get_top_selling_medicines,
    get_slow_moving_medicines,
    calculate_sales_statistics,
    estimate_demand_trends,
    export_analytics_summary,
)

__all__ = [
    "DEMAND_ESTIMATE_DISCLAIMER",
    "prepare_enriched_sales",
    "get_periodic_sales_summary",
    "get_sales_by_dimension",
    "get_top_selling_medicines",
    "get_slow_moving_medicines",
    "calculate_sales_statistics",
    "estimate_demand_trends",
    "export_analytics_summary",
]
