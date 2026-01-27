"""
Configuration settings for Silver Metrics Tracker.
Contains URLs, thresholds, and constants.
"""

import os
from pathlib import Path

# === Directory Paths ===
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DATA_DIR = DOCS_DIR / "data"

# Database
DB_PATH = DATA_DIR / "silver_metrics.db"

# === Data Source URLs ===

# CME Group - COMEX Silver Warehouse Stocks
CME_SILVER_STOCKS_URL = "https://www.cmegroup.com/delivery_reports/Silver_stocks.xls"

# CME Group - Silver Futures Margins
CME_SILVER_MARGINS_URL = "https://www.cmegroup.com/markets/metals/precious/silver.margins.html"

# Kitco - Spot Prices
KITCO_SPOT_URL = "https://www.kitco.com/charts/livesilver.html"

# Paper vs Physical - Premium Tracking
PAPER_VS_PHYSICAL_URL = "https://www.papervsphysical.com"

# Shanghai Premium - MetalpriceAPI (get free key at https://metalpriceapi.com/register)
# Set via environment variable: export METALPRICEAPI_KEY=your_key_here
# Note: Free tier (100 requests/month) insufficient for hourly updates (720/month). Paid plan required.
METALPRICEAPI_URL = "https://api.metalpriceapi.com/v1/latest"

# Shanghai premium reference (for validation): https://metalcharts.org/shanghai

# Yahoo Finance - Silver Futures Symbol
YAHOO_SILVER_SYMBOL = "SI=F"

# === Historical Thresholds ===
# These define what "normal" vs "stressed" looks like
# Based on 2010-2025 historical data analysis
# Reference: Pre-2021 quiet periods, 2021 squeeze, 2025 rally recovery

THRESHOLDS = {
    # Lease Rates (annualized %)
    # Historical: 0.3-3% normal (balanced supply), >5% = borrowing stress, 20-40%+ = shortage
    "lease_rate": {
        "normal_low": 0.3,
        "normal_high": 3.0,
        "watch": 5.0,        # Yellow - borrowing stress emerging
        "stressed": 10.0,     # Red - major stress
        "extreme": 20.0,      # Crisis level
    },
    
    # Physical Premiums (% over spot)
    # Historical: 5-15% normal (aggregate/generic), 15-20% watch, >20% = retail shortage
    # Note: Government coins (Eagles) naturally higher (10-25%); generic bars 5-10%
    "premium_pct": {
        "normal_low": 5.0,
        "normal_high": 15.0,
        "watch": 20.0,        # Yellow - elevated demand
        "stressed": 30.0,     # Red - shortage signal
        "extreme": 50.0,      # Severe shortage
    },
    
    # Physical Premiums ($/oz over spot for coins)
    "premium_usd_coins": {
        "normal_low": 4.0,
        "normal_high": 8.0,
        "stressed": 15.0,
        "extreme": 25.0,
    },
    
    # COMEX Inventory (millions of oz)
    # Historical: 350-450M normal, >500M = buildups, <300M = drawdowns/delivery pressure
    # Recovery/inflows above 400M ease stress
    "inventory_total": {
        "healthy": 400.0,      # Green - good buffer, recovery signal
        "normal_low": 350.0,   # Yellow - watchable but acceptable
        "stressed": 300.0,     # Red - delivery pressure likely
        "critical": 250.0,     # Extreme tightness
    },
    
    # COMEX Registered (millions of oz)
    # Deliverable silver - more sensitive indicator
    "inventory_registered": {
        "healthy": 100.0,
        "normal_low": 75.0,
        "stressed": 50.0,
        "critical": 30.0,
    },
    
    # Margin stability (days since last change)
    # Frequent hikes signal speculative heat (e.g., 2011, 2025-2026 adjustments)
    "margin_stability_days": {
        "stable": 30,          # 1+ month = green (normalized)
        "normalizing": 14,     # 2+ weeks = yellow (cooling)
        "volatile": 7,         # Weekly changes = red (stressed)
    },
    
    # Margin as % of notional value
    # New threshold: Normal ~7-9%, warning >10%
    # Notional = 5000 oz × spot price
    "margin_pct_notional": {
        "normal_low": 7.0,
        "normal_high": 9.0,
        "elevated": 10.0,      # Warning threshold
        "extreme": 12.0,
    },
    
    # Shanghai Gold Exchange Premium (USD per troy oz)
    # Measures East-West arbitrage gap
    # Normal: $1-2/oz difference, elevated demand in China or supply constraints push higher
    "shanghai_premium": {
        "normal_high": 2.0,     # Green - normal arbitrage range
        "elevated": 5.0,        # Yellow - elevated China demand
        "stressed": 8.0,        # Red - significant arbitrage opportunity/supply constraint
    },
}

# === Composite Score Thresholds ===
# How many indicators must be "green" for overall market easing signal
COMPOSITE_THRESHOLDS = {
    "easing": 4,        # 4-5 of 5 = market easing (green overall)
    "mixed": 2,         # 2-3 of 5 = mixed signals (yellow)
    "stressed": 1,      # ≤1 of 5 = market stress (red)
}

# === Status Determination ===
# Maps metric values to status colors

STATUS_COLORS = {
    "green": "normalizing",  # Market stress easing
    "yellow": "caution",     # Elevated but not extreme
    "red": "stressed",       # High stress / supply tightness
}

# === Request Headers ===
# Mimic browser to avoid blocks

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# === Update Schedule ===
UPDATE_INTERVAL_HOURS = 1

# === Logging ===
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
