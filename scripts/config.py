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

# Yahoo Finance - Silver Futures Symbol
YAHOO_SILVER_SYMBOL = "SI=F"

# === Historical Thresholds ===
# These define what "normal" vs "stressed" looks like

THRESHOLDS = {
    # Lease Rates (annualized %)
    "lease_rate": {
        "normal_low": 0.3,
        "normal_high": 3.0,
        "stressed": 10.0,  # Above this = major stress
        "extreme": 20.0,   # Above this = crisis
    },
    
    # Physical Premiums (% over spot)
    "premium_pct": {
        "normal_low": 3.0,
        "normal_high": 10.0,
        "stressed": 20.0,
        "extreme": 50.0,
    },
    
    # Physical Premiums ($/oz over spot for coins)
    "premium_usd_coins": {
        "normal_low": 4.0,
        "normal_high": 8.0,
        "stressed": 15.0,
        "extreme": 25.0,
    },
    
    # COMEX Inventory (millions of oz)
    "inventory_total": {
        "healthy": 400.0,
        "normal_low": 300.0,
        "stressed": 250.0,
        "critical": 200.0,
    },
    
    # COMEX Registered (millions of oz)
    "inventory_registered": {
        "healthy": 100.0,
        "normal_low": 75.0,
        "stressed": 50.0,
        "critical": 30.0,
    },
    
    # Margin stability (days since last change)
    "margin_stability_days": {
        "stable": 30,      # 1+ month = stable
        "normalizing": 14, # 2+ weeks = improving
        "volatile": 7,     # Weekly changes = stressed
    },
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
UPDATE_INTERVAL_HOURS = 12

# === Logging ===
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
