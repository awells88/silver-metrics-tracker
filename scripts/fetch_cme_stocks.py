"""
Fetch COMEX silver warehouse inventory data from CME Group.
Downloads and parses the daily Silver_stocks.xls report.
"""

import logging
import io
from datetime import datetime
from typing import Optional, Dict, Any

import requests
import pandas as pd

from scripts.config import CME_SILVER_STOCKS_URL, REQUEST_HEADERS, RAW_DATA_DIR
from scripts.db import insert_inventory, get_latest_inventory

logger = logging.getLogger(__name__)


def download_cme_stocks_file() -> Optional[bytes]:
    """
    Download the CME Silver stocks XLS file.
    Returns raw bytes of the file.
    """
    try:
        response = requests.get(
            CME_SILVER_STOCKS_URL, 
            headers=REQUEST_HEADERS, 
            timeout=60
        )
        response.raise_for_status()
        
        # Verify we got an Excel file
        content_type = response.headers.get('Content-Type', '')
        if 'excel' not in content_type.lower() and 'spreadsheet' not in content_type.lower():
            # CME might return HTML error page
            if b'<html' in response.content[:100].lower():
                logger.error("Received HTML instead of Excel file - CME may be blocking")
                return None
        
        logger.info(f"Downloaded CME stocks file: {len(response.content)} bytes")
        return response.content
        
    except requests.RequestException as e:
        logger.error(f"Error downloading CME stocks file: {e}")
        return None


def parse_cme_stocks(file_content: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse the CME Silver stocks XLS file.
    Extracts registered, eligible, and total ounces.
    
    CME file structure:
    - Individual warehouse sections with per-warehouse totals
    - Row "TOTAL REGISTERED": 114,262,775.06 oz (across all warehouses)
    - Row "TOTAL ELIGIBLE": 303,898,928.60 oz
    - Row "COMBINED TOTAL": 418,161,703.66 oz (sum of registered + eligible)
    
    The last numeric column in each row is the current closing inventory.
    """
    try:
        # Read Excel file from bytes
        df = pd.read_excel(
            io.BytesIO(file_content),
            engine='xlrd',  # For .xls files
            header=None
        )
        
        registered_oz = None
        eligible_oz = None
        combined_total = None
        
        # Look for specific total rows by text label
        for idx, row in df.iterrows():
            # Get the first cell as the label
            label = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
            
            # Get the last non-null numeric value (closing inventory)
            closing_val = None
            for val in reversed(row.values):
                if isinstance(val, (int, float)) and val > 0:
                    closing_val = float(val)
                    break
            
            if "TOTAL REGISTERED" in label and closing_val:
                registered_oz = closing_val
                logger.info(f"Found TOTAL REGISTERED at row {idx}: {registered_oz/1e6:.2f}M oz")
            elif "TOTAL ELIGIBLE" in label and closing_val:
                eligible_oz = closing_val
                logger.info(f"Found TOTAL ELIGIBLE at row {idx}: {eligible_oz/1e6:.2f}M oz")
            elif "COMBINED TOTAL" in label and closing_val:
                combined_total = closing_val
                logger.info(f"Found COMBINED TOTAL at row {idx}: {combined_total/1e6:.2f}M oz")
        
        # Validate we found the data
        if combined_total is None and (registered_oz is None or eligible_oz is None):
            logger.error("Could not find TOTAL REGISTERED, TOTAL ELIGIBLE, or COMBINED TOTAL rows")
            return None
        
        # Use combined total if found, otherwise sum registered + eligible
        if combined_total:
            total_oz = combined_total
            # If we didn't find individual totals, estimate from combined
            if registered_oz is None and eligible_oz is None:
                # COMEX typically has ~30% registered, ~70% eligible
                registered_oz = total_oz * 0.30
                eligible_oz = total_oz * 0.70
                logger.warning("Estimated registered/eligible from combined total")
        else:
            total_oz = (registered_oz or 0) + (eligible_oz or 0)
        
        # Sanity check: COMEX silver is typically 200M-600M oz total
        if total_oz < 100_000_000 or total_oz > 1_000_000_000:
            logger.warning(f"Total oz ({total_oz:,.0f}) outside typical range 100M-1000M")
        
        # Calculate daily change if we have previous data
        daily_change = None
        prev = get_latest_inventory()
        if prev:
            daily_change = total_oz - prev['total_oz']
        
        result = {
            'registered_oz': registered_oz,
            'eligible_oz': eligible_oz,
            'total_oz': total_oz,
            'daily_change_oz': daily_change,
            'timestamp': datetime.now().isoformat(),
            'source': 'CME'
        }
        
        logger.info(f"Parsed CME stocks: Registered={registered_oz/1e6:.2f}M oz, "
                   f"Eligible={eligible_oz/1e6:.2f}M oz, Total={total_oz/1e6:.2f}M oz")
        
        return result
        
    except Exception as e:
        logger.error(f"Error parsing CME stocks file: {e}")
        return None


def save_raw_file(content: bytes, filename: str = None):
    """Save raw downloaded file for debugging/auditing."""
    if filename is None:
        filename = f"silver_stocks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
    
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RAW_DATA_DIR / filename
    
    with open(filepath, 'wb') as f:
        f.write(content)
    
    logger.info(f"Saved raw file to: {filepath}")
    return filepath


def fetch_cme_stocks() -> Optional[Dict[str, Any]]:
    """
    Main function to fetch and process CME silver stocks data.
    Downloads file, parses it, and stores in database.
    """
    # Download the file
    content = download_cme_stocks_file()
    if content is None:
        return None
    
    # Optionally save raw file
    # save_raw_file(content)
    
    # Parse the data
    data = parse_cme_stocks(content)
    if data is None:
        return None
    
    # Store in database
    try:
        insert_inventory(
            registered_oz=data['registered_oz'],
            eligible_oz=data['eligible_oz'],
            total_oz=data['total_oz'],
            daily_change_oz=data.get('daily_change_oz'),
            source=data['source']
        )
        logger.info("Stored CME inventory data in database")
    except Exception as e:
        logger.error(f"Error storing inventory data: {e}")
    
    return data


def get_inventory_summary(data: Dict[str, Any]) -> str:
    """Generate human-readable summary of inventory data."""
    total_moz = data['total_oz'] / 1_000_000
    reg_moz = data['registered_oz'] / 1_000_000
    elig_moz = data['eligible_oz'] / 1_000_000
    
    change_str = ""
    if data.get('daily_change_oz'):
        change_moz = data['daily_change_oz'] / 1_000_000
        direction = "↑" if change_moz > 0 else "↓"
        change_str = f" ({direction} {abs(change_moz):.2f}M oz)"
    
    return (f"COMEX Silver Inventory: {total_moz:.2f}M oz{change_str}\n"
            f"  Registered: {reg_moz:.2f}M oz\n"
            f"  Eligible: {elig_moz:.2f}M oz")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("Testing CME stocks fetcher...")
    
    from scripts.db import init_database
    init_database()
    
    data = fetch_cme_stocks()
    if data:
        print("\n" + get_inventory_summary(data))
    else:
        print("Failed to fetch CME stocks data")
